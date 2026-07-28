import structlog
from app.core.config import get_settings
from fastapi import WebSocket, WebSocketException, status
from jose import JWTError, jwt

logger = structlog.get_logger()
settings = get_settings()


def get_user_id_from_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_user_id_ws(websocket: WebSocket) -> str:
    """
    Extracts the user ID from the JWT token present in the HTTP-only cookie.

    The token is read ONLY from the cookie. Passing tokens via query string is
    rejected because query parameters leak into access logs, proxy logs and
    browser history.
    """
    token = websocket.cookies.get("access_token")

    user_id = get_user_id_from_token(token) if token else None

    if not user_id:
        logger.warning("ws_auth_failed", has_cookie_token=bool(token))
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )

    return user_id
