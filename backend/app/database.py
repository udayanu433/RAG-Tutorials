import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "academic_hub.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        role_access TEXT NOT NULL, -- 'Student', 'Faculty', or 'All'
        created_at TEXT NOT NULL
    )
    """)
    
    # Documents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        file_path TEXT NOT NULL,
        gemini_file_name TEXT,
        role_access TEXT NOT NULL, -- 'Student', 'Faculty', or 'All'
        doc_type TEXT NOT NULL,
        topic TEXT NOT NULL,
        uploaded_at TEXT NOT NULL
    )
    """)
    
    # Pre-populate with some sample notifications if table is empty
    cursor.execute("SELECT COUNT(*) FROM notifications")
    if cursor.fetchone()[0] == 0:
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO notifications (title, content, role_access, created_at) VALUES (?, ?, ?, ?)",
            ("KTU Semester Registration Extension", "The deadline for KTU B.Tech semester registration has been extended to August 15th, 2026. Please complete the process on the portal.", "All", now)
        )
        cursor.execute(
            "INSERT INTO notifications (title, content, role_access, created_at) VALUES (?, ?, ?, ?)",
            ("Faculty Meeting: Curriculum Revision", "Urgent meeting for all faculty members on August 1st at 10:00 AM regarding the new KTU curriculum revision updates.", "Faculty", now)
        )
        cursor.execute(
            "INSERT INTO notifications (title, content, role_access, created_at) VALUES (?, ?, ?, ?)",
            ("Activity Points Submission Mandate", "All final year students must submit their Activity Points certificate verification documents to their advisors by August 10th.", "Student", now)
        )
    
    conn.commit()
    conn.close()
    print("[INFO] SQLite database initialized successfully.")

if __name__ == "__main__":
    init_db()
