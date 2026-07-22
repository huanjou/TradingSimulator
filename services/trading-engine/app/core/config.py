from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    KAFKA_BROKER: str = "localhost:9092"
    KAFKA_ORDERS_TOPIC: str = "orders"
    KAFKA_TRADES_TOPIC: str = "trades"
    KAFKA_ORDER_UPDATES_TOPIC: str = "order_updates"
    KAFKA_MARKET_DATA_TOPIC: str = "market_data"
    QUERY_SERVICE_URL: str = "http://query-service:8000"
    REDIS_URL: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
