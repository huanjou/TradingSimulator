import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest


@pytest.mark.asyncio
async def test_get_order_success(auth_client):
    """Happy Path: Test getting an order by ID successfully."""
    client, user = auth_client
    order_id = str(uuid.uuid4())

    mock_response = MagicMock()
    mock_response.id = order_id
    mock_response.user_id = str(user.id)
    mock_response.symbol = "BTC/USD"
    mock_response.side = "BUY"
    mock_response.order_type = "LIMIT"
    mock_response.quantity = 1.0
    mock_response.price = 50000.0
    mock_response.status = "PENDING"

    with patch(
        "app.services.order_query.orders_pb2_grpc.OrderQueryServiceStub"
    ) as mock_stub_class:
        mock_stub = mock_stub_class.return_value
        mock_stub.GetOrder = AsyncMock(return_value=mock_response)

        response = await client.get(f"/api/v1/orders/{order_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id
        assert data["symbol"] == "BTC/USD"


@pytest.mark.asyncio
async def test_get_order_not_found(auth_client):
    """Sad Path: Test getting a non-existent order."""
    client, user = auth_client
    order_id = str(uuid.uuid4())

    with patch(
        "app.services.order_query.orders_pb2_grpc.OrderQueryServiceStub"
    ) as mock_stub_class:
        mock_stub = mock_stub_class.return_value

        # Simulate gRPC NOT_FOUND error
        mock_error = grpc.aio.AioRpcError(
            code=grpc.StatusCode.NOT_FOUND,
            initial_metadata=None,
            trailing_metadata=None,
            details="Order not found",
            debug_error_string="",
        )
        # Mocking the code() method return value
        mock_error.code = lambda: grpc.StatusCode.NOT_FOUND

        mock_stub.GetOrder = AsyncMock(side_effect=mock_error)

        response = await client.get(f"/api/v1/orders/{order_id}")

        assert response.status_code == 404
        assert "Order not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_order_forbidden(auth_client):
    """Sad Path: Test getting an order owned by another user."""
    client, user = auth_client
    order_id = str(uuid.uuid4())

    mock_response = MagicMock()
    mock_response.id = order_id
    mock_response.user_id = str(uuid.uuid4())  # Different user ID

    with patch(
        "app.services.order_query.orders_pb2_grpc.OrderQueryServiceStub"
    ) as mock_stub_class:
        mock_stub = mock_stub_class.return_value
        mock_stub.GetOrder = AsyncMock(return_value=mock_response)

        response = await client.get(f"/api/v1/orders/{order_id}")

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_orders_by_user_success(auth_client):
    """Happy Path: Test getting orders for the current user."""
    client, user = auth_client

    mock_order = MagicMock()
    mock_order.id = str(uuid.uuid4())
    mock_order.user_id = str(user.id)
    mock_order.symbol = "ETH/USD"
    mock_order.status = "FILLED"

    mock_response = MagicMock()
    mock_response.orders = [mock_order]

    with patch(
        "app.services.order_query.orders_pb2_grpc.OrderQueryServiceStub"
    ) as mock_stub_class:
        mock_stub = mock_stub_class.return_value
        mock_stub.GetOrdersByUser = AsyncMock(return_value=mock_response)

        response = await client.get("/api/v1/orders/user/me?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "ETH/USD"


@pytest.mark.asyncio
async def test_get_orders_service_unavailable(auth_client):
    """Sad Path: Test gRPC connection failure."""
    client, user = auth_client

    with patch(
        "app.services.order_query.orders_pb2_grpc.OrderQueryServiceStub"
    ) as mock_stub_class:
        mock_stub = mock_stub_class.return_value

        mock_error = grpc.aio.AioRpcError(
            code=grpc.StatusCode.UNAVAILABLE,
            initial_metadata=None,
            trailing_metadata=None,
            details="Service unavailable",
            debug_error_string="",
        )
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE

        mock_stub.GetOrdersByUser = AsyncMock(side_effect=mock_error)

        response = await client.get("/api/v1/orders/user/me")

        assert response.status_code == 503
        assert "Query service unavailable" in response.json()["detail"]
