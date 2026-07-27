import pytest
from unittest.mock import AsyncMock, patch
from app.repositories.wallet_repository import WalletRepository
from app.schemas.wallet import Wallet

@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    return mock

@pytest.fixture
def repo(mock_redis):
    return WalletRepository(redis_client=mock_redis)

@pytest.mark.asyncio
async def test_get_wallets_by_user_empty(repo, mock_redis):
    mock_redis.hgetall.return_value = {}
    wallets = await repo.get_wallets_by_user("user1")
    assert wallets == {}

@pytest.mark.asyncio
async def test_get_wallets_by_user_with_data(repo, mock_redis):
    mock_redis.hgetall.return_value = {
        b"USD": b'{"currency": "USD", "available": 1000.0, "locked": 50.0}',
        b"BTC": b'{"currency": "BTC", "available": 2.5, "locked": 0.0}',
    }
    wallets = await repo.get_wallets_by_user("user1")
    
    assert len(wallets) == 2
    assert "USD" in wallets
    assert "BTC" in wallets
    
    usd_wallet = wallets["USD"]
    assert usd_wallet.currency == "USD"
    assert usd_wallet.available == 1000.0
    assert usd_wallet.locked == 50.0

@pytest.mark.asyncio
async def test_update_wallet_balance(repo, mock_redis):
    await repo.update_wallet_balance("user1", "USD", "1500.0", "100.0")
    
    mock_redis.hset.assert_called_once()
    args, kwargs = mock_redis.hset.call_args
    assert args[0] == "wallet:user1"
    assert args[1] == "USD"
    # value is JSON
    import json
    val = json.loads(args[2])
    assert val["currency"] == "USD"
    assert val["available"] == 1500.0
    assert val["locked"] == 100.0
