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
            conn.commit()

    def record_trade(self, position_id: str, symbol: str, broker: str, side: str, units: float, price: float):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO positions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (position_id, symbol, broker, side, units, price, price, datetime.now(timezone.utc))
            )
            conn.commit()
