from pydantic import BaseModel


class SymbolCreateRequest(BaseModel):
    symbol: str


class SymbolCreateResponse(BaseModel):
    status: str
    message: str
