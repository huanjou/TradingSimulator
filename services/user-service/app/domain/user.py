from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class User:
    id: UUID
    email: str
    hashed_password: str
    is_active: bool
    is_superuser: bool
    token_version: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
