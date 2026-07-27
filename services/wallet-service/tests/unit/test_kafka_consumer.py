import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_wallet_repo():
    return AsyncMock()

@pytest.fixture
def mock_consumer():
    with patch("app.services.kafka_consumer.AIOKafkaConsumer") as mock:
        yield mock

@pytest.mark.asyncio
async def test_consume_balance_updates(mock_wallet_repo, mock_consumer):
    from app.services.kafka_consumer import WalletKafkaConsumer
    
    # create a mock message
    msg = MagicMock()
    msg.value = json.dumps({
        "user_id": "user1",
        "currency": "USD",
        "available": "2000.0",
        "locked": "100.0"
    }).encode("utf-8")
    
    # mock async generator
    async def mock_aiter():
        yield msg

    consumer_instance = AsyncMock()
    consumer_instance.__aiter__.side_effect = lambda: mock_aiter()
    mock_consumer.return_value = consumer_instance
    
    consumer = WalletKafkaConsumer()
    consumer.wallet_repo = mock_wallet_repo
    
    # We need to manually call _consume and cancel it to prevent infinite loop if it doesn't break
    # Actually the generator only yields one message and stops, but `async for` will naturally stop.
    await consumer._consume()
    
    mock_wallet_repo.update_wallet_balance.assert_called_once_with(
        user_id="user1",
        currency="USD",
        available="2000.0",
        locked="100.0"
    )
