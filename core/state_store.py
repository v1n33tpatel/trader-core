import sqlite3, os
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.getenv(
    "TRADER_STATE_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trader_state.db"),
)

class StateStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    broker TEXT,
                    side TEXT,
                    units REAL,
                    entry_price REAL,
                    current_price REAL,
                    opened_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_audit (
                    date TEXT PRIMARY KEY,
                    realized_pnl REAL,
                    order_count INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_resources (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_url_or_path TEXT,
                    summary TEXT,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    openwebui_file_id TEXT,
                    last_synced_at TIMESTAMP,
                    auto_update INTEGER DEFAULT 1,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_sync_logs (
                    id TEXT PRIMARY KEY,
                    synced_at TIMESTAMP NOT NULL,
                    trigger_type TEXT NOT NULL,
                    items_synced INTEGER NOT NULL,
                    items_failed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    details_json TEXT
                )
            """)
            conn.commit()

    def record_trade(self, position_id: str, symbol: str, broker: str, side: str, units: float, price: float):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO positions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (position_id, symbol, broker, side, units, price, price, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()

    def set_setting(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings VALUES (?, ?, ?)",
                (key, str(value), datetime.now(timezone.utc).isoformat())
            )
            conn.commit()


    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def get_all_settings(self) -> dict[str, str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_positions(self, limit: int = 50) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM positions ORDER BY opened_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_audits(self, limit: int = 30) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM daily_audit ORDER BY date DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Custom Resources & Open-WebUI RAG Sync
    # =========================================================================

    def save_resource(self, resource: dict) -> dict:
        """Inserts or updates a custom resource in SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        res_id = resource.get("id")
        created_at = resource.get("created_at") or now
        updated_at = now

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO custom_resources (
                    id, category, title, source_url_or_path, summary, content,
                    metadata_json, openwebui_file_id, last_synced_at, auto_update,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category=excluded.category,
                    title=excluded.title,
                    source_url_or_path=excluded.source_url_or_path,
                    summary=excluded.summary,
                    content=excluded.content,
                    metadata_json=excluded.metadata_json,
                    openwebui_file_id=coalesce(excluded.openwebui_file_id, custom_resources.openwebui_file_id),
                    last_synced_at=coalesce(excluded.last_synced_at, custom_resources.last_synced_at),
                    auto_update=excluded.auto_update,
                    updated_at=excluded.updated_at
                """,
                (
                    res_id,
                    resource.get("category", "WEBSITE"),
                    resource.get("title", "Untitled Resource"),
                    resource.get("source_url_or_path", ""),
                    resource.get("summary", ""),
                    resource.get("content", ""),
                    resource.get("metadata_json", "{}"),
                    resource.get("openwebui_file_id"),
                    resource.get("last_synced_at"),
                    1 if resource.get("auto_update", 1) in (1, True, "1") else 0,
                    created_at,
                    updated_at
                )
            )
            conn.commit()
        return self.get_resource(res_id) or resource

    def get_resource(self, resource_id: str) -> dict | None:
        """Retrieves a single custom resource by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM custom_resources WHERE id = ?", (resource_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_resources(self, category: str | None = None, limit: int = 200) -> list[dict]:
        """Lists all custom resources, optionally filtered by category."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if category and category.upper() != "ALL":
                cursor = conn.execute(
                    "SELECT * FROM custom_resources WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                    (category.upper(), limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM custom_resources ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def delete_resource(self, resource_id: str) -> bool:
        """Deletes a custom resource from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM custom_resources WHERE id = ?", (resource_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_resource_sync(self, resource_id: str, openwebui_file_id: str, last_synced_at: str | None = None):
        """Updates the Open-WebUI file ID and last synced timestamp for a resource."""
        synced_at = last_synced_at or datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE custom_resources SET openwebui_file_id = ?, last_synced_at = ?, updated_at = ? WHERE id = ?",
                (openwebui_file_id, synced_at, synced_at, resource_id)
            )
            conn.commit()

    def record_sync_log(self, log_entry: dict):
        """Records a sync audit log entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO resource_sync_logs (
                    id, synced_at, trigger_type, items_synced, items_failed, status, duration_ms, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_entry.get("id"),
                    log_entry.get("synced_at", datetime.now(timezone.utc).isoformat()),
                    log_entry.get("trigger_type", "MANUAL_UI"),
                    int(log_entry.get("items_synced", 0)),
                    int(log_entry.get("items_failed", 0)),
                    log_entry.get("status", "SUCCESS"),
                    float(log_entry.get("duration_ms", 0.0)),
                    log_entry.get("details_json", "[]")
                )
            )
            conn.commit()

    def get_sync_logs(self, limit: int = 30) -> list[dict]:
        """Retrieves recent sync audit logs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM resource_sync_logs ORDER BY synced_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]


