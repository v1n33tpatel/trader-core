import sqlite3, os
from datetime import datetime

class StateStore:
    def __init__(self, db_path: str = "/home/vineet/trader-core/trader_state.db"):
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
                (position_id, symbol, broker, side, units, price, price, datetime.utcnow())
            )
            conn.commit()
