import sqlite3
from datetime import datetime
from typing import Optional

if __package__:
    from .config import DATABASE_PATH, ensure_app_dirs
else:
    from config import DATABASE_PATH, ensure_app_dirs

DATABASE = str(DATABASE_PATH)


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            operator_id TEXT,
            batch_id TEXT,
            final_count INTEGER,
            video_path TEXT,
            created_by INTEGER
        )
        """
    )

    # Migration safety for existing databases.
    if not _column_exists(cursor, "sessions", "created_by"):
        cursor.execute("ALTER TABLE sessions ADD COLUMN created_by INTEGER")
    if not _column_exists(cursor, "sessions", "started_at"):
        cursor.execute("ALTER TABLE sessions ADD COLUMN started_at TEXT")
    if not _column_exists(cursor, "sessions", "ended_at"):
        cursor.execute("ALTER TABLE sessions ADD COLUMN ended_at TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS session_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT,
            last_seen_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_products_session_id ON session_products(session_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_products_product_name ON session_products(product_name)"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            codec TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
        """
    )
    if not _column_exists(cursor, "videos", "codec"):
        cursor.execute("ALTER TABLE videos ADD COLUMN codec TEXT")
    if not _column_exists(cursor, "videos", "created_at"):
        cursor.execute("ALTER TABLE videos ADD COLUMN created_at TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_session_id ON videos(session_id)")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # Default settings
    default_settings = [
        ("company_name", "Nexus Industrial Trace", "2026-03-22T20:15:00Z"),
        ("company_address", "Global HQ, Tech Sector 7", "2026-03-22T20:15:00Z"),
        ("company_contact", "+1-800-NEXUS-01", "2026-03-22T20:15:00Z"),
        ("company_gst_id", "GST-NEXUS-7788", "2026-03-22T20:15:00Z"),
        ("company_logo_url", "", "2026-03-22T20:15:00Z"),
        ("default_conf_threshold", "0.50", "2026-03-22T20:15:00Z"),
        ("default_iou_threshold", "0.65", "2026-03-22T20:15:00Z"),
        ("default_roi_padding", "5", "2026-03-22T20:15:00Z"),
        ("retention_days", "30", "2026-03-22T20:15:00Z"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
        default_settings
    )

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
            (username, password_hash, full_name, int(is_admin), _utcnow_iso()),
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


def save_session(
    operator_id,
    batch_id,
    final_count,
    video_path,
    created_by: Optional[int] = None,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    timestamp = ended_at or _utcnow_iso()
    cursor.execute(
        """
        INSERT INTO sessions (timestamp, operator_id, batch_id, final_count, video_path, created_by, started_at, ended_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (timestamp, operator_id, batch_id, final_count, video_path, created_by, started_at, ended_at),
    )
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


def upsert_product(name: str) -> int:
    normalized = (name or "").strip()
    if not normalized:
        raise ValueError("Product name cannot be empty.")

    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM products WHERE lower(name) = lower(?)", (normalized,))
    existing = cursor.fetchone()
    if existing:
        product_id = existing["id"]
    else:
        cursor.execute(
            "INSERT INTO products (name, created_at) VALUES (?, ?)",
            (normalized, _utcnow_iso()),
        )
        product_id = cursor.lastrowid
        conn.commit()
    conn.close()
    return product_id


def save_session_products(session_id: int, product_counts: dict, product_timestamps: Optional[dict] = None):
    ensure_app_dirs()
    product_timestamps = product_timestamps or {}

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_products WHERE session_id = ?", (session_id,))

    now = _utcnow_iso()
    for name, value in sorted(product_counts.items()):
        product_name = str(name or "").strip()
        if not product_name:
            continue
        count = max(0, int(value or 0))
        cursor.execute("SELECT id FROM products WHERE lower(name) = lower(?)", (product_name,))
        existing = cursor.fetchone()
        if existing:
            product_id = existing["id"]
        else:
            cursor.execute(
                "INSERT INTO products (name, created_at) VALUES (?, ?)",
                (product_name, now),
            )
            product_id = cursor.lastrowid

        timestamps = product_timestamps.get(product_name, {})
        first_seen_at = timestamps.get("first_seen_at")
        last_seen_at = timestamps.get("last_seen_at")
        cursor.execute(
            """
            INSERT INTO session_products (
                session_id, product_id, product_name, count, first_seen_at, last_seen_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, product_id, product_name, count, first_seen_at, last_seen_at, now),
        )

    conn.commit()
    conn.close()


def get_session_products(session_id: int):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, product_id, product_name, count, first_seen_at, last_seen_at
        FROM session_products
        WHERE session_id = ?
        ORDER BY product_name ASC
        """,
        (session_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_video_metadata(session_id: int, file_path: str, codec: str = "mp4v"):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO videos (session_id, file_path, codec, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, file_path, codec, _utcnow_iso()),
    )
    conn.commit()
    video_id = cursor.lastrowid
    conn.close()
    return video_id


def update_session_video_path(session_id: int, video_path: str):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET video_path = ? WHERE id = ?",
        (video_path, session_id),
    )
    conn.commit()
    conn.close()


def get_latest_video_for_session(session_id: int):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM videos
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_video_by_id(video_id: int):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_videos_for_session(session_id: int):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, session_id, file_path, codec, created_at
        FROM videos
        WHERE session_id = ?
        ORDER BY id DESC
        """,
        (session_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_sessions_detailed(
    created_by: Optional[int] = None,
    is_admin: bool = False,
    operator_id: Optional[str] = None,
    product_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()

    where = []
    params = []

    if not is_admin:
        where.append("s.created_by = ?")
        params.append(created_by)

    if operator_id:
        where.append("s.operator_id = ?")
        params.append(operator_id)

    if date_from:
        where.append("date(s.timestamp) >= date(?)")
        params.append(date_from)

    if date_to:
        where.append("date(s.timestamp) <= date(?)")
        params.append(date_to)

    if search:
        where.append(
            """
            (
                CAST(s.id AS TEXT) LIKE ?
                OR COALESCE(s.operator_id, '') LIKE ?
                OR COALESCE(s.batch_id, '') LIKE ?
            )
            """
        )
        token = f"%{search.strip()}%"
        params.extend([token, token, token])

    if product_name:
        where.append(
            """
            EXISTS (
                SELECT 1
                FROM session_products spx
                WHERE spx.session_id = s.id
                  AND lower(spx.product_name) = lower(?)
            )
            """
        )
        params.append(product_name)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    cursor.execute(
        f"""
        SELECT
            s.id,
            s.timestamp,
            s.operator_id,
            s.batch_id,
            s.final_count,
            s.video_path,
            s.started_at,
            s.ended_at,
            v.id AS resolved_video_id,
            COALESCE(v.file_path, s.video_path) AS resolved_video_path,
            COALESCE(SUM(sp.count), 0) AS products_total_count
        FROM sessions s
        LEFT JOIN session_products sp ON sp.session_id = s.id
        LEFT JOIN (
            SELECT v1.id, v1.session_id, v1.file_path
            FROM videos v1
            WHERE v1.id = (
                SELECT MAX(v2.id)
                FROM videos v2
                WHERE v2.session_id = v1.session_id
            )
        ) v ON v.session_id = s.id
        {where_clause}
        GROUP BY s.id
        ORDER BY s.timestamp DESC
        """,
        tuple(params),
    )

    rows = cursor.fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["products"] = get_session_products(item["id"])
        item["video_available"] = bool(item.get("resolved_video_path"))
        if item["products"]:
            item["products_label"] = ", ".join(f"{p['product_name']} ({p['count']})" for p in item["products"])
        else:
            item["products_label"] = ""
        result.append(item)

    conn.close()
    return result


def get_history_filters():
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT operator_id
        FROM sessions
        WHERE operator_id IS NOT NULL AND TRIM(operator_id) != ''
        ORDER BY operator_id ASC
        """
    )
    operators = [row["operator_id"] for row in cursor.fetchall()]

    cursor.execute(
        """
        SELECT DISTINCT product_name
        FROM session_products
        WHERE product_name IS NOT NULL AND TRIM(product_name) != ''
        ORDER BY product_name ASC
        """
    )
    products = [row["product_name"] for row in cursor.fetchall()]

    conn.close()
    return {"operators": operators, "products": products}


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

    cursor.execute(
        """
        SELECT product_name, COALESCE(SUM(count), 0) AS total
        FROM session_products
        GROUP BY product_name
        ORDER BY total DESC
        LIMIT 5
        """
    )
    top_products = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "total_sessions": totals["total_sessions"],
        "total_count": totals["total_count"],
        "today_sessions": today["today_sessions"],
        "latest_timestamp": totals["latest_timestamp"],
        "total_users": users["total_users"],
        "recent_sessions": recent,
        "top_products": top_products,
    }
def get_system_settings():
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def update_system_setting(key, value):
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, str(value), _utcnow_iso()),
    )
    conn.commit()
    conn.close()


def purge_all_data():
    ensure_app_dirs()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_products")
    cursor.execute("DELETE FROM videos")
    cursor.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()


def get_sessions_by_ids(session_ids: list):
    ensure_app_dirs()
    if not session_ids:
        return []
    conn = _connect()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in session_ids)
    cursor.execute(
        f"""
        SELECT * FROM sessions 
        WHERE id IN ({placeholders})
        ORDER BY timestamp DESC
        """,
        tuple(session_ids),
    )
    rows = cursor.fetchall()
    conn.close()
    return [tuple(row) for row in rows]
