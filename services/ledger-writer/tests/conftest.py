import os

os.environ["POSTGRES_URL"] = (
    "postgresql+asyncpg://admin:password@localhost:5432/ledger_db"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["KAFKA_BROKER"] = "localhost:9092"
os.environ["ENV"] = "test"
