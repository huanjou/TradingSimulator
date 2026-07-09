from pydantic import BaseModel


class UserEntity(BaseModel):
    id: str
    email: str
    hashed_password: str
