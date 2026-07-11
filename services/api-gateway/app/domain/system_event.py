import enum
import uuid

from pydantic import BaseModel, Field


class SystemEventType(str, enum.Enum):
    SYMBOL_CREATED = "SYMBOL_CREATED"


class SystemEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: SystemEventType
    symbol: str
