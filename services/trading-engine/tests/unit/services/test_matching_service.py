from decimal import Decimal

import pytest
from app.domain.engine import MatchingEngine
from app.services.matching_service import MatchingService


class FakePublisher:
    def __init__(self):
        self.published: list[tuple[str, bytes, bytes | None]] = []

    async def publish(self, topic: str, message: bytes, key: bytes | None = None):
        self.published.append((topic, message, key))


@pytest.fixture
def engine():
    return MatchingEngine()


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def service(engine, publisher):
    return MatchingService(
        engine=engine,
        publisher=publisher,
        trades_topic="trades",
        updates_topic="order_updates",
        balance_updates_topic="balance_updates",
    )


def _deposit_cmd(user_id: str, amount: str, version: int | None) -> dict:
    cmd = {
        "type": "DEPOSIT",
        "user_id": user_id,
        "currency": "USD",
        "amount": amount,
    }
    if version is not None:
        cmd["balance_version"] = version
    return cmd


def _order(user_id: str, order_id: str, depends_on: int | None = None) -> dict:
    data = {
        "id": order_id,
        "user_id": user_id,
        "symbol": "BTC/USD",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": "1",
        "price": "100",
    }
    if depends_on is not None:
        data["depends_on_balance_version"] = depends_on
    return data


@pytest.mark.asyncio
async def test_deposit_updates_balance_version(service, engine):
    await service.handle_wallet_commands_batch([_deposit_cmd("u1", "1000", 3)])

    assert engine.user_balance_versions["u1"] == 3
    assert engine.wallets["u1"]["USD"].available == Decimal("1000")


@pytest.mark.asyncio
async def test_stale_balance_version_is_not_applied(service, engine):
    await service.handle_wallet_commands_batch([_deposit_cmd("u1", "1000", 5)])
    # A replayed/older command must not move the version backwards.
    await service.handle_wallet_commands_batch([_deposit_cmd("u1", "10", 2)])

    assert engine.user_balance_versions["u1"] == 5


@pytest.mark.asyncio
async def test_order_without_dependency_is_processed_immediately(service, engine):
    # Backward compatible: no depends_on_balance_version -> no deferral,
    # so the unfunded order is rejected as before.
    await service.handle_orders_batch([_order("u1", "o1")])

    assert service._deferred_orders == []
    assert engine.user_balance_versions == {}


@pytest.mark.asyncio
async def test_order_deferred_until_deposit_arrives(service, engine, publisher):
    # Order depends on a deposit the engine has not seen yet.
    await service.handle_orders_batch([_order("u1", "o1", depends_on=1)])

    assert len(service._deferred_orders) == 1
    assert publisher.published == []  # no REJECTED update was published

    # The funding deposit arrives -> the deferred order is processed and the
    # 100 USD limit BUY locks funds instead of being rejected.
    await service.handle_wallet_commands_batch([_deposit_cmd("u1", "1000", 1)])

    assert service._deferred_orders == []
    assert engine.wallets["u1"]["USD"].locked == Decimal("100")
    assert engine.wallets["u1"]["USD"].available == Decimal("900")


@pytest.mark.asyncio
async def test_deferred_order_retried_on_next_orders_batch(service, engine):
    await service.handle_orders_batch([_order("u1", "o1", depends_on=1)])
    assert len(service._deferred_orders) == 1

    # Deposit is applied without triggering the deferred flush directly.
    engine.process_deposit("u1", "USD", Decimal("1000"))
    engine.user_balance_versions["u1"] = 1

    # The next orders batch re-checks deferred orders first.
    await service.handle_orders_batch([])
    assert service._deferred_orders == []
    assert engine.wallets["u1"]["USD"].locked == Decimal("100")


@pytest.mark.asyncio
async def test_defer_attempts_exhausted_processes_normally(service, engine):
    await service.handle_orders_batch([_order("u1", "o1", depends_on=99)])

    # Retried on each batch until MAX_DEFER_ATTEMPTS is reached.
    for _ in range(MatchingService.MAX_DEFER_ATTEMPTS - 1):
        await service.handle_orders_batch([])
        assert len(service._deferred_orders) == 1

    # Attempts exhausted -> processed normally (rejected: still unfunded).
    await service.handle_orders_batch([])
    assert service._deferred_orders == []
