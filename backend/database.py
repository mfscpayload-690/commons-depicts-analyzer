"""
SQLite Database Module

Manages local storage of file analysis results.
Enhanced with timestamp tracking and verification functions.
"""

import sqlite3
import os
from datetime import datetime
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
    """Initialize the database schema."""
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
        file_name: File title from Commons
        category: Category being analyzed
        depicts: Comma-separated depicts labels (or None)
        has_depicts: Whether file has P180 statements
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO files (file_name, category, depicts, has_depicts, analyzed_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(file_name, category) 
        DO UPDATE SET depicts = excluded.depicts, has_depicts = excluded.has_depicts, analyzed_at = CURRENT_TIMESTAMP
    """, (file_name, category, depicts, 1 if has_depicts else 0))
    
    conn.commit()
    conn.close()


def get_files_by_category(category: str) -> List[Dict[str, Any]]:
    """
    Get all files for a category.
    
    Args:
        category: Category name
    
    Returns:
        List of file records as dicts
    """
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
    """
    Get analysis statistics for a category.
    
    Args:
        category: Category name
    
    Returns:
        Dict with total, with_depicts, and without_depicts counts
    """
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


def clear_category(category: str) -> None:
    """
    Clear all records for a category (for re-analysis).
    
    Args:
        category: Category name
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM files WHERE category = ?", (category,))
    
    conn.commit()
    conn.close()


def verify_category_saved(category: str) -> Dict[str, Any]:
    """
    Verify that a category's data was properly saved to the database.
    
    Args:
        category: Category name
    
    Returns:
        Dict with verification info including record count, timestamps, and sample data
    """
    # Normalize category name
    if not category.startswith("Category:"):
        category = f"Category:{category}"
    
    conn = _get_connection()
    cursor = conn.cursor()
    
    # Get count and timestamps
    cursor.execute("""
        SELECT 
            COUNT(*) as total_records,
            MIN(analyzed_at) as first_analyzed,
            MAX(analyzed_at) as last_analyzed,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
            SUM(CASE WHEN has_depicts = 0 THEN 1 ELSE 0 END) as without_depicts
        FROM files 
        WHERE category = ?
    """, (category,))
    
    row = cursor.fetchone()
    
    # Get sample records
    cursor.execute("""
        SELECT file_name, depicts, has_depicts, analyzed_at
        FROM files 
        WHERE category = ?
        LIMIT 5
    """, (category,))
    samples = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    if row and row["total_records"] > 0:
        return {
            "category": category,
            "verified": True,
            "total_records": row["total_records"],
            "with_depicts": row["with_depicts"] or 0,
            "without_depicts": row["without_depicts"] or 0,
            "first_analyzed": row["first_analyzed"],
            "last_analyzed": row["last_analyzed"],
            "sample_records": samples
        }
    
    return {
        "category": category,
        "verified": False,
        "total_records": 0,
        "message": "No records found for this category in database"
    }


def get_all_categories() -> List[Dict[str, Any]]:
    """
    Get a summary of all analyzed categories in the database.
    
    Returns:
        List of category summaries with counts and timestamps
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            category,
            COUNT(*) as total_files,
            SUM(CASE WHEN has_depicts = 1 THEN 1 ELSE 0 END) as with_depicts,
            MAX(analyzed_at) as last_analyzed
        FROM files 
        GROUP BY category
        ORDER BY last_analyzed DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
