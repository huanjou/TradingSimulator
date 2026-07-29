"""Circuit breaker + mandatory durable mirror behaviour of SnapshotManager.

Two guarantees are covered here:
  * A dead Redis must never block the snapshot cycle, and must only be probed
    once per REDIS_RETRY_INTERVAL instead of on every cycle.
  * The durable Postgres mirror is mandatory: if it fails, save_snapshot raises
    so cold-start recovery guarantees are never silently degraded.
"""

from decimal import Decimal

import orjson
import pytest
import redis.exceptions
from app.domain.engine import MatchingEngine, WalletInfo
from app.services import snapshot_service
from app.services.snapshot_service import SnapshotManager

OFFSETS = {"orders": {"0": 100}}


class _FlakyRedis:
    """Minimal async Redis stub whose failure mode is switchable per test."""

    def __init__(self):
        self.fail = False
        self.set_calls = 0
        self.store: dict[str, bytes] = {}

    async def set(self, key, value):
        self.set_calls += 1
        if self.fail:
            raise redis.exceptions.ConnectionError("redis is down")
        self.store[key] = value


class _FakeDurableStore:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.saved: list[dict] = []

    async def save(self, snapshot: dict) -> None:
        if self.fail:
            raise RuntimeError("postgres is down")
        self.saved.append(snapshot)


class _FakeClock:
    """Controllable replacement for time.monotonic."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = _FakeClock()
    monkeypatch.setattr(snapshot_service.time, "monotonic", fake)
    return fake


@pytest.fixture
def flaky_redis():
    return _FlakyRedis()


@pytest.fixture
def engine():
    engine = MatchingEngine()
    engine.wallets["u1"] = {
        "USD": WalletInfo(available=Decimal("100"), locked=Decimal("0"))
    }
    engine.user_balance_versions["u1"] = 1
    return engine


def _manager(redis_client, monkeypatch, durable_store=None) -> SnapshotManager:
    """SnapshotManager with tenacity's backoff bypassed.

    The retry policy itself is asserted separately; here the interest is the
    circuit breaker around it, and real exponential sleeps would make these
    tests take seconds.
    """
    manager = SnapshotManager(redis_client, durable_store=durable_store)

    async def _direct_set(key, data):
        await redis_client.set(key, data)

    monkeypatch.setattr(manager, "_redis_set_with_retry", _direct_set)
    return manager


@pytest.mark.asyncio
async def test_redis_failure_does_not_raise(flaky_redis, engine, clock, monkeypatch):
    manager = _manager(flaky_redis, monkeypatch)
    flaky_redis.fail = True

    # A dead Redis must not propagate out of the snapshot cycle.
    await manager.save_snapshot(engine, OFFSETS)

    assert manager._redis_available is False


@pytest.mark.asyncio
async def test_open_circuit_skips_redis_within_retry_interval(
    flaky_redis, engine, clock, monkeypatch
):
    manager = _manager(flaky_redis, monkeypatch)
    flaky_redis.fail = True

    await manager.save_snapshot(engine, OFFSETS)
    assert flaky_redis.set_calls == 1

    # Subsequent cycles inside the interval must not touch Redis at all.
    clock.advance(SnapshotManager.REDIS_RETRY_INTERVAL / 3)
    await manager.save_snapshot(engine, OFFSETS)
    clock.advance(SnapshotManager.REDIS_RETRY_INTERVAL / 3)
    await manager.save_snapshot(engine, OFFSETS)

    assert flaky_redis.set_calls == 1


@pytest.mark.asyncio
async def test_open_circuit_probes_redis_after_retry_interval(
    flaky_redis, engine, clock, monkeypatch
):
    manager = _manager(flaky_redis, monkeypatch)
    flaky_redis.fail = True
    await manager.save_snapshot(engine, OFFSETS)
    assert flaky_redis.set_calls == 1

    clock.advance(SnapshotManager.REDIS_RETRY_INTERVAL + 1)
    await manager.save_snapshot(engine, OFFSETS)

    # Exactly one probe per interval, and the circuit stays open on failure.
    assert flaky_redis.set_calls == 2
    assert manager._redis_available is False


@pytest.mark.asyncio
async def test_circuit_closes_when_redis_recovers(
    flaky_redis, engine, clock, monkeypatch
):
    manager = _manager(flaky_redis, monkeypatch)
    flaky_redis.fail = True
    await manager.save_snapshot(engine, OFFSETS)

    flaky_redis.fail = False
    clock.advance(SnapshotManager.REDIS_RETRY_INTERVAL + 1)
    await manager.save_snapshot(engine, OFFSETS)

    assert manager._redis_available is True
    assert manager.snapshot_key in flaky_redis.store

    # Once closed, every cycle writes again without waiting for a probe window.
    await manager.save_snapshot(engine, OFFSETS)
    assert flaky_redis.set_calls == 3


@pytest.mark.asyncio
async def test_durable_mirror_written_while_redis_circuit_is_open(
    flaky_redis, engine, clock, monkeypatch
):
    durable = _FakeDurableStore()
    manager = _manager(flaky_redis, monkeypatch, durable_store=durable)
    flaky_redis.fail = True

    await manager.save_snapshot(engine, OFFSETS)
    clock.advance(1)
    await manager.save_snapshot(engine, OFFSETS)

    # Redis being down must not stop the durable snapshot: it is what keeps
    # cold-start recovery precise while the cache is unavailable.
    assert len(durable.saved) == 2
    assert durable.saved[0]["offsets"] == OFFSETS
    assert durable.saved[0]["balance_versions"] == {"u1": 1}


@pytest.mark.asyncio
async def test_durable_store_failure_is_fatal(flaky_redis, engine, clock, monkeypatch):
    durable = _FakeDurableStore(fail=True)
    manager = _manager(flaky_redis, monkeypatch, durable_store=durable)

    # The durable mirror is mandatory: its failure must surface to the caller.
    with pytest.raises(RuntimeError, match="postgres is down"):
        await manager.save_snapshot(engine, OFFSETS)

    # The Redis write still happened before the durable step failed.
    assert manager.snapshot_key in flaky_redis.store


@pytest.mark.asyncio
async def test_durable_store_failure_is_fatal_even_when_redis_is_down(
    flaky_redis, engine, clock, monkeypatch
):
    durable = _FakeDurableStore(fail=True)
    manager = _manager(flaky_redis, monkeypatch, durable_store=durable)
    flaky_redis.fail = True

    with pytest.raises(RuntimeError, match="postgres is down"):
        await manager.save_snapshot(engine, OFFSETS)


@pytest.mark.asyncio
async def test_redis_and_durable_store_receive_identical_snapshot(
    flaky_redis, engine, clock, monkeypatch
):
    durable = _FakeDurableStore()
    manager = _manager(flaky_redis, monkeypatch, durable_store=durable)

    await manager.save_snapshot(engine, OFFSETS)

    from_redis = orjson.loads(flaky_redis.store[manager.snapshot_key])
    assert from_redis == durable.saved[0]


@pytest.mark.asyncio
async def test_build_failure_skips_both_targets_without_raising(
    flaky_redis, clock, monkeypatch
):
    durable = _FakeDurableStore()
    manager = _manager(flaky_redis, monkeypatch, durable_store=durable)

    class _BrokenEngine:
        wallets: dict = {}
        user_balance_versions: dict = {}

        def get_all_pending_orders(self):
            raise ValueError("engine state is unreadable")

    # A snapshot that cannot even be built is logged and skipped; writing a
    # partial snapshot would be worse than writing none.
    await manager.save_snapshot(_BrokenEngine(), OFFSETS)

    assert flaky_redis.set_calls == 0
    assert durable.saved == []


@pytest.mark.asyncio
async def test_offsets_are_deep_copied_into_the_snapshot(
    flaky_redis, engine, clock, monkeypatch
):
    durable = _FakeDurableStore()
    manager = _manager(flaky_redis, monkeypatch, durable_store=durable)
    live_offsets = {"orders": {"0": 100}}

    await manager.save_snapshot(engine, live_offsets)
    # The consumer keeps advancing its offsets after the snapshot was taken.
    live_offsets["orders"]["0"] = 999

    # The persisted pair (state, offsets) must stay the point-in-time one, or
    # replaying from it would skip events.
    assert durable.saved[0]["offsets"] == {"orders": {"0": 100}}


@pytest.mark.asyncio
async def test_transient_redis_errors_are_retried_before_opening_circuit(
    flaky_redis, engine, monkeypatch
):
    # Here the real tenacity-wrapped method is used, with the backoff removed
    # so the 3-attempt policy can be asserted quickly.
    monkeypatch.setattr(snapshot_service.asyncio, "sleep", _noop_sleep)
    manager = SnapshotManager(flaky_redis)
    flaky_redis.fail = True

    await manager.save_snapshot(engine, OFFSETS)

    # 3 attempts within a single cycle, then the circuit opens.
    assert flaky_redis.set_calls == 3
    assert manager._redis_available is False


async def _noop_sleep(_seconds):
    return None
