from dataclasses import dataclass
from decimal import Decimal


@dataclass
class WalletEntity:
    user_id: str
    currency: str
    available: Decimal
    locked: Decimal

    def __post_init__(self):
        if (
            not self.user_id
            or not isinstance(self.user_id, str)
            or not self.user_id.strip()
        ):
            raise ValueError("WalletEntity user_id must be a non-empty string")
        if (
            not self.currency
            or not isinstance(self.currency, str)
            or not self.currency.strip()
        ):
            raise ValueError("WalletEntity currency must be a non-empty string")

        try:
            self.available = Decimal(str(self.available))
        except Exception as e:
            raise ValueError(f"Invalid available balance: {self.available}") from e

        try:
            self.locked = Decimal(str(self.locked))
        except Exception as e:
            raise ValueError(f"Invalid locked balance: {self.locked}") from e

        if self.available < Decimal("0"):
            raise ValueError("WalletEntity available balance cannot be negative")
        if self.locked < Decimal("0"):
            raise ValueError("WalletEntity locked balance cannot be negative")
