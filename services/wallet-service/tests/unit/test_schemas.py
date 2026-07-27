from decimal import Decimal

import pytest
from app.schemas.wallet import DepositRequest, WalletBalance
from pydantic import ValidationError


def test_deposit_request_valid():
    req = DepositRequest(currency="usd ", amount=Decimal("100.50"))
    assert req.currency == "USD"
    assert req.amount == Decimal("100.50")


def test_deposit_request_zero_amount():
    with pytest.raises(ValidationError) as exc_info:
        DepositRequest(currency="USD", amount=Decimal("0.00"))
    assert "greater than 0" in str(exc_info.value)


def test_deposit_request_negative_amount():
    with pytest.raises(ValidationError) as exc_info:
        DepositRequest(currency="USD", amount=Decimal("-50.00"))
    assert "greater than 0" in str(exc_info.value)


def test_deposit_request_invalid_currency():
    with pytest.raises(ValidationError):
        DepositRequest(currency="", amount=Decimal("10.00"))


def test_wallet_balance_valid():
    wb = WalletBalance(currency="BTC", available="1.5", locked="0.2")
    assert wb.currency == "BTC"
    assert wb.available == "1.5"
    assert wb.locked == "0.2"


def test_wallet_balance_negative():
    with pytest.raises(ValidationError) as exc_info:
        WalletBalance(currency="BTC", available="-1.0", locked="0.0")
    assert "balance cannot be negative" in str(exc_info.value)


def test_wallet_balance_invalid_decimal_str():
    with pytest.raises(ValidationError) as exc_info:
        WalletBalance(currency="BTC", available="not_a_number", locked="0.0")
    assert "invalid balance string" in str(exc_info.value)
