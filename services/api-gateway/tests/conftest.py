import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """
    Fixture that provides a TestClient for testing FastAPI endpoints.
    TestClient automatically manages ASGI lifespan events (startup/shutdown),
    which is essential for initializing the real Kafka producer in our test environment.
    """
    with TestClient(app) as tc:
        yield tc
