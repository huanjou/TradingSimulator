from functools import lru_cache

from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Cache Writer"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    HTTP_PORT: int = 8000

    # Message Broker
    KAFKA_BROKER: str = "kafka:9092"
    KAFKA_ORDER_UPDATES_TOPIC: str = "order_updates"
    KAFKA_CONSUMER_GROUP: str = "cache-writer-group"

    # Cache
    REDIS_URL: AnyUrl = "redis://redis:6379"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
