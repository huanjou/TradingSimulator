import asyncio
from contextlib import asynccontextmanager

import uvicorn
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.telemetry import setup_opentelemetry
from app.services.consumer import consume
from fastapi import FastAPI

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Kafka consumer as a background task
    shutdown_event = asyncio.Event()
    consumer_task = asyncio.create_task(consume(shutdown_event))
    app.state.consumer_task = consumer_task
    yield
    # Shutdown: let the in-flight batch finish (bounded), then cancel
    shutdown_event.set()
    try:
        await asyncio.wait_for(
            asyncio.gather(consumer_task, return_exceptions=True), timeout=10
        )
    except TimeoutError:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(health_router)

if __name__ == "__main__":
    setup_logging(log_level=settings.LOG_LEVEL)
    setup_opentelemetry()
    uvicorn.run(app, host="0.0.0.0", port=settings.HTTP_PORT)
