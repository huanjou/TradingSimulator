from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


# Shared properties
class UserBase(BaseModel):
    email: EmailStr


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str


# Properties to receive via API on login
class UserLogin(UserBase):
    password: str


# Properties to return to client
class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str | None = None
