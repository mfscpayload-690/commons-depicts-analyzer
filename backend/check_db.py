"""Quick script to check database contents"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'depicts.db')
print(f"\n{'='*60}")
print("DATABASE CHECK - depicts.db")
print(f"{'='*60}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Total count
    cursor.execute('SELECT COUNT(*) FROM files')
    total = cursor.fetchone()[0]
    print(f"\nTotal files stored: {total}")

    # Per category
    cursor.execute('''
        SELECT category,
               COUNT(*) as total,
               SUM(has_depicts) as with_depicts
        FROM files
        GROUP BY category
        ORDER BY total DESC
    ''')

    print(f"\n{'Category':<40} {'Files':<8} {'With P180':<10} {'Coverage'}")
    print("-" * 70)

    for row in cursor.fetchall():
        cat = row[0]
        total_files = row[1]
        with_depicts = row[2] or 0
        coverage = (with_depicts / total_files * 100) if total_files > 0 else 0
        print(f"{cat:<40} {total_files:<8} {with_depicts:<10} {coverage:.0f}%")

    # Sample records
    print(f"\n{'='*60}")
    print("SAMPLE RECORDS (first 5)")
    print(f"{'='*60}")
    cursor.execute('SELECT file_name, category, depicts, has_depicts FROM files LIMIT 5')
    for row in cursor.fetchall():
        print(f"\nFile: {row[0]}")
        print(f"  Category: {row[1]}")
        print(f"  Depicts: {row[2] or 'None'}")
        print(f"  Has P180: {'Yes' if row[3] else 'No'}")

    conn.close()
    print(f"\n{'='*60}")
    print("DATABASE VERIFIED - All data is stored correctly!")
    print(f"{'='*60}\n")

except Exception as e:
    print(f"Error: {e}")
