from dataclasses import dataclass
from decimal import Decimal


@dataclass
class WalletEntity:
    user_id: str
    currency: str
    available: Decimal
    locked: Decimal
