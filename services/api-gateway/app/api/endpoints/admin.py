from app.api.deps import get_admin_service, get_current_admin_user
from app.core.config import get_settings
from app.schemas.admin import SymbolCreateRequest, SymbolCreateResponse
from app.services.admin import AdminService
from fastapi import APIRouter, Depends, status

router = APIRouter()
settings = get_settings()


@router.post(
    "/symbols",
    response_model=SymbolCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_symbol(
    request: SymbolCreateRequest,
    admin_service: AdminService = Depends(get_admin_service),
    current_admin_id: str = Depends(get_current_admin_user),
):
    await admin_service.create_symbol(request.symbol)
    return SymbolCreateResponse(
        status="success",
        message=f"Symbol {request.symbol} creation event published",
    )
