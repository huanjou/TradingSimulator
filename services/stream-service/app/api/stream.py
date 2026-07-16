import asyncio

import orjson
from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.services.kafka_streamer import kafka_streamer

router = APIRouter()


@router.get("/stream")
async def stream_prices(request: Request, symbol: str = Query(None)):
    """
    SSE endpoint to stream market data.
    If `symbol` is provided, filters to that symbol.
    """

    async def event_generator():
        q = kafka_streamer.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    data = await asyncio.wait_for(q.get(), timeout=1.0)
                    if symbol and data.get("symbol") != symbol:
                        continue

                    yield {"event": "price", "data": orjson.dumps(data).decode("utf-8")}
                except asyncio.TimeoutError:
                    # Keep connection alive
                    yield {"event": "ping", "data": "ping"}
        finally:
            kafka_streamer.unsubscribe(q)

    return EventSourceResponse(event_generator())
