from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "wallet-service"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Redis (Read Model)
    REDIS_URL: str = "redis://redis:6379/0"

    # Kafka
    KAFKA_BROKER: str = "kafka:9092"
    KAFKA_WALLET_COMMANDS_TOPIC: str = "wallet_commands"

    # Auth
    JWT_SECRET: str = "supersecretjwtkey123"
    JWT_ALGORITHM: str = "HS256"

    # Telemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://jaeger:4317"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
