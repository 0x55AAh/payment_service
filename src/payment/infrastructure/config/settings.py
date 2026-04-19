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
    API_KEY: str = "test_api_key"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_service"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_JSON: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    def setup_logging(self) -> None:
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
        
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

settings = Settings()
