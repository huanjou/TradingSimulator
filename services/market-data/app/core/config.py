from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    KAFKA_BROKER: str = "localhost:9092"
    KAFKA_MARKET_DATA_TOPIC: str = "market_data"

    # Provider config
    MARKET_PROVIDER: str = "binance"
    MARKET_SYMBOLS: str = "BTC/USD,ETH/USD"

    # Dependencies
    QUERY_SERVICE_URL: str = "http://query-service:8000"

    # Port for the minimal HTTP /health endpoint (Docker healthcheck)
    HEALTH_PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
