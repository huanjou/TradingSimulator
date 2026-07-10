from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    KAFKA_BROKER: str = "localhost:9092"
    KAFKA_MARKET_DATA_TOPIC: str = "market_data"
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws/btcusdt@bookTicker"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
