from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Trading Simulator Notification WS"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Kafka
    KAFKA_BROKER: str = "kafka:9092"
    KAFKA_ORDER_UPDATES_TOPIC: str = "order_updates"
    KAFKA_TRADES_TOPIC: str = "trades"
    KAFKA_BALANCE_UPDATES_TOPIC: str = "balance_updates"

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Otel
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://jaeger:4317"
    OTEL_SERVICE_NAME: str = "notification-ws"

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", extra="ignore"
    )


def get_settings() -> Settings:
    return Settings()
