from app.db.session import engine
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("")
async def health_check(request: Request):
    """Liveness + readiness check: verifies Postgres and the gRPC server."""
    checks = {}

    # Check Postgres (replica)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "error"

    # Check gRPC server (started in lifespan)
    grpc_server = getattr(request.app.state, "grpc_server", None)
    checks["grpc"] = "ok" if grpc_server is not None else "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )
