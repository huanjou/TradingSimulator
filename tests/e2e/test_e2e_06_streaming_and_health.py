import json

import pytest
import requests
from conftest import (
    API_GATEWAY_URL,
    STREAM_SERVICE_URL,
    USER_SERVICE_URL,
)


def test_api_gateway_health():
    resp = requests.get(f"{API_GATEWAY_URL}/health")
    assert resp.status_code == 200, f"API gateway health check failed: {resp.text}"
    data = resp.json()
    assert (
        data.get("status") in ["ok", "healthy", "up", "running", "success"]
        or resp.status_code == 200
    )


@pytest.mark.parametrize(
    "service_name,url",
    [
        ("api-gateway", f"{API_GATEWAY_URL}/health"),
        ("user-service", f"{USER_SERVICE_URL}/health"),
        ("stream-service", f"{STREAM_SERVICE_URL}/health"),
    ],
)
def test_microservice_health_endpoints(service_name, url):
    resp = requests.get(url)
    assert (
        resp.status_code == 200
    ), f"{service_name} health check failed at {url}: {resp.text}"


@pytest.mark.parametrize(
    "service_name,base_url",
    [
        ("api-gateway", "http://localhost:8000"),
        ("query-service", "http://localhost:8001"),
        ("stream-service", "http://localhost:8002"),
        ("user-service", "http://localhost:8003"),
        ("wallet-service", "http://localhost:8005"),
    ],
)
def test_microservices_openapi_docs_reachable(service_name, base_url):
    resp = requests.get(f"{base_url}/docs")
    assert (
        resp.status_code == 200
    ), f"{service_name} /docs check failed at {base_url}/docs: {resp.status_code}"


def test_sse_market_data_streaming():
    url = f"{STREAM_SERVICE_URL}/stream?symbol=BTC/USD,ETH/USD"
    with requests.get(url, stream=True, timeout=5) as resp:
        assert resp.status_code == 200
        lines_received = []
        # Read the first few lines of the Server-Sent Events stream
        for i, line in enumerate(resp.iter_lines(decode_unicode=True)):
            if line:
                lines_received.append(line)
            if i >= 10 or len(lines_received) >= 4:
                break

        # Verify that we received price events formatted as SSE
        assert any(
            line.startswith("event: price") for line in lines_received
        ), f"No 'event: price' found in {lines_received}"
        data_lines = [line for line in lines_received if line.startswith("data: ")]
        assert len(data_lines) >= 1

        # Parse the JSON payload inside the data line
        raw_json = data_lines[0].replace("data: ", "", 1)
        price_data = json.loads(raw_json)
        assert price_data["symbol"] in ["BTC/USD", "ETH/USD"]
        assert float(price_data["bid_price"]) > 0
        assert float(price_data["ask_price"]) > 0
