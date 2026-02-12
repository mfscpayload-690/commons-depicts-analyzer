"""
SQLite Database Module

Manages local storage of file analysis results.
Uses a single table design for hackathon simplicity.
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "depicts.db")


def _get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite database with required schema."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            category TEXT NOT NULL,
            depicts TEXT,
            has_depicts INTEGER NOT NULL,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_name, category)
        )
    """)
    
    # Add analyzed_at column if it doesn't exist (migration)
    try:
        cursor.execute("SELECT analyzed_at FROM files LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE files ADD COLUMN analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    # Create index for faster category lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_category 
        ON files(category)
    """)
    
    conn.commit()
    conn.close()


def insert_file(file_name: str, category: str, depicts: Optional[str], has_depicts: bool) -> None:
    """
    Insert or update a file record.
    
    Args:
        file_name: Commons file name with "File:" prefix
        category: Category name with "Category:" prefix
        depicts: Comma-separated depicts labels (or None)
        has_depicts: Boolean flag
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO files (file_name, category, depicts, has_depicts, analyzed_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(file_name, category) 
        DO UPDATE SET 
            depicts = excluded.depicts,
            has_depicts = excluded.has_depicts,
            analyzed_at = CURRENT_TIMESTAMP
    """, (file_name, category, depicts, 1 if has_depicts else 0))
    
    conn.commit()
    conn.close()


def get_files_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all files for a category."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT file_name, depicts, has_depicts 
        FROM files 
        WHERE category = ?
        ORDER BY has_depicts DESC, file_name ASC
    """, (category,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_statistics(category: str) -> Dict[str, int]:
    """Get analysis statistics for a category."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
            SUM(CASE WHEN has_depicts = 0 THEN 1 ELSE 0 END) as without_depicts
        FROM files 
        WHERE category = ?
    """, (category,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row and row["total"] > 0:
        return {
            "total": row["total"],
            "with_depicts": row["with_depicts"] or 0,
            "without_depicts": row["without_depicts"] or 0
        }
    
    return {"total": 0, "with_depicts": 0, "without_depicts": 0}


def get_history_stats() -> List[Dict[str, Any]]:
    """
    Get aggregated statistics for all categories in the database.
    Used for the analysis history dashboard.
    
    Returns:
        List of category statistics including last analyzed timestamp
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            category,
            COUNT(*) as total,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
            SUM(CASE WHEN has_depicts = 0 THEN 1 ELSE 0 END) as without_depicts,
            MAX(analyzed_at) as last_analyzed
        FROM files
        GROUP BY category
        ORDER BY category ASC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        total = row["total"]
        with_dep = row["with_depicts"] or 0
        history.append({
            "category": row["category"],
            "total": total,
            "total_files": total,
            "with_depicts": with_dep,
            "without_depicts": total - with_dep,
            "last_analyzed": row["last_analyzed"]
        })
    
    return history


def get_all_categories() -> List[Dict[str, Any]]:
    """
    Get a list of all analyzed categories with file counts and coverage.
    Used by the /api/history endpoint.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            category,
            COUNT(*) as total_files,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts
        FROM files 
        GROUP BY category
        ORDER BY category ASC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    categories = []
    for row in rows:
        total = row["total_files"]
        with_dep = row["with_depicts"] or 0
        categories.append({
            "category": row["category"],
            "total_files": total,
            "with_depicts": with_dep,
            "without_depicts": total - with_dep
        })
    return categories


def verify_category_saved(category: str) -> Dict[str, Any]:
    """
    Verify that a category's data was saved to the database.
    Returns verification info including record count and sample data.
    """
    if not category.startswith("Category:"):
        category = f"Category:{category}"
    
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as cnt FROM files WHERE category = ?", (category,))
    count = cursor.fetchone()["cnt"]
    
    if count == 0:
        conn.close()
        return {"verified": False, "category": category, "record_count": 0}
    
    cursor.execute(
        "SELECT file_name, depicts, has_depicts FROM files WHERE category = ? LIMIT 5",
        (category,)
    )
    samples = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return {
        "verified": True,
        "category": category,
        "record_count": count,
        "sample_records": samples
    }


def clear_category(category: str) -> None:
    """Clear all records for a category."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM files WHERE category = ?", (category,))
    
    conn.commit()
    conn.close()
