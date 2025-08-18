import logging
import sqlite3
from datetime import datetime
import pandas as pd
from config import Config

class BalanceStorage:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._init_db()

    def _init_db(self):
        try:
            self.conn = sqlite3.connect(
                Config.SQLALCHEMY_DATABASE_URI.split('///')[1],
                check_same_thread=False,
                isolation_level=None,
                timeout=10.0
            )
            self._create_tables()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    def _create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    spot_balance REAL NOT NULL,
                    futures_balance REAL NOT NULL,
                    total_balance REAL NOT NULL
                )
            """)

    def save_balance(self, spot_total, futures_total):
        try:
            with self.conn:
                self.conn.execute(
                    """INSERT INTO balance_history 
                    (timestamp, spot_balance, futures_balance, total_balance) 
                    VALUES (?, ?, ?, ?)""",
                    (datetime.now(), spot_total, futures_total, spot_total + futures_total)
                )
            self.logger.info(f"Saved balances - Spot: {spot_total:.2f}, Futures: {futures_total:.2f}")
        except sqlite3.Error as e:
            self.logger.error(f"Error saving balances: {e}")

    def get_balance_history(self, days=30):
        try:
            query = """
                SELECT date(timestamp) as date, 
                       spot_balance, 
                       futures_balance
                FROM balance_history
                WHERE timestamp >= datetime('now', ?)
                ORDER BY date
            """
            df = pd.read_sql(query, self.conn, params=[f'-{days} days'])
            return df
        except sqlite3.Error as e:
            self.logger.error(f"Error getting balance history: {e}")
            return pd.DataFrame()

    def close(self):
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
                self.logger.info("Database connection closed")
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")