from app.core.config import get_settings
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

settings = get_settings()


def get_current_user_id(request: Request) -> str:
    """
    Extracts the user ID from the JWT token present in the Authorization
    header or HTTP-Only cookie.
    Validates CSRF token if the authentication was done via Cookie.
    """
    token: str | None = None
    is_cookie = False

    # 1. Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    # 2. Check Cookie
    if not token:
        token = request.cookies.get("access_token")
        is_cookie = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # 3. Validate CSRF for modifying requests if token came from cookie
    if is_cookie and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or incorrect",
            )

    # 4. Verify JWT
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        # Refresh tokens (type="refresh") must never be accepted as access
        # tokens. Legacy access tokens carry no "type" claim and still pass.
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from e


def get_request_token(request: Request) -> str:
    """
    Extracts the raw JWT from the Authorization header or HTTP-Only cookie so
    it can be forwarded to internal services (e.g. query-service via gRPC
    metadata). Validation is performed by get_current_user_id and again by the
    downstream service.
    """
    token: str | None = None

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return token


def get_current_admin_user(request: Request) -> str:
    """
    Extracts the user ID and verifies that the user has an ADMIN role.
    """
    # Reuse extraction logic (this requires token to be available, but we can
    # just duplicate or refactor later). Actually, simpler to just get token
    # directly here since the logic is small, or just call get_current_user_id
    # to validate CSRF first.
    user_id = get_current_user_id(request)

    # We need the token again to check role
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    else:
        token = request.cookies.get("access_token")

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return user_id
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from e


def get_admin_service():
    from app.core.kafka import kafka_client
    from app.services.admin import AdminService

    return AdminService(kafka_client)
