from decimal import Decimal

import pytest
from app.domain.wallet import WalletEntity


def test_wallet_entity_valid():
    entity = WalletEntity(
        user_id="user1", currency="USD", available=Decimal("100"), locked=Decimal("20")
    )
    assert entity.user_id == "user1"
    assert entity.currency == "USD"
    assert entity.available == Decimal("100")
    assert entity.locked == Decimal("20")


def test_wallet_entity_empty_user_id():
    with pytest.raises(ValueError) as exc_info:
        WalletEntity(
            user_id="", currency="USD", available=Decimal("10"), locked=Decimal("0")
        )
    assert "user_id must be a non-empty string" in str(exc_info.value)


def test_wallet_entity_empty_currency():
    with pytest.raises(ValueError) as exc_info:
        WalletEntity(
            user_id="user1", currency="", available=Decimal("10"), locked=Decimal("0")
        )
    assert "currency must be a non-empty string" in str(exc_info.value)


def test_wallet_entity_negative_available():
    with pytest.raises(ValueError) as exc_info:
        WalletEntity(
            user_id="user1",
            currency="USD",
            available=Decimal("-5"),
            locked=Decimal("0"),
        )
    assert "available balance cannot be negative" in str(exc_info.value)


def test_wallet_entity_negative_locked():
    with pytest.raises(ValueError) as exc_info:
        WalletEntity(
            user_id="user1",
            currency="USD",
            available=Decimal("10"),
            locked=Decimal("-10"),
        )
    assert "locked balance cannot be negative" in str(exc_info.value)


def test_wallet_entity_invalid_decimal():
    with pytest.raises(ValueError) as exc_info:
        WalletEntity(
            user_id="user1", currency="USD", available="invalid", locked=Decimal("0")
        )
    assert "Invalid available balance" in str(exc_info.value)
