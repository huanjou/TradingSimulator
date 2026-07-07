import os

os.environ.setdefault(
    "POSTGRES_URL", "postgresql+asyncpg://admin:password@127.0.0.1:5432/ledger_db"
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("KAFKA_BROKER", "127.0.0.1:9092")
os.environ.setdefault("ENV", "test")
