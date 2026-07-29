"""JWT authentication on the query-service gRPC surface.

The gRPC port is reachable from other services, so it must not be an
unauthenticated back door around the REST auth: every RPC has to present a
valid token, and the decoded payload is what the servicers use for ownership
and admin checks.
"""

from datetime import UTC, datetime, timedelta

import grpc
import pytest
from app.core.config import get_settings
from app.grpc_server import JwtAuthInterceptor, get_authenticated_user
from jose import jwt

settings = get_settings()
METHOD = "/orders.OrderQueryService/GetOrder"


def _token(sub="user-1", role=None, expires_in_minutes=15, secret=None) -> str:
    payload = {
        "sub": sub,
        "exp": datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
    }
    if role:
        payload["role"] = role
    if sub is None:
        payload.pop("sub")
    return jwt.encode(
        payload,
        secret or settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


class _HandlerCallDetails:
    def __init__(self, metadata: dict | None):
        self.invocation_metadata = tuple((metadata or {}).items())
        self.method = METHOD


class _FakeContext:
    """Captures the abort a rejected RPC is expected to trigger."""

    def __init__(self):
        self.aborted_with = None

    async def abort(self, code, details):
        self.aborted_with = (code, details)
        raise grpc.RpcError(details)


def _continuation(behavior):
    async def _continue(handler_call_details):
        return grpc.unary_unary_rpc_method_handler(behavior)

    return _continue


async def _echo_auth(request, context):
    """Servicer stand-in that reports what the interceptor bound for this RPC."""
    return get_authenticated_user()


async def _intercept(metadata: dict | None, behavior=_echo_auth):
    interceptor = JwtAuthInterceptor()
    return await interceptor.intercept_service(
        _continuation(behavior), _HandlerCallDetails(metadata)
    )


async def test_valid_token_binds_user_to_the_rpc():
    handler = await _intercept({"authorization": f"Bearer {_token(sub='user-7')}"})

    user_id, is_admin = await handler.unary_unary(object(), _FakeContext())

    assert user_id == "user-7"
    assert is_admin is False


async def test_admin_role_is_exposed_to_the_servicer():
    handler = await _intercept(
        {"authorization": f"Bearer {_token(sub='admin-1', role='admin')}"}
    )

    user_id, is_admin = await handler.unary_unary(object(), _FakeContext())

    assert user_id == "admin-1"
    assert is_admin is True


async def test_non_admin_role_is_not_treated_as_admin():
    handler = await _intercept({"authorization": f"Bearer {_token(role='superuser')}"})

    _, is_admin = await handler.unary_unary(object(), _FakeContext())

    assert is_admin is False


async def test_bare_token_without_bearer_prefix_is_accepted():
    handler = await _intercept({"authorization": _token(sub="user-9")})

    user_id, _ = await handler.unary_unary(object(), _FakeContext())

    assert user_id == "user-9"


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"authorization": ""},
        {"authorization": "Bearer "},
        {"other-header": "value"},
    ],
    ids=["no-metadata", "empty", "empty-value", "bearer-only", "wrong-header"],
)
async def test_missing_token_is_rejected(metadata):
    handler = await _intercept(metadata)
    context = _FakeContext()

    with pytest.raises(grpc.RpcError):
        await handler.unary_unary(object(), context)

    assert context.aborted_with[0] == grpc.StatusCode.UNAUTHENTICATED


async def test_malformed_token_is_rejected():
    handler = await _intercept({"authorization": "Bearer not-a-jwt"})
    context = _FakeContext()

    with pytest.raises(grpc.RpcError):
        await handler.unary_unary(object(), context)

    assert context.aborted_with[0] == grpc.StatusCode.UNAUTHENTICATED


async def test_token_signed_with_another_secret_is_rejected():
    forged = _token(sub="attacker", secret="a_completely_different_secret")
    handler = await _intercept({"authorization": f"Bearer {forged}"})
    context = _FakeContext()

    with pytest.raises(grpc.RpcError):
        await handler.unary_unary(object(), context)

    assert context.aborted_with[0] == grpc.StatusCode.UNAUTHENTICATED


async def test_expired_token_is_rejected():
    handler = await _intercept(
        {"authorization": f"Bearer {_token(expires_in_minutes=-5)}"}
    )
    context = _FakeContext()

    with pytest.raises(grpc.RpcError):
        await handler.unary_unary(object(), context)

    assert context.aborted_with[0] == grpc.StatusCode.UNAUTHENTICATED


async def test_token_without_subject_is_rejected():
    # Without "sub" there is no user to authorize against, so the RPC must not
    # fall through to the servicer with an empty identity.
    handler = await _intercept({"authorization": f"Bearer {_token(sub=None)}"})
    context = _FakeContext()

    with pytest.raises(grpc.RpcError):
        await handler.unary_unary(object(), context)

    assert context.aborted_with[0] == grpc.StatusCode.UNAUTHENTICATED


async def test_rejected_rpc_never_reaches_the_servicer():
    called = {"yes": False}

    async def behavior(request, context):
        called["yes"] = True

    handler = await _intercept({"authorization": "Bearer bad"}, behavior=behavior)
    with pytest.raises(grpc.RpcError):
        await handler.unary_unary(object(), _FakeContext())

    assert called["yes"] is False


async def test_auth_payload_is_reset_after_the_rpc():
    handler = await _intercept({"authorization": f"Bearer {_token(sub='user-3')}"})
    await handler.unary_unary(object(), _FakeContext())

    # Leaking the payload into the next RPC would authorize it as this user.
    assert get_authenticated_user() == ("", False)


async def test_auth_payload_is_reset_even_when_the_servicer_raises():
    async def failing_behavior(request, context):
        raise RuntimeError("servicer blew up")

    handler = await _intercept(
        {"authorization": f"Bearer {_token(sub='user-4')}"},
        behavior=failing_behavior,
    )

    with pytest.raises(RuntimeError, match="servicer blew up"):
        await handler.unary_unary(object(), _FakeContext())

    assert get_authenticated_user() == ("", False)


async def test_unauthenticated_user_defaults_are_not_admin():
    # Outside any intercepted RPC there is no identity at all.
    assert get_authenticated_user() == ("", False)


async def test_serializers_are_preserved_on_the_wrapped_handler():
    def _deserializer(data):
        return data

    def _serializer(obj):
        return obj

    async def _continue(handler_call_details):
        return grpc.unary_unary_rpc_method_handler(
            _echo_auth,
            request_deserializer=_deserializer,
            response_serializer=_serializer,
        )

    handler = await JwtAuthInterceptor().intercept_service(
        _continue, _HandlerCallDetails({"authorization": f"Bearer {_token()}"})
    )

    # Wrapping must not drop the codec, or every message would fail to parse.
    assert handler.request_deserializer is _deserializer
    assert handler.response_serializer is _serializer


async def test_non_unary_handler_is_passed_through_unchanged():
    async def _continue(handler_call_details):
        return None

    handler = await JwtAuthInterceptor().intercept_service(
        _continue, _HandlerCallDetails({"authorization": f"Bearer {_token()}"})
    )

    assert handler is None
