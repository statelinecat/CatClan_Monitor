import sqlite3
from datetime import datetime
from config import Config
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HistoricalDataImporter:
    def __init__(self):
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Инициализация подключения к БД"""
        try:
            db_path = Config.SQLALCHEMY_DATABASE_URI.split('///')[1]
            self.conn = sqlite3.connect(
                db_path,
                check_same_thread=False,
                isolation_level=None,
                timeout=10.0
            )
            logger.info(f"Connected to database at {db_path}")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def add_historical_data(self, date, futures_balance, spot_balance=0):
        """Добавление исторических данных баланса"""
        try:
            with self.conn:
                # Проверяем существование записи
                cursor = self.conn.execute(
                    "SELECT 1 FROM balance_history WHERE date(timestamp) = date(?)",
                    (date,)
                )
                if cursor.fetchone() is None:
                    self.conn.execute(
                        """INSERT INTO balance_history 
                        (timestamp, spot_balance, futures_balance, total_balance) 
                        VALUES (?, ?, ?, ?)""",
                        (date, spot_balance, futures_balance, spot_balance + futures_balance)
                    )
                    logger.info(f"Added: {date} - Futures: {futures_balance:.2f} USDT")
                    return True
                else:
                    logger.info(f"Skipped (exists): {date}")
                    return False
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def close(self):
        """Закрытие соединения с БД"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def import_historical_data():
    """Основная функция импорта данных"""
    historical_data = [
        # Формат: (дата, фьючерсный баланс)
        ("01.08.2025", 110.00),
        ("02.08.2025", 114.63),
        ("03.08.2025", 113.04),
        ("04.08.2025", 111.69),
        ("05.08.2025", 128.52),
        ("06.08.2025", 138.49),
        ("07.08.2025", 141.30),
        ("08.08.2025", 106.60),
        ("09.08.2025", 157.34),
        ("10.08.2025", 154.08),
        ("11.08.2025", 153.80),
        ("12.08.2025", 157.32),
        ("13.08.2025", 144.07),
        ("14.08.2025", 168.32),
        ("15.08.2025", 171.52),
        ("16.08.2025", 167.32),
        ("17.08.2025", 168.93)
    ]

    importer = HistoricalDataImporter()
    if not importer.conn:
        return False

    added_count = 0
    skipped_count = 0

    try:
        for date_str, futures_balance in historical_data:
            try:
                date = datetime.strptime(date_str, '%d.%m.%Y')
                if importer.add_historical_data(date, futures_balance):
                    added_count += 1
                else:
                    skipped_count += 1
            except ValueError as e:
                logger.error(f"Invalid date format {date_str}: {e}")
                continue

        logger.info(f"Import completed. Added: {added_count}, Skipped: {skipped_count}")
        return True

    except Exception as e:
        logger.error(f"Fatal error during import: {e}")
        return False
    finally:
        importer.close()


if __name__ == '__main__':
    logger.info("Starting historical data import...")

    if import_historical_data():
        logger.info("Data import finished successfully!")
        exit(0)
    else:
        logger.error("Data import failed!")
        exit(1)