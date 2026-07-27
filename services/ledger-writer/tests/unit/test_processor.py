import json
from unittest.mock import AsyncMock

import pytest
from app.services.processor import process_orders

class MockMessage:
    def __init__(self, value_dict=None, raw_value=None):
        if raw_value is not None:
            self.value = raw_value
        else:
            self.value = json.dumps(value_dict).encode("utf-8")


@pytest.fixture
def mock_repos():
    return {
        "order_repo": AsyncMock(),
        "trade_repo": AsyncMock(),
        "symbol_repo": AsyncMock(),
        "balance_repo": AsyncMock()
    }


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_process_orders_success(mock_session, mock_repos):
    messages = [
        MockMessage(
            {
                "id": "1049b870-9115-42f0-bc65-bbeaad370d71",
                "user_id": "597c03a6-14e3-4dd2-aa9c-ec22e74271cf",
                "symbol": "BTC/USD",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "1.0",
                "price": "50000",
                "status": "OPEN",
            }
        )
    ]

    await process_orders(messages, session=mock_session, **mock_repos)

    # Assertions
    mock_repos["order_repo"].upsert_bulk.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_orders_db_failure(mock_session, mock_repos):
    messages = [
        MockMessage(
            {
                "id": "1049b870-9115-42f0-bc65-bbeaad370d71",
                "user_id": "597c03a6-14e3-4dd2-aa9c-ec22e74271cf",
                "symbol": "BTC/USD",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "1.0",
                "price": "50000",
                "status": "OPEN",
            }
        )
    ]

    mock_session.commit.side_effect = Exception("DB Connection Failed")

    with pytest.raises(Exception, match="DB Connection Failed"):
        await process_orders(messages, session=mock_session, topic="orders", **mock_repos)

    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_process_orders_update_success(mock_session, mock_repos):
    messages = [
        MockMessage(
            {
                "order_id": "1049b870-9115-42f0-bc65-bbeaad370d71",
                "status": "FILLED",
                "filled_quantity": 1.0,
            }
        )
    ]

    await process_orders(messages, session=mock_session, topic="order_updates", **mock_repos)

    mock_repos["order_repo"].update_status_bulk.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_balance_updates(mock_session, mock_repos):
    messages = [
        MockMessage(
            {
                "user_id": "user1",
                "currency": "USD",
                "available": "5000.0",
                "locked": "100.0"
            }
        )
    ]

    await process_orders(messages, session=mock_session, topic="balance_updates", **mock_repos)

    mock_repos["balance_repo"].upsert_bulk.assert_called_once()
    mock_session.commit.assert_called_once()

    args, _ = mock_repos["balance_repo"].upsert_bulk.call_args
    assert len(args[1]) == 1
    assert args[1][0]["user_id"] == "user1"
    assert args[1][0]["currency"] == "USD"
    assert args[1][0]["available"] == "5000.0"
    assert args[1][0]["locked"] == "100.0"


@pytest.mark.asyncio
async def test_process_orders_poison_pill(mock_session, mock_repos):
    """
    Test that invalid messages (poison pills) do not crash the batch processing,
    and valid messages are still processed.
    """
    messages = [
        MockMessage(raw_value=b"NOT VALID JSON"),  # JSONDecodeError
        MockMessage(
            {
                "id": "1049b870-9115-42f0-bc65-bbeaad370d71",
                "user_id": "597c03a6-14e3-4dd2-aa9c-ec22e74271cf",
                "symbol": "BTC/USD",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "1.0",
                "price": "50000",
                "status": "OPEN",
            }
        ),
        MockMessage(raw_value=b"\"justastring\"")  # TypeError/ValueError (not a dict)
    ]

    # Should not raise exception
    await process_orders(messages, session=mock_session, **mock_repos)
    
    # Assertions
    mock_repos["order_repo"].upsert_bulk.assert_called_once()
    # The batch should contain exactly one valid order
    args, _ = mock_repos["order_repo"].upsert_bulk.call_args
    assert len(args[1]) == 1
    assert args[1][0]["id"] == "1049b870-9115-42f0-bc65-bbeaad370d71"
    
    mock_session.commit.assert_called_once()
