from functools import lru_cache

from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Trading Simulator API Gateway"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Message Broker
    KAFKA_BROKER: str = "kafka:9092"

    # Services
    USER_SERVICE_URL: AnyUrl = "http://user-service:8000"

    # Cache
    REDIS_URL: AnyUrl = "redis://redis:6379"

    # Auth
    JWT_SECRET: str = "supersecretjwtkey123"
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
