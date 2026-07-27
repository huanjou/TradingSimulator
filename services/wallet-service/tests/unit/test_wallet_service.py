import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.wallet_service import WalletService

@pytest.fixture
def mock_publisher():
    return AsyncMock()

@pytest.fixture
def service(mock_publisher):
    svc = WalletService()
    svc.publisher = mock_publisher
    svc.commands_topic = "wallet_commands"
    return svc

@pytest.mark.asyncio
async def test_deposit(service, mock_publisher):
    await service.deposit("user1", "USD", 500.0)
    
    mock_publisher.publish.assert_called_once()
    args, kwargs = mock_publisher.publish.call_args
    assert args[0] == "wallet_commands"
    
    payload = json.loads(args[1])
    assert payload["user_id"] == "user1"
    assert payload["type"] == "DEPOSIT"
    assert payload["currency"] == "USD"
    assert payload["amount"] == 500.0
    
    # check key
    assert kwargs["key"] == b"user1"
