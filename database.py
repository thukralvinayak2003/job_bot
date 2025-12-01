"""
database.py
Simple SQLite wrapper to store applied jobs and avoid duplicates.
"""

import sqlite3
import threading
from datetime import datetime

DB_PATH = "jobs.db"
_LOCK = threading.Lock()

class Database:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        with _LOCK:
            cur = self.conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS applied_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_link TEXT UNIQUE,
                company TEXT,
                role TEXT,
                status TEXT,
                timestamp TEXT
            )
            """)
            self.conn.commit()

    def add_job(self, job_link, company, role, status="applied"):
        with _LOCK:
            cur = self.conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO applied_jobs (job_link, company, role, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (job_link, company, role, status, datetime.utcnow().isoformat())
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate

    def has_job(self, job_link):
        with _LOCK:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM applied_jobs WHERE job_link = ?", (job_link,))
            return cur.fetchone() is not None

    def count_today(self):
        with _LOCK:
            cur = self.conn.cursor()
            today = datetime.utcnow().date().isoformat()
            cur.execute("SELECT COUNT(*) FROM applied_jobs WHERE timestamp >= ?", (today,))
            # Note: simplistic; timestamp is ISO-8601 string; future improvement: use proper timezone
            result = cur.fetchone()
            return result[0] if result else 0

    def get_applied_job_links(self):
        """Get list of all job links that have been applied to or marked as already applied"""
        try:
            with _LOCK:
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT job_link FROM applied_jobs 
                    WHERE status IN ('applied', 'already_applied')
                """)
                results = cursor.fetchall()
                return [row[0] for row in results]
        except Exception as e:
            print(f"Error getting applied job links: {e}")
            return []

    def is_job_applied(self, job_link):
        """Check if a specific job has already been applied to"""
        try:
            with _LOCK:
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM applied_jobs 
                    WHERE job_link = ? AND status IN ('applied', 'already_applied')
                """, (job_link,))
                return cursor.fetchone()[0] > 0
        except Exception as e:
            print(f"Error checking if job applied: {e}")
            return False

db = Database()