import json
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class JsonFormatter(logging.Formatter):
    """
    Кастомный JSON-форматтер для логирования.
    """
    def format(self, record: logging.LogRecord) -> str:
        """
        Преобразует запись лога в JSON-строку.
        """
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

class Settings(BaseSettings):
    """
    Класс настроек приложения, использующий pydantic-settings для загрузки из переменных окружения и .env файла.
    """
    API_KEY: str = "test_api_key"
    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_service"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    
    # Outbox settings
    OUTBOX_CLEANUP_INTERVAL: int = 60  # Интервал очистки в секундах
    OUTBOX_RETENTION_DAYS: int = 1     # Сколько дней хранить обработанные сообщения
    OUTBOX_BATCH_SIZE: int = 10        # Размер пачки для обработки Relay
    OUTBOX_EMPTY_POLLING_INTERVAL: float = 5.0  # Интервал ожидания при пустой очереди (сек)
    OUTBOX_PROCESSING_INTERVAL: float = 1.0     # Интервал между батчами (сек)

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    LOG_JSON: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def setup_logging(self) -> None:
        """
        Настраивает систему логирования приложения.
        Устанавливает уровень логирования, удаляет существующие обработчики и добавляет
        StreamHandler с соответствующим форматтером (JSON или текстовый).
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(self.LOG_LEVEL)

        # Очищаем существующие хендлеры, чтобы избежать дублирования
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        handler = logging.StreamHandler()

        formatter: logging.Formatter
        if self.LOG_JSON:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(self.LOG_FORMAT)

        formatter.datefmt = self.LOG_DATE_FORMAT
        
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

settings = Settings()
