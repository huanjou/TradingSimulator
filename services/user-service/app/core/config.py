from pydantic import PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "user-service"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # DB
    DATABASE_URL: PostgresDsn

    # Auth
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # short-lived; renewed via refresh token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @model_validator(mode="after")
    def validate_jwt_secret_length(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if len(self.JWT_SECRET.get_secret_value()) < 32:
                raise ValueError(
                    "JWT_SECRET must be at least 32 characters in production"
                )
        return self

    @property
    def COOKIE_SECURE(self) -> bool:
        return self.ENVIRONMENT == "production"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Telemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://jaeger:4317"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
