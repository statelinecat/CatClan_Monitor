import os
from dotenv import load_dotenv

# Загрузка переменных окружения с обработкой ошибок
try:
    load_dotenv()
except Exception as e:
    print(f"Warning: Could not load .env file - {e}")


class Config:
    # API Binance
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
    BINANCE_API_URL = os.getenv('BINANCE_API_URL', 'https://api.binance.com')
    BINANCE_REQUEST_TIMEOUT = int(os.getenv('BINANCE_REQUEST_TIMEOUT', '10'))

    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///balances.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Validation
    @classmethod
    def validate_config(cls):
        required_vars = ['BINANCE_API_KEY', 'BINANCE_API_SECRET']
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required config variables: {', '.join(missing)}")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


# Добавьте в конфиг
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 3600
}