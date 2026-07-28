from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    KAFKA_BROKER: str = "localhost:9092"
    KAFKA_ORDERS_TOPIC: str = "orders"
    KAFKA_TRADES_TOPIC: str = "trades"
    KAFKA_ORDER_UPDATES_TOPIC: str = "order_updates"
    KAFKA_MARKET_DATA_TOPIC: str = "market_data"
    KAFKA_WALLET_COMMANDS_TOPIC: str = "wallet_commands"
    KAFKA_BALANCE_UPDATES_TOPIC: str = "balance_updates"
    QUERY_SERVICE_URL: str = "http://query-service:8000"
    REDIS_URL: str = "redis://redis:6379/0"
    # Durable ledger used for cold-start recovery when no Redis snapshot exists.
    # Optional: if unset, the engine falls back to legacy empty-state startup.
    POSTGRES_URL: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
