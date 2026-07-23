import asyncio

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.services.streamer import StreamManager

router = APIRouter()


def get_streamer(request: Request) -> StreamManager:
    return request.app.state.streamer


@router.get("/stream")
async def stream_prices(
    request: Request,
    symbol: str = Query(..., description="Symbol to subscribe to, e.g., BTCUSDT"),
    streamer: StreamManager = Depends(get_streamer),
) -> EventSourceResponse:
    """
    SSE endpoint to stream market data for a specific symbol.
    """

    async def event_generator():
        q = streamer.subscribe(symbol)
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    data_bytes = await asyncio.wait_for(q.get(), timeout=1.0)
                    # Yield raw json string (decode bytes to str for SSE)
                    yield {"event": "price", "data": data_bytes.decode("utf-8")}
                except asyncio.TimeoutError:
                    # Keep connection alive
                    yield {"event": "ping", "data": "ping"}
        finally:
            streamer.unsubscribe(symbol, q)

    return EventSourceResponse(event_generator())
