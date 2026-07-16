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
