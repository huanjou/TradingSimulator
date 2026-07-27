import json
from unittest.mock import AsyncMock, patch

import pytest
from app.services.processor import process_orders


class MockMessage:
    def __init__(self, value_dict=None, raw_bytes=None):
        if raw_bytes is not None:
            self.value = raw_bytes
        else:
            self.value = json.dumps(value_dict).encode("utf-8")


@pytest.mark.asyncio
async def test_process_orders_success():
    messages = [
        MockMessage(
            {
                "id": "order-1",
                "user_id": "user-1",
                "symbol": "BTC/USD",
                "nested_data": {"key": "value"},
            }
        )
    ]

    with patch(
        "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
    ) as mock_cache:
        await process_orders(messages)

        mock_cache.assert_called_once()
        args, _ = mock_cache.call_args
        cached_dicts = args[0]

        assert len(cached_dicts) == 1
        assert cached_dicts[0]["id"] == "order-1"
        assert cached_dicts[0]["nested_data"] == '{"key":"value"}'


@pytest.mark.asyncio
async def test_process_orders_poison_pill():
    # Mix of valid and invalid messages
    messages = [
        MockMessage(raw_bytes=b"NOT VALID JSON {"),
        MockMessage({"id": "order-2"}),
    ]

    with patch(
        "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
    ) as mock_cache:
        await process_orders(messages)

        # Should only call cache_orders_bulk with the valid message
        mock_cache.assert_called_once()
        args, _ = mock_cache.call_args
        cached_dicts = args[0]

        assert len(cached_dicts) == 1
        assert cached_dicts[0]["id"] == "order-2"


@pytest.mark.asyncio
async def test_process_orders_cache_failure():
    messages = [MockMessage({"id": "order-3"})]

    with patch(
        "app.services.processor.cache_orders_bulk", new_callable=AsyncMock
    ) as mock_cache:
        mock_cache.side_effect = Exception("Redis Down")

        with pytest.raises(Exception, match="Redis Down"):
            await process_orders(messages)


@pytest.mark.asyncio
async def test_process_balance_updates():
    messages = [
        MockMessage(
            {
                "user_id": "user1",
                "currency": "USD",
                "available": "500.0",
                "locked": "10.0",
            }
        )
    ]

    with patch(
        "app.services.processor.cache_service", new_callable=AsyncMock
    ) as mock_cache_service:
        await process_orders(messages, topic="balance_updates")

        mock_cache_service.update_balance.assert_called_once_with(
            "user1", "USD", "500.0", "10.0"
        )
