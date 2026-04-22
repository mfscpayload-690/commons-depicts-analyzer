"""
Database Module — Commons Depicts Analyzer

SQLite for local development, PostgreSQL on Railway (or any DATABASE_URL).
DATABASE_URL is set automatically by Railway when a Postgres service is linked.
"""

import os
import queue
import threading
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway sometimes gives postgres:// but psycopg2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_POSTGRES = bool(DATABASE_URL)

# ── SQLite setup ──────────────────────────────────────────────────────────────
if not USE_POSTGRES:
    import sqlite3

    DB_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "depicts.db")
    )
    _POOL_SIZE = 5
    _pool: queue.LifoQueue = queue.LifoQueue(maxsize=_POOL_SIZE)
    _pool_lock = threading.Lock()
    _pool_created = 0

    def _create_sqlite_conn():
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _get_connection():
        global _pool_created
        conn = None
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            with _pool_lock:
                if _pool_created < _POOL_SIZE:
                    conn = _create_sqlite_conn()
                    _pool_created += 1
                else:
                    conn = _pool.get(timeout=5)
        try:
            yield conn
        finally:
            if conn is not None:
                try:
                    _pool.put_nowait(conn)
                except queue.Full:
                    conn.close()

# ── PostgreSQL setup ──────────────────────────────────────────────────────────
else:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool as pg_pool

    _pg_pool = pg_pool.ThreadedConnectionPool(1, 10, DATABASE_URL)

    @contextmanager
    def _get_connection():
        conn = _pg_pool.getconn()
        conn.autocommit = False
        try:
            yield conn
        finally:
            _pg_pool.putconn(conn)


# ── Static SQL (no f-strings — placeholders are dialect constants) ────────────
# SQLite uses ?, PostgreSQL uses %s. Defined once here, used throughout.

_SQL_INSERT_PG = """
    INSERT INTO files (file_name, category, depicts, has_depicts, analyzed_at)
    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
    ON CONFLICT (file_name, category) DO UPDATE SET
        depicts     = EXCLUDED.depicts,
        has_depicts = EXCLUDED.has_depicts,
        analyzed_at = CURRENT_TIMESTAMP
"""

_SQL_INSERT_SQ = """
    INSERT INTO files (file_name, category, depicts, has_depicts, analyzed_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(file_name, category) DO UPDATE SET
        depicts     = excluded.depicts,
        has_depicts = excluded.has_depicts,
        analyzed_at = CURRENT_TIMESTAMP
"""

_SQL_SELECT_FILES_PG = """
    SELECT file_name, depicts, has_depicts
    FROM files
    WHERE category = %s
    ORDER BY has_depicts DESC, file_name ASC
"""

_SQL_SELECT_FILES_SQ = """
    SELECT file_name, depicts, has_depicts
    FROM files
    WHERE category = ?
    ORDER BY has_depicts DESC, file_name ASC
"""

_SQL_STATS_PG = """
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
        SUM(CASE WHEN has_depicts = 0 THEN 1 ELSE 0 END) as without_depicts
    FROM files WHERE category = %s
"""

_SQL_STATS_SQ = """
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
        SUM(CASE WHEN has_depicts = 0 THEN 1 ELSE 0 END) as without_depicts
    FROM files WHERE category = ?
"""

_SQL_COUNT_PG = "SELECT COUNT(*) as cnt FROM files WHERE category = %s"
_SQL_COUNT_SQ = "SELECT COUNT(*) as cnt FROM files WHERE category = ?"

_SQL_SAMPLE_PG = "SELECT file_name, depicts, has_depicts FROM files WHERE category = %s LIMIT 5"
_SQL_SAMPLE_SQ = "SELECT file_name, depicts, has_depicts FROM files WHERE category = ? LIMIT 5"

_SQL_DELETE_PG = "DELETE FROM files WHERE category = %s"
_SQL_DELETE_SQ = "DELETE FROM files WHERE category = ?"


# ── Public API ────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    with _get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id          SERIAL PRIMARY KEY,
                    file_name   TEXT NOT NULL,
                    category    TEXT NOT NULL,
                    depicts     TEXT,
                    has_depicts INTEGER NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (file_name, category)
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_category ON files(category)"
            )
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name   TEXT NOT NULL,
                    category    TEXT NOT NULL,
                    depicts     TEXT,
                    has_depicts INTEGER NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(file_name, category)
                )
            """)
            try:
                cur.execute("SELECT analyzed_at FROM files LIMIT 1")
            except Exception:
                cur.execute(
                    "ALTER TABLE files ADD COLUMN analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_category ON files(category)"
            )
        conn.commit()


def insert_file(
    file_name: str, category: str, depicts: Optional[str], has_depicts: bool
) -> None:
    sql = _SQL_INSERT_PG if USE_POSTGRES else _SQL_INSERT_SQ
    with _get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (file_name, category, depicts, 1 if has_depicts else 0))
        conn.commit()


def get_files_by_category(category: str) -> List[Dict[str, Any]]:
    sql = _SQL_SELECT_FILES_PG if USE_POSTGRES else _SQL_SELECT_FILES_SQ
    with _get_connection() as conn:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql, (category,))
        return [dict(r) for r in cur.fetchall()]


def get_statistics(category: str) -> Dict[str, int]:
    sql = _SQL_STATS_PG if USE_POSTGRES else _SQL_STATS_SQ
    with _get_connection() as conn:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql, (category,))
        row = dict(cur.fetchone())
        if row and row["total"]:
            return {
                "total": int(row["total"]),
                "with_depicts": int(row["with_depicts"] or 0),
                "without_depicts": int(row["without_depicts"] or 0),
            }
        return {"total": 0, "with_depicts": 0, "without_depicts": 0}


def get_all_categories() -> List[Dict[str, Any]]:
    sql = """
        SELECT
            category,
            COUNT(*) as total_files,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
            MAX(analyzed_at) as last_analyzed
        FROM files
        GROUP BY category
        ORDER BY category ASC
    """
    with _get_connection() as conn:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql)
        result = []
        for row in cur.fetchall():
            row = dict(row)
            total = int(row["total_files"])
            with_dep = int(row["with_depicts"] or 0)
            result.append({
                "category": row["category"],
                "total_files": total,
                "with_depicts": with_dep,
                "without_depicts": total - with_dep,
                "last_analyzed": row["last_analyzed"],
            })
        return result


def get_history_stats() -> List[Dict[str, Any]]:
    sql = """
        SELECT
            category,
            COUNT(*) as total,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
            SUM(CASE WHEN has_depicts = 0 THEN 1 ELSE 0 END) as without_depicts,
            MAX(analyzed_at) as last_analyzed
        FROM files
        GROUP BY category
        ORDER BY category ASC
    """
    with _get_connection() as conn:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql)
        history = []
        for row in cur.fetchall():
            row = dict(row)
            total = int(row["total"])
            with_dep = int(row["with_depicts"] or 0)
            history.append({
                "category": row["category"],
                "total": total,
                "total_files": total,
                "with_depicts": with_dep,
                "without_depicts": total - with_dep,
                "last_analyzed": row["last_analyzed"],
            })
        return history


def verify_category_saved(category: str) -> Dict[str, Any]:
    if not category.startswith("Category:"):
        category = f"Category:{category}"
    sql_count = _SQL_COUNT_PG if USE_POSTGRES else _SQL_COUNT_SQ
    sql_sample = _SQL_SAMPLE_PG if USE_POSTGRES else _SQL_SAMPLE_SQ
    with _get_connection() as conn:
        if USE_POSTGRES:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        cur.execute(sql_count, (category,))
        count = int(dict(cur.fetchone())["cnt"])
        if count == 0:
            return {"verified": False, "category": category, "record_count": 0}
        cur.execute(sql_sample, (category,))
        samples = [dict(r) for r in cur.fetchall()]
        return {
            "verified": True,
            "category": category,
            "record_count": count,
            "sample_records": samples,
        }


def clear_category(category: str) -> None:
    sql = _SQL_DELETE_PG if USE_POSTGRES else _SQL_DELETE_SQ
    with _get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (category,))
        conn.commit()
