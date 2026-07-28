from app.core.config import get_settings
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

settings = get_settings()


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT, returning its payload.
    Raises jose.JWTError if the token is invalid or expired.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def _extract_token(request: Request) -> str | None:
    # 1. Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]

    # 2. Check Cookie
    return request.cookies.get("access_token")


def get_token_payload(request: Request) -> dict:
    """
    Extracts the JWT from the Authorization header or HTTP-Only cookie and
    returns its decoded payload.
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_token(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from e

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return payload


def get_current_user(request: Request) -> str:
    """
    Extracts the authenticated user ID from the JWT token present in the
    Authorization header or HTTP-Only cookie.
    """
    return get_token_payload(request)["sub"]


def get_current_admin_user(request: Request) -> str:
    """
    Extracts the user ID and verifies that the user has an ADMIN role.
    """
    payload = get_token_payload(request)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return payload["sub"]
