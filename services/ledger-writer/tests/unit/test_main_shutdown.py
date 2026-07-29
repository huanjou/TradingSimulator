"""Graceful shutdown of the ledger-writer worker.

On SIGTERM the in-flight batch must be allowed to finish and commit its
offsets before the process exits, otherwise a redeploy replays (or loses)
whatever was mid-flight. The drain is bounded, so a stuck consumer cannot
block the shutdown forever.
"""

import asyncio

import main as main_module
import pytest


class _FakeHealthServer:
    def __init__(self, checks_fn, port=0):
        self.checks_fn = checks_fn
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class _FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


@pytest.fixture
def harness(monkeypatch):
    """Wires main() to fakes and exposes the captured shutdown event."""
    state = {"event": None, "health": None, "engine": _FakeEngine()}

    def _capture_event(shutdown_event):
        # Stand in for install_signal_handlers: signal handlers cannot be
        # installed in a test loop, so the event is triggered directly.
        state["event"] = shutdown_event

    def _health_server(checks_fn, port=0):
        state["health"] = _FakeHealthServer(checks_fn, port)
        return state["health"]

    monkeypatch.setattr(main_module, "install_signal_handlers", _capture_event)
    monkeypatch.setattr(main_module, "HealthServer", _health_server)
    monkeypatch.setattr(main_module, "engine", state["engine"])
    return state


async def _wait_for_startup(state):
    for _ in range(100):
        await asyncio.sleep(0.01)
        if state["event"] is not None and state["health"] is not None:
            return
    raise AssertionError("main() did not finish starting up")


@pytest.mark.asyncio
async def test_sigterm_lets_the_in_flight_batch_finish(harness, monkeypatch):
    finished = asyncio.Event()

    async def fake_consume(shutdown_event):
        await shutdown_event.wait()
        # The in-flight batch keeps working after the shutdown signal.
        await asyncio.sleep(0.05)
        finished.set()

    monkeypatch.setattr(main_module, "consume", fake_consume)

    task = asyncio.create_task(main_module.main())
    await _wait_for_startup(harness)

    harness["event"].set()
    await task

    # The consumer was drained, not cancelled mid-batch.
    assert finished.is_set()
    assert harness["health"].stopped is True
    assert harness["engine"].disposed is True


@pytest.mark.asyncio
async def test_shutdown_releases_resources_when_consumer_dies_on_its_own(
    harness, monkeypatch
):
    async def dying_consume(shutdown_event):
        raise RuntimeError("kafka is gone")

    monkeypatch.setattr(main_module, "consume", dying_consume)

    task = asyncio.create_task(main_module.main())
    await _wait_for_startup(harness)

    # A dead consumer must bring the process down cleanly rather than leaving
    # a container that passes liveness while consuming nothing.
    await task

    assert harness["health"].stopped is True
    assert harness["engine"].disposed is True


@pytest.mark.asyncio
async def test_stuck_consumer_is_cancelled_after_the_drain_timeout(
    harness, monkeypatch
):
    cancelled = asyncio.Event()

    async def stuck_consume(shutdown_event):
        try:
            await asyncio.Event().wait()  # never completes
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(main_module, "consume", stuck_consume)

    async def instant_timeout(awaitable, timeout):
        # Collapse the 10s drain budget so the bounded path is exercised fast.
        assert timeout == 10
        raise TimeoutError

    monkeypatch.setattr(main_module.asyncio, "wait_for", instant_timeout)

    task = asyncio.create_task(main_module.main())
    await _wait_for_startup(harness)

    harness["event"].set()
    await task

    # The drain is bounded: a stuck consumer gets cancelled, not waited on.
    assert cancelled.is_set()
    assert harness["health"].stopped is True
    assert harness["engine"].disposed is True


@pytest.mark.asyncio
async def test_health_reports_kafka_error_once_the_consumer_stops(harness, monkeypatch):
    async def fake_consume(shutdown_event):
        await shutdown_event.wait()

    monkeypatch.setattr(main_module, "consume", fake_consume)

    task = asyncio.create_task(main_module.main())
    await _wait_for_startup(harness)

    checks_fn = harness["health"].checks_fn
    # Postgres is unreachable in this unit test, so only the kafka key is
    # asserted: it tracks liveness of the consume loop.
    assert (await checks_fn())["kafka"] == "ok"

    harness["event"].set()
    await task

    assert (await checks_fn())["kafka"] == "error"


def test_install_signal_handlers_registers_termination_signals(monkeypatch):
    import signal

    async def _run():
        event = asyncio.Event()
        registered = []

        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "add_signal_handler",
            lambda sig, handler: registered.append((sig, handler)),
        )

        main_module.install_signal_handlers(event)
        # Snapshot inside the loop: asyncio.run() restores its own SIGINT
        # handler on the way out, which would otherwise show up here.
        return list(registered), event

    registered, event = asyncio.run(_run())

    assert [sig for sig, _ in registered] == [signal.SIGTERM, signal.SIGINT]
    # Each handler just flips the shutdown event; the drain happens in main().
    for _, handler in registered:
        handler()
    assert event.is_set()


def test_install_signal_handlers_falls_back_on_platforms_without_loop_support(
    monkeypatch,
):
    import signal

    async def _run():
        event = asyncio.Event()
        installed = []

        loop = asyncio.get_running_loop()

        def _unsupported(sig, handler):
            raise NotImplementedError

        monkeypatch.setattr(loop, "add_signal_handler", _unsupported)
        monkeypatch.setattr(
            signal, "signal", lambda sig, handler: installed.append((sig, handler))
        )

        main_module.install_signal_handlers(event)
        return list(installed), event

    installed, event = asyncio.run(_run())

    # Windows has no loop-level signal handlers; the sync fallback must still
    # wire both signals so shutdown is graceful there too.
    assert [sig for sig, _ in installed] == [signal.SIGTERM, signal.SIGINT]
    for _, handler in installed:
        handler()
    assert event.is_set()
