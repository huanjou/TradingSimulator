def test_health_check(client):
    """
    Test the /api/v1/health endpoint.
    It should return status code 200 and a JSON with health status.
    Since we run tests via docker-compose.test.yml, DB and Kafka are real,
    and they should report "connected".
    """
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["kafka"] == "connected"
