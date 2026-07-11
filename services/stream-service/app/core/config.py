from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "stream-service"
    VERSION: str = "0.1.0"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    MARKET_DATA_TOPIC: str = "market_data"
    REDIS_URL: str = "redis://redis:6379/0"

    class Config:
        case_sensitive = True


settings = Settings()
