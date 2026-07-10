import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import setup_middlewares


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    setup_middlewares(app)

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    return app


def test_logging_middleware(app_with_middleware):
    from structlog.testing import capture_logs

    client = TestClient(app_with_middleware)

    with capture_logs() as log_output:
        start = time.time()
        response = client.get("/test")
        end = time.time()

    assert response.status_code == 200

    # The logging middleware should have recorded one event
    assert len(log_output) == 1
    log_entry = log_output[0]

    assert log_entry["event"] == "http_request"
    assert log_entry["method"] == "GET"
    assert log_entry["path"] == "/test"
    assert log_entry["status_code"] == 200
    assert "duration" in log_entry
    assert log_entry["duration"] <= (end - start)
