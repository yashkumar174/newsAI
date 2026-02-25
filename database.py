import sqlite3
from datetime import datetime


DB_PATH = "users.db"


def init_db(db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                timezone TEXT DEFAULT 'UTC',
                schedule_hour INTEGER DEFAULT 8,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, topic)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                alert_date TEXT NOT NULL,
                alert_count INTEGER DEFAULT 0,
                UNIQUE(chat_id, alert_date)
            )
        ''')

        # Migration: if old 'topic' column exists in users, migrate data
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'topic' in columns:
            rows = conn.execute('SELECT chat_id, topic FROM users WHERE topic IS NOT NULL').fetchall()
            for chat_id, topic in rows:
                try:
                    conn.execute('INSERT OR IGNORE INTO topics (chat_id, topic) VALUES (?, ?)', (chat_id, topic))
                except Exception:
                    pass
            # Drop old column by recreating table (SQLite doesn't support DROP COLUMN in older versions)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users_new (
                    chat_id INTEGER PRIMARY KEY,
                    timezone TEXT DEFAULT 'UTC',
                    schedule_hour INTEGER DEFAULT 8,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('INSERT OR IGNORE INTO users_new (chat_id, updated_at) SELECT chat_id, updated_at FROM users')
            conn.execute('DROP TABLE users')
            conn.execute('ALTER TABLE users_new RENAME TO users')


# --- User management ---

def ensure_user(chat_id: int, db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        conn.execute('INSERT OR IGNORE INTO users (chat_id) VALUES (?)', (chat_id,))


def set_user_timezone(chat_id: int, timezone: str, hour: int, db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        conn.execute('''
            INSERT INTO users (chat_id, timezone, schedule_hour)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET timezone=excluded.timezone, schedule_hour=excluded.schedule_hour
        ''', (chat_id, timezone, hour))


def get_user_settings(chat_id: int, db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        cursor = conn.execute('SELECT timezone, schedule_hour FROM users WHERE chat_id=?', (chat_id,))
        row = cursor.fetchone()
        return row if row else ('UTC', 8)


# --- Topics management ---

def add_topic(chat_id: int, topic: str, db_path=None):
    db = db_path or DB_PATH
    ensure_user(chat_id, db_path)
    with sqlite3.connect(db) as conn:
        conn.execute('INSERT OR IGNORE INTO topics (chat_id, topic) VALUES (?, ?)', (chat_id, topic.lower().strip()))


def remove_topic(chat_id: int, topic: str, db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        conn.execute('DELETE FROM topics WHERE chat_id=? AND topic=?', (chat_id, topic.lower().strip()))


def get_user_topics(chat_id: int, db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        cursor = conn.execute('SELECT topic FROM topics WHERE chat_id=?', (chat_id,))
        return [row[0] for row in cursor.fetchall()]


def clear_topics(chat_id: int, db_path=None):
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        conn.execute('DELETE FROM topics WHERE chat_id=?', (chat_id,))


def get_all_users(db_path=None):
    """Returns list of (chat_id, timezone, schedule_hour)."""
    db = db_path or DB_PATH
    with sqlite3.connect(db) as conn:
        cursor = conn.execute('SELECT chat_id, timezone, schedule_hour FROM users')
        return cursor.fetchall()


def get_all_users_with_topics(db_path=None):
    """Returns list of (chat_id, timezone, schedule_hour, topics_list)."""
    db = db_path or DB_PATH
    users = get_all_users(db_path)
    result = []
    for chat_id, tz, hour in users:
        topics = get_user_topics(chat_id, db_path)
        if topics:
            result.append((chat_id, tz, hour, topics))
    return result


# --- Alert tracking ---

def get_alert_count(chat_id: int, date_str: str = None, db_path=None):
    db = db_path or DB_PATH
    date_str = date_str or datetime.utcnow().strftime('%Y-%m-%d')
    with sqlite3.connect(db) as conn:
        cursor = conn.execute(
            'SELECT alert_count FROM alerts_log WHERE chat_id=? AND alert_date=?',
            (chat_id, date_str)
        )
        row = cursor.fetchone()
        return row[0] if row else 0


def increment_alert_count(chat_id: int, date_str: str = None, db_path=None):
    db = db_path or DB_PATH
    date_str = date_str or datetime.utcnow().strftime('%Y-%m-%d')
    with sqlite3.connect(db) as conn:
        conn.execute('''
            INSERT INTO alerts_log (chat_id, alert_date, alert_count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, alert_date) DO UPDATE SET alert_count = alert_count + 1
        ''', (chat_id, date_str))


# Backward compat alias
def set_user_topic(chat_id: int, topic: str, db_path=None):
    add_topic(chat_id, topic, db_path)
