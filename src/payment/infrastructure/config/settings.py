import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_KEY: str = "test_api_key"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_service"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    def setup_logging(self):
        logging.basicConfig(
            level=self.LOG_LEVEL,
            format=self.LOG_FORMAT,
            force=True  # Переопределяем существующую конфигурацию
        )

settings = Settings()
