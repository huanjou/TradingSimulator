import ipaddress
import time

import structlog
from app.core.config import get_settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

logger = structlog.get_logger("api_access")
settings = get_settings()

# Only proxies on these networks (Docker internal ranges + localhost) may set
# X-Forwarded-For. Requests from any other address keep their socket IP, so a
# client hitting the gateway directly cannot spoof its IP to dodge rate limits.
TRUSTED_PROXY_NETWORKS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.1/32",
]


class _TrustedNetworks:
    """Set-like container that matches host IPs against CIDR ranges."""

    def __init__(self, networks: list[str]):
        self.networks = [ipaddress.ip_network(net) for net in networks]

    def __contains__(self, host: str | None) -> bool:
        if host is None:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(ip in net for net in self.networks)


class CIDRProxyHeadersMiddleware(ProxyHeadersMiddleware):
    """ProxyHeadersMiddleware with CIDR support.

    uvicorn's ProxyHeadersMiddleware only accepts literal IPs or '*', which
    would either miss the nginx container (its IP is dynamic) or trust any
    client. This subclass swaps the literal-IP set for CIDR matching.
    """

    def __init__(self, app, trusted_networks: list[str]):
        super().__init__(app, trusted_hosts=[])
        self.trusted_hosts = _TrustedNetworks(trusted_networks)
        self.always_trust = False


def setup_middlewares(app: FastAPI):
    """
    Configures all application middlewares (CORS, Rate Limiting, etc.)
    """

    # Trust X-Forwarded-For headers only from our Nginx proxy (Docker internal
    # networks / localhost). This updates request.client.host to the user's
    # real IP while ignoring spoofed headers from untrusted sources.
    app.add_middleware(
        CIDRProxyHeadersMiddleware, trusted_networks=TRUSTED_PROXY_NETWORKS
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=process_time,
        )
        return response

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
