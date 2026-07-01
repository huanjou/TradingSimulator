import pytest


@pytest.mark.asyncio
async def test_create_limit_order_success(client, user_factory):
    """Happy Path: Test creating a LIMIT order with a valid price."""
    user = await user_factory()
    payload = {
        "user_id": str(user.id),
        "symbol": "BTC/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 0.5,
        "price": 50000.00,
    }
    response = await client.post("/api/v1/orders/", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["order_type"] == "LIMIT"
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_create_market_order_success(client, user_factory):
    """Happy Path: Test creating a MARKET order without a price."""
    user = await user_factory()
    payload = {
        "user_id": str(user.id),
        "symbol": "ETH/USD",
        "side": "SELL",
        "order_type": "MARKET",
        "quantity": 2.0,
    }
    response = await client.post("/api/v1/orders/", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["order_type"] == "MARKET"
    assert data["price"] is None


@pytest.mark.parametrize(
    "invalid_payload_updates, expected_status",
    [
        ({"quantity": -1.0}, 422),  # Invalid quantity
        ({"quantity": 0}, 422),  # Zero quantity
        ({"side": "HOLD"}, 422),  # Invalid side enum
        ({"order_type": "UNKNOWN"}, 422),  # Invalid order type
        ({"price": -100.0}, 422),  # Invalid price
        ({"symbol": ""}, 422),  # Empty symbol
        ({"symbol": "BTCUSD"}, 422),  # Missing slash
        ({"symbol": "btc/usd"}, 422),  # Lowercase not allowed by regex
        ({"symbol": "BTC-USD"}, 422),  # Hyphen instead of slash
    ],
)
@pytest.mark.asyncio
async def test_create_order_schema_validation(
    client, user_factory, invalid_payload_updates, expected_status
):
    """Sad Path: Various payload schema validation failures (API Pydantic validation)."""
    user = await user_factory()
    payload = {
        "user_id": str(user.id),
        "symbol": "BTC/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 1.0,
        "price": 50000.0,
    }
    # Update payload with invalid data
    payload.update(invalid_payload_updates)

    response = await client.post("/api/v1/orders/", json=payload)
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_create_order_missing_fields(client):
    """Sad Path: Missing required fields (API Pydantic validation)."""
    payload = {
        "symbol": "BTC/USD"
        # Missing user_id, side, order_type, quantity
    }
    response = await client.post("/api/v1/orders/", json=payload)
    assert response.status_code == 422
    assert len(response.json()["detail"]) >= 4


@pytest.mark.asyncio
async def test_create_limit_order_without_price(client, user_factory):
    """Sad Path: Limit order without a price (Domain Invariant validation)."""
    user = await user_factory()
    payload = {
        "user_id": str(user.id),
        "symbol": "BTC/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 1.0,
        # Missing price
    }
    response = await client.post("/api/v1/orders/", json=payload)
    assert response.status_code == 400
    assert "Limit orders must have a specified price." in response.json()["detail"]


from unittest.mock import patch


@pytest.mark.asyncio
async def test_create_order_publishes_to_kafka(client, user_factory):
    """Happy Path: Ensure Kafka send_event is called with correct data."""
    user = await user_factory()
    payload = {
        "user_id": str(user.id),
        "symbol": "BTC/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 1.5,
        "price": 40000.00,
    }

    with patch("app.services.order.kafka_client.send_event") as mock_send_event:
        response = await client.post("/api/v1/orders/", json=payload)

        assert response.status_code == 202
        data = response.json()

        # Verify kafka was called exactly once
        mock_send_event.assert_called_once()

        # Extract arguments it was called with
        args, kwargs = mock_send_event.call_args

        assert kwargs["topic"] == "orders"

        kafka_payload = kwargs["value"]
        assert kafka_payload["id"] == data["id"]
        assert kafka_payload["user_id"] == str(user.id)
        assert kafka_payload["symbol"] == "BTC/USD"
        assert kafka_payload["side"] == "BUY"
        assert kafka_payload["type"] == "LIMIT"
        assert kafka_payload["quantity"] == 1.5
        assert kafka_payload["price"] == 40000.0
        assert kafka_payload["status"] == "PENDING"
