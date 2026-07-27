from unittest.mock import AsyncMock

import pytest
from app.repositories.wallet_repository import WalletRepository


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    return mock


@pytest.fixture
def repo(mock_redis):
    return WalletRepository(redis=mock_redis)


@pytest.mark.asyncio
async def test_get_wallets_by_user_empty(repo, mock_redis):
    mock_redis.hgetall.return_value = {}
    wallets = await repo.get_wallet_balances("user1")
    assert wallets == []


@pytest.mark.asyncio
async def test_get_wallets_by_user_with_data(repo, mock_redis):
    mock_redis.hgetall.return_value = {
        "USD": '{"currency": "USD", "available": 1000.0, "locked": 50.0}',
        "BTC": '{"currency": "BTC", "available": 2.5, "locked": 0.0}',
    }
    wallets = await repo.get_wallet_balances("user1")

    assert len(wallets) == 2

    usd_wallet = next(w for w in wallets if w.currency == "USD")
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

    val = json.loads(args[2].decode("utf-8") if isinstance(args[2], bytes) else args[2])
    assert val["available"] == "1500.0"
    assert val["locked"] == "100.0"


@pytest.mark.asyncio
async def test_repository_corrupted_json_in_redis():
    """QA Resilience: При битом JSON в Redis возвращаются остальные балансы."""
    from unittest.mock import patch

    mock_redis = AsyncMock()
    mock_redis.hgetall.return_value = {
        "USD": '{"currency": "USD", "available": 100.0, "locked": 10.0}',
        "CORRUPTED_CURRENCY": "{broken_json_without_closing_bracket",
        "EUR": '{"currency": "EUR", "available": 50.0, "locked": 0.0}',
    }
    repo = WalletRepository(redis=mock_redis)

    with patch("app.repositories.wallet_repository.logger.error") as mock_logger:
        wallets = await repo.get_wallet_balances("user_resilient")

        assert len(wallets) == 2
        currencies = [w.currency for w in wallets]
        assert "USD" in currencies and "EUR" in currencies
        assert "CORRUPTED_CURRENCY" not in currencies

        mock_logger.assert_called_once()
        assert "CORRUPTED_CURRENCY" in mock_logger.call_args[0]


@pytest.mark.asyncio
async def test_repository_missing_balance_fields_in_redis():
    """QA Resilience: При отсутствии полей в JSON подставляются дефолтные 0."""
    from decimal import Decimal

    mock_redis = AsyncMock()
    mock_redis.hgetall.return_value = {"TEST_CURRENCY": '{"currency": "TEST_CURRENCY"}'}
    repo = WalletRepository(redis=mock_redis)
    wallets = await repo.get_wallet_balances("user1")
    assert len(wallets) == 1
    assert wallets[0].available == Decimal("0")
    assert wallets[0].locked == Decimal("0")
