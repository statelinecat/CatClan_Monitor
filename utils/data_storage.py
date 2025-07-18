import sqlite3
from datetime import datetime
import pandas as pd
from config import Config


class BalanceStorage:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        """Инициализация подключения к БД с поддержкой многопоточности"""
        self.conn = sqlite3.connect(
            Config.SQLALCHEMY_DATABASE_URI.split('///')[1],
            check_same_thread=False,  # Ключевой параметр для Flask
            isolation_level=None,  # Автокоммит транзакций
            timeout=10.0  # Таймаут при блокировке
        )
        # Создание таблицы
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
        """Сохранение баланса в БД"""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO balance_history (timestamp, spot_balance, futures_balance, total_balance) VALUES (?, ?, ?, ?)",
                    (datetime.now(), spot_total, futures_total, spot_total + futures_total)
                )
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def get_balance_history(self, days=30):
        """Получение истории баланса"""
        try:
            query = """
                SELECT date(timestamp) as date, 
                       spot_balance, 
                       futures_balance,
                       total_balance
                FROM balance_history
                WHERE timestamp >= datetime('now', ?)
                ORDER BY date
            """
            return pd.read_sql(query, self.conn, params=[f'-{days} days'])
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()

    def close(self):
        """Закрытие соединения с БД"""
        if hasattr(self, 'conn'):
            self.conn.close()