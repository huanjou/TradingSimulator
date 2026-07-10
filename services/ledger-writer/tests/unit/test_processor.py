import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.processor import process_orders


class MockMessage:
    def __init__(self, value_dict):
        self.value = json.dumps(value_dict).encode("utf-8")


@pytest.mark.asyncio
async def test_process_orders_success():
    messages = [
        MockMessage(
            {
                "id": "order-1",
                "user_id": "user-1",
                "symbol": "BTC/USD",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "1.0",
                "price": "50000",
                "status": "OPEN",
            }
        )
    ]

    with patch("app.services.processor.AsyncSessionLocal") as mock_session_maker:
        mock_session = AsyncMock()
        # Async context manager mock
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        await process_orders(messages)

        # Assertions
        assert mock_session.execute.call_count == 2  # 1 for user, 1 for order
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_orders_db_failure():
    messages = [
        MockMessage(
            {
                "id": "order-1",
                "user_id": "user-1",
                "symbol": "BTC/USD",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "1.0",
                "price": "50000",
                "status": "OPEN",
            }
        )
    ]

    with patch("app.services.processor.AsyncSessionLocal") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB Connection Failed")
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        # We expect the exception to be raised, not swallowed
        with pytest.raises(Exception, match="DB Connection Failed"):
            await process_orders(messages, topic="orders")

        mock_session.commit.assert_not_called()
        mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_process_orders_update_success():
    messages = [
        MockMessage(
            {
                "order_id": "order-1",
                "status": "FILLED",
                "filled_quantity": 1.0,
            }
        )
    ]

    with patch("app.services.processor.AsyncSessionLocal") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        await process_orders(messages, topic="order_updates")

        # Assertions
        assert mock_session.execute.call_count == 1  # 1 for order_repo.update_status
        mock_session.commit.assert_called_once()
