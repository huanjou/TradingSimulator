from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    KAFKA_BROKER: str = "localhost:9092"
    KAFKA_ORDERS_TOPIC: str = "orders"
    KAFKA_TRADES_TOPIC: str = "trades"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
