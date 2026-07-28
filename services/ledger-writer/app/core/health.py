"""Minimal HTTP server exposing GET /health for Docker healthchecks.

The service is not a web application, so instead of pulling in a full web
framework we serve the single endpoint with a tiny asyncio server.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable

import structlog

logger = structlog.get_logger(__name__)


class HealthServer:
    """Serves GET /health, reporting per-dependency connectivity checks."""

    def __init__(
        self,
        checks_fn: Callable[[], Awaitable[dict[str, str]]],
        port: int = 8000,
    ):
        self._checks_fn = checks_fn
        self._port = port
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "0.0.0.0", self._port)
        logger.info("health_server_started", port=self._port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("health_server_stopped")

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            # Read and discard the request headers; only GET /health is served.
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)

            checks = await self._checks_fn()
            all_ok = all(v == "ok" for v in checks.values())
            body = json.dumps(
                {"status": "healthy" if all_ok else "degraded", "checks": checks}
            ).encode()
            status_line = b"200 OK" if all_ok else b"503 Service Unavailable"
            writer.write(
                b"HTTP/1.1 " + status_line + b"\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            await writer.drain()
        except Exception as e:
            logger.warning("health_request_failed", error=str(e))
        finally:
            writer.close()
