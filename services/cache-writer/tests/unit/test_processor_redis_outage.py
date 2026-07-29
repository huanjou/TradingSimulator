"""Redis outage handling in the cache-writer batch processor.

Redis is a cache, not the source of truth: after the retry policy is
exhausted, the batch is dropped and the offset is committed anyway so the
consumer never stalls. Postgres (via ledger-writer) keeps the data, and the
cache converges once Redis is back. Any other error must still propagate.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
import redis.exceptions
from app.services.processor import process_balances, process_orders


class MockMessage:
    def __init__(self, value_dict):
        self.value = json.dumps(value_dict).encode("utf-8")


@pytest.mark.parametrize(
    "redis_error",
    [
        redis.exceptions.ConnectionError("connection refused"),
        redis.exceptions.TimeoutError("timed out"),
        OSError("socket closed"),
    ],
)
@pytest.mark.asyncio
async def test_orders_batch_is_dropped_when_redis_is_unreachable(redis_error):
    messages = [MockMessage({"id": "order-1", "user_id": "user-1"})]

    with patch(
        "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
    ) as mock_cache:
        mock_cache.side_effect = redis_error

        # Must not raise: a raising processor would block offset commits and
        # stall the whole pipeline for as long as Redis is down.
        await process_orders(messages)

    mock_cache.assert_awaited_once()


@pytest.mark.parametrize(
    "redis_error",
    [
        redis.exceptions.ConnectionError("connection refused"),
        redis.exceptions.TimeoutError("timed out"),
        OSError("socket closed"),
    ],
)
@pytest.mark.asyncio
async def test_balances_batch_is_dropped_when_redis_is_unreachable(redis_error):
    messages = [MockMessage({"user_id": "user-1", "currency": "USD"})]

    with patch(
        "app.services.cache_service.cache_balances_bulk", new_callable=AsyncMock
    ) as mock_cache:
        mock_cache.side_effect = redis_error

        await process_balances(messages)

    mock_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_outage_is_logged_with_the_dropped_order_ids():
    messages = [
        MockMessage({"id": "order-1", "user_id": "user-1"}),
        MockMessage({"id": "order-2", "user_id": "user-2"}),
    ]

    with (
        patch(
            "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
        ) as mock_cache,
        patch("app.services.processor.logger.error") as mock_log,
    ):
        mock_cache.side_effect = redis.exceptions.ConnectionError("down")
        await process_orders(messages)

    # The dropped ids must be recoverable from the logs for reconciliation.
    event, kwargs = mock_log.call_args[0][0], mock_log.call_args.kwargs
    assert event == "cache_batch_dropped_redis_unavailable"
    assert kwargs["batch_size"] == 2
    assert kwargs["order_ids"] == ["order-1", "order-2"]


@pytest.mark.asyncio
async def test_redis_outage_is_logged_with_the_dropped_balance_owners():
    messages = [MockMessage({"user_id": "user-1", "currency": "USD"})]

    with (
        patch(
            "app.services.cache_service.cache_balances_bulk", new_callable=AsyncMock
        ) as mock_cache,
        patch("app.services.processor.logger.error") as mock_log,
    ):
        mock_cache.side_effect = redis.exceptions.TimeoutError("down")
        await process_balances(messages)

    kwargs = mock_log.call_args.kwargs
    assert mock_log.call_args[0][0] == "cache_batch_dropped_redis_unavailable"
    assert kwargs["users"] == [("user-1", "USD")]


@pytest.mark.asyncio
async def test_unexpected_errors_still_propagate_for_orders():
    # Only Redis connectivity failures are swallowed; a bug must not be
    # silently masked as a cache outage.
    messages = [MockMessage({"id": "order-1"})]

    with patch(
        "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
    ) as mock_cache:
        mock_cache.side_effect = ValueError("unexpected bug")

        with pytest.raises(ValueError, match="unexpected bug"):
            await process_orders(messages)


@pytest.mark.asyncio
async def test_unexpected_errors_still_propagate_for_balances():
    messages = [MockMessage({"user_id": "user-1", "currency": "USD"})]

    with patch(
        "app.services.cache_service.cache_balances_bulk", new_callable=AsyncMock
    ) as mock_cache:
        mock_cache.side_effect = ValueError("unexpected bug")

        with pytest.raises(ValueError, match="unexpected bug"):
            await process_balances(messages)


@pytest.mark.asyncio
async def test_empty_batch_does_not_touch_redis():
    with patch(
        "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
    ) as mock_cache:
        await process_orders([])

    mock_cache.assert_not_awaited()
