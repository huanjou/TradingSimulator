import os

# The Settings object is built at import time and requires these to be present,
# so they must be set before anything imports app.core.config.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://admin:password@127.0.0.1:5432/test_user_db"
)
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_unit_tests_0123456789")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")
