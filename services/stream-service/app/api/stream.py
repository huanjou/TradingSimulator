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
    symbol: str = Query(..., description="Symbol to subscribe to, or comma-separated list (e.g., BTC/USD,ETH/USD)"),
    streamer: StreamManager = Depends(get_streamer),
) -> EventSourceResponse:
    """
    SSE endpoint to stream market data for a specific symbol or multiple symbols.
    """

    async def event_generator():
        symbols_list = [s.strip() for s in symbol.split(",")]
        q = streamer.subscribe(symbols_list)
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
            streamer.unsubscribe(symbols_list, q)

    return EventSourceResponse(event_generator())
