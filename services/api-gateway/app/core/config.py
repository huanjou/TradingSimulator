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
    QUERY_SERVICE_GRPC_URL: str = "query-service:50051"

    # Cache
    REDIS_URL: AnyUrl = "redis://redis:6379"

    # Rate limiting (per authenticated user, order placement)
    ORDER_RATE_LIMIT_MAX_REQUESTS: int = 10
    ORDER_RATE_LIMIT_WINDOW_SECONDS: int = 1

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
