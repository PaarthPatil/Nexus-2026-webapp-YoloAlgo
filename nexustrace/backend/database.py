import sqlite3
from datetime import datetime
from typing import Optional

if __package__:
    from .config import DATABASE_PATH, ensure_app_dirs
else:
    from config import DATABASE_PATH, ensure_app_dirs

DATABASE = str(DATABASE_PATH)


def _connect():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col["name"] == column_name for col in columns)


def _row_to_dict(row):
    return dict(row) if row else None


def init_db():
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            operator_id TEXT,
            batch_id TEXT,
            final_count INTEGER,
            video_path TEXT,
            created_by INTEGER
        )
    ''')

    # Migration safety for existing databases created before created_by was added.
    if not _column_exists(cursor, "sessions", "created_by"):
        cursor.execute("ALTER TABLE sessions ADD COLUMN created_by INTEGER")

    conn.commit()
    conn.close()


def count_users():
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def create_user(username, password_hash, full_name=None, is_admin=False):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, full_name, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, password_hash, full_name, int(is_admin), datetime.utcnow().isoformat()),
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return None
    conn.close()
    return user_id


def get_user_by_username(username):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = _row_to_dict(cursor.fetchone())
    conn.close()
    return user


def get_user_by_id(user_id):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = _row_to_dict(cursor.fetchone())
    conn.close()
    return user


def save_session(operator_id, batch_id, final_count, video_path, created_by: Optional[int] = None):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().isoformat()
    cursor.execute('''
        INSERT INTO sessions (timestamp, operator_id, batch_id, final_count, video_path, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, operator_id, batch_id, final_count, video_path, created_by))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_sessions(created_by: Optional[int] = None, is_admin: bool = False):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    if is_admin:
        cursor.execute("SELECT * FROM sessions ORDER BY timestamp DESC")
    else:
        cursor.execute("SELECT * FROM sessions WHERE created_by = ? ORDER BY timestamp DESC", (created_by,))
    rows = cursor.fetchall()
    conn.close()
    return [tuple(row) for row in rows]


def get_session(session_id, created_by: Optional[int] = None, is_admin: bool = False):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    if is_admin:
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    else:
        cursor.execute("SELECT * FROM sessions WHERE id = ? AND created_by = ?", (session_id, created_by))
    row = cursor.fetchone()
    conn.close()
    return tuple(row) if row else None


def get_dashboard_stats(created_by: Optional[int] = None, is_admin: bool = False):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()

    if is_admin:
        cursor.execute(
            """
            SELECT COUNT(*) AS total_sessions,
                   COALESCE(SUM(final_count), 0) AS total_count,
                   MAX(timestamp) AS latest_timestamp
            FROM sessions
            """
        )
        totals = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS today_sessions
            FROM sessions
            WHERE date(timestamp) = date('now')
            """
        )
        today = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        users = cursor.fetchone()
    else:
        cursor.execute(
            """
            SELECT COUNT(*) AS total_sessions,
                   COALESCE(SUM(final_count), 0) AS total_count,
                   MAX(timestamp) AS latest_timestamp
            FROM sessions
            WHERE created_by = ?
            """,
            (created_by,),
        )
        totals = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS today_sessions
            FROM sessions
            WHERE created_by = ?
              AND date(timestamp) = date('now')
            """,
            (created_by,),
        )
        today = cursor.fetchone()
        users = {"total_users": None}

    cursor.execute(
        """
        SELECT id, timestamp, operator_id, batch_id, final_count
        FROM sessions
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT 5
        """.format(where_clause="" if is_admin else "WHERE created_by = ?"),
        () if is_admin else (created_by,),
    )
    recent = [tuple(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "total_sessions": totals["total_sessions"],
        "total_count": totals["total_count"],
        "today_sessions": today["today_sessions"],
        "latest_timestamp": totals["latest_timestamp"],
        "total_users": users["total_users"],
        "recent_sessions": recent,
    }
