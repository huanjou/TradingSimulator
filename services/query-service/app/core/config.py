from functools import lru_cache

from pydantic import AnyUrl, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Trading Simulator API Gateway"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database
    POSTGRES_URL: PostgresDsn
    POSTGRES_PRIMARY_URL: PostgresDsn | None = None

    # Message Broker
    KAFKA_BROKER: str = "kafka:9092"

    # Cache
    REDIS_URL: AnyUrl = "redis://redis:6379"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
