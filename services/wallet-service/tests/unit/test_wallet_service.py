from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.wallet import DepositRequest
from app.services.wallet_service import WalletService


@pytest.fixture
def mock_repository():
    repo = AsyncMock()
    repo.next_balance_version.return_value = 1
    return repo


@pytest.fixture
def service(mock_repository):
    return WalletService(repository=mock_repository)


@pytest.mark.asyncio
@patch("app.services.wallet_service.kafka_client")
async def test_deposit(mock_kafka_client, mock_repository, service):
    mock_kafka_client.send_command = AsyncMock()
    mock_repository.next_balance_version.return_value = 7
    req = DepositRequest(currency="USD", amount=500.0)
    res = await service.process_deposit("user1", req)

    mock_kafka_client.send_command.assert_called_once()
    kwargs = mock_kafka_client.send_command.call_args.kwargs
    assert kwargs["topic"] == "wallet_commands"

    payload = kwargs["value"]
    assert payload["user_id"] == "user1"
    assert payload["type"] == "DEPOSIT"
    assert payload["currency"] == "USD"
    assert payload["amount"] == "500.0"
    # The per-user monotonic version is attached for causal ordering.
    assert payload["balance_version"] == 7
    assert res.balance_version == 7

    # check key
    assert kwargs["key"] == b"user1"


@pytest.mark.asyncio
async def test_get_my_wallets(mock_repository, service):
    from decimal import Decimal

    from app.domain.wallet import WalletEntity

    mock_repository.get_wallet_balances.return_value = [
        WalletEntity(
            user_id="user1",
            currency="USD",
            available=Decimal("1500.5"),
            locked=Decimal("50.0"),
        )
    ]
    res = await service.get_my_wallets("user1")
    assert len(res.balances) == 1
    assert res.balances[0].currency == "USD"
    assert res.balances[0].available == "1500.5"
    assert res.balances[0].locked == "50.0"


@pytest.mark.asyncio
@patch("app.services.wallet_service.kafka_client")
async def test_deposit_extreme_precision_and_large_numbers(mock_kafka_client, service):
    """QA Boundary: Работа с огромными числами и высокой точностью."""
    from decimal import Decimal

    mock_kafka_client.send_command = AsyncMock()

    huge_amount = Decimal("9999999999999999999999999999.1234567890123456789")
    req = DepositRequest(currency="BTC", amount=huge_amount)

    res = await service.process_deposit("user_crypto", req)
    assert res.status == "success"

    kwargs = mock_kafka_client.send_command.call_args.kwargs
    assert kwargs["value"]["amount"] == str(huge_amount)
