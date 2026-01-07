import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

def migrate():
    """lectures 테이블에 keywords 컬럼 추가"""
    db_path = Config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(lectures)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'keywords' in columns:
            print("Colum 'keywords' already exists in 'lectures' table.")
        else:
            print("Adding 'keywords' column to 'lectures' table...")
            cursor.execute("ALTER TABLE lectures ADD COLUMN keywords TEXT")
            conn.commit()
            print("Migration successful: Added 'keywords' column.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
