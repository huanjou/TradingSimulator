import time

import pytest
from app.core.middleware import (
    TRUSTED_PROXY_NETWORKS,
    CIDRProxyHeadersMiddleware,
    setup_middlewares,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


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


@pytest.fixture
def proxy_middleware():
    async def dummy_app(scope, receive, send):  # pragma: no cover
        pass

    return CIDRProxyHeadersMiddleware(
        dummy_app, trusted_networks=TRUSTED_PROXY_NETWORKS
    )


def test_proxy_headers_trusts_docker_networks(proxy_middleware):
    # Nginx containers on Docker internal networks are trusted proxies
    assert "172.18.0.5" in proxy_middleware.trusted_hosts
    assert "10.1.2.3" in proxy_middleware.trusted_hosts
    assert "192.168.16.2" in proxy_middleware.trusted_hosts
    assert "127.0.0.1" in proxy_middleware.trusted_hosts


def test_proxy_headers_rejects_untrusted_sources(proxy_middleware):
    # Public IPs must not be allowed to set X-Forwarded-For
    assert "203.0.113.10" not in proxy_middleware.trusted_hosts
    assert "8.8.8.8" not in proxy_middleware.trusted_hosts
    assert not proxy_middleware.always_trust


def test_proxy_headers_ignores_garbage_hosts(proxy_middleware):
    assert "not-an-ip" not in proxy_middleware.trusted_hosts
    assert None not in proxy_middleware.trusted_hosts


def test_spoofed_forwarded_for_ignored_from_untrusted_client(proxy_middleware):
    # An untrusted client presenting X-Forwarded-For keeps its socket address
    x_forwarded_hosts = ["1.2.3.4"]
    assert not proxy_middleware.always_trust
    assert "203.0.113.10" not in proxy_middleware.trusted_hosts
    # get_trusted_client_host is only consulted for trusted peers; for a
    # trusted nginx hop the reported client is the first untrusted entry.
    assert proxy_middleware.get_trusted_client_host(x_forwarded_hosts) == "1.2.3.4"
