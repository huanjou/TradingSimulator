import pytest
from app.services.kafka_worker import kafka_worker


@pytest.mark.asyncio
async def test_health_check(async_client):
    # The Kafka worker is started in the app lifespan, which the test
    # client does not run; start it here (Kafka/Redis are mocked).
    await kafka_worker.start()
    try:
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["checks"]["kafka"] == "ok"
    finally:
        await kafka_worker.stop()


@pytest.mark.asyncio
async def test_health_check_degraded_without_kafka(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["kafka"] == "error"
