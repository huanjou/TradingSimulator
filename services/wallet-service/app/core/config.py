from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known insecure default that must never be used outside local development.
INSECURE_JWT_SECRET = "supersecretjwtkey123"  # noqa: S105


class Settings(BaseSettings):
    PROJECT_NAME: str = "wallet-service"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Redis (Read Model)
    REDIS_URL: str = "redis://redis:6379/0"

    # Kafka
    KAFKA_BROKER: str = "kafka:9092"
    KAFKA_WALLET_COMMANDS_TOPIC: str = "wallet_commands"

    # Auth (JWT_SECRET is required, no insecure default baked into the image)
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Telemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://jaeger:4317"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="after")
    def check_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production" and self.JWT_SECRET == INSECURE_JWT_SECRET:
            raise ValueError("Cannot use default JWT_SECRET in production!")
        return self


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
