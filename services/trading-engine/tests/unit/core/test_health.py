"""The tiny HTTP server behind the Docker healthcheck of the worker services.

trading-engine, ledger-writer and market-data are not web applications, so
their /health endpoint is this hand-rolled asyncio server. It must report 200
only when every dependency check reports "ok", and 503 otherwise, so an
unhealthy container is actually restarted instead of silently limping along.
"""

import asyncio
import json

import pytest
from app.core.health import HealthServer


async def _request_health(port: int) -> tuple[int, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()

    raw = await asyncio.wait_for(reader.read(), timeout=5)
    writer.close()

    head, _, body = raw.partition(b"\r\n\r\n")
    status_code = int(head.split(b"\r\n")[0].split(b" ")[1])
    return status_code, json.loads(body)


async def _serve(checks_fn) -> tuple[HealthServer, int]:
    # Port 0 lets the OS pick a free port so tests never collide.
    server = HealthServer(checks_fn, port=0)
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    return server, port


def _checks(**values):
    async def _fn() -> dict[str, str]:
        return dict(values)

    return _fn


@pytest.mark.asyncio
async def test_all_checks_ok_reports_200_healthy():
    server, port = await _serve(_checks(kafka="ok", postgres="ok"))
    try:
        status_code, body = await _request_health(port)
    finally:
        await server.stop()

    assert status_code == 200
    assert body == {
        "status": "healthy",
        "checks": {"kafka": "ok", "postgres": "ok"},
    }


@pytest.mark.asyncio
async def test_single_failing_check_reports_503_degraded():
    server, port = await _serve(_checks(kafka="ok", postgres="error"))
    try:
        status_code, body = await _request_health(port)
    finally:
        await server.stop()

    # One broken dependency is enough to fail the healthcheck.
    assert status_code == 503
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"] == "error"


@pytest.mark.asyncio
async def test_non_ok_status_values_are_treated_as_unhealthy():
    server, port = await _serve(_checks(kafka="degraded"))
    try:
        status_code, body = await _request_health(port)
    finally:
        await server.stop()

    assert status_code == 503
    assert body["status"] == "degraded"


@pytest.mark.asyncio
async def test_no_checks_reports_healthy():
    # A service without dependencies is healthy as soon as it serves requests.
    server, port = await _serve(_checks())
    try:
        status_code, body = await _request_health(port)
    finally:
        await server.stop()

    assert status_code == 200
    assert body == {"status": "healthy", "checks": {}}


@pytest.mark.asyncio
async def test_status_is_recomputed_on_every_request():
    state = {"kafka": "ok"}

    async def checks_fn() -> dict[str, str]:
        return dict(state)

    server, port = await _serve(checks_fn)
    try:
        assert (await _request_health(port))[0] == 200

        state["kafka"] = "error"
        assert (await _request_health(port))[0] == 503

        state["kafka"] = "ok"
        assert (await _request_health(port))[0] == 200
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_failing_checks_fn_does_not_kill_the_server():
    calls = {"n": 0}

    async def flaky_checks() -> dict[str, str]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("check blew up")
        return {"kafka": "ok"}

    server, port = await _serve(flaky_checks)
    try:
        # The first request gets no usable response...
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\n\r\n")
        await writer.drain()
        assert await asyncio.wait_for(reader.read(), timeout=5) == b""
        writer.close()

        # ...but the server keeps serving the next one.
        assert (await _request_health(port))[0] == 200
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_stop_closes_the_listening_socket():
    server, port = await _serve(_checks(kafka="ok"))
    await server.stop()

    with pytest.raises(OSError):
        await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=5)


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    server, _ = await _serve(_checks(kafka="ok"))
    await server.stop()
    # A second stop during shutdown must not raise.
    await server.stop()
    assert server._server is None
