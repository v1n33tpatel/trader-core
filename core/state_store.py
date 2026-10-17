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

