from app.api.exceptions import (
    OrderSubmissionFailedException,
    OrderValidationException,
    setup_exception_handlers,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Setup a dummy app for testing handlers
app = FastAPI()
setup_exception_handlers(app)


@app.get("/test-validation")
async def trigger_validation_error():
    raise OrderValidationException("Price must be positive")


@app.get("/test-submission")
async def trigger_submission_error():
    raise OrderSubmissionFailedException("Kafka unavailable")


client = TestClient(app)


def test_order_validation_exception_handler():
    response = client.get("/test-validation")
    assert response.status_code == 400
    assert response.json() == {"detail": "Price must be positive"}


def test_order_submission_failed_exception_handler():
    response = client.get("/test-submission")
    assert response.status_code == 500
    assert response.json() == {"detail": "Kafka unavailable"}
