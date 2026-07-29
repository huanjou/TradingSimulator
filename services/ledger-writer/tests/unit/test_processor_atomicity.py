"""Transactional guarantees of the ledger-writer batch processor.

The batch writes (order inserts, trade inserts, balance upserts, symbol
events) share a single transaction with a single commit, so a failure can
never leave a partially persisted batch behind. Order status updates are the
one exception: they run in their own commit scope with a per-row fallback,
which must not interfere with the atomic block.
"""

import json
from unittest.mock import AsyncMock, call

import pytest
from app.services.processor import process_orders

ORDER_ID = "1049b870-9115-42f0-bc65-bbeaad370d71"
OTHER_ORDER_ID = "2149b870-9115-42f0-bc65-bbeaad370d72"
THIRD_ORDER_ID = "3249b870-9115-42f0-bc65-bbeaad370d73"
TRADE_ID = "597c03a6-14e3-4dd2-aa9c-ec22e74271cf"
OTHER_TRADE_ID = "697c03a6-14e3-4dd2-aa9c-ec22e74271d0"


class MockMessage:
    def __init__(self, value_dict):
        self.value = json.dumps(value_dict).encode("utf-8")


@pytest.fixture
def mock_repos():
    return {
        "order_repo": AsyncMock(),
        "trade_repo": AsyncMock(),
        "symbol_repo": AsyncMock(),
        "balance_repo": AsyncMock(),
    }


@pytest.fixture
def mock_session():
    return AsyncMock()


def _trade(trade_id=TRADE_ID, order_id=ORDER_ID) -> MockMessage:
    return MockMessage(
        {
            "trade_id": trade_id,
            "order_id": order_id,
            "symbol": "BTC/USD",
            "price": "50000",
            "quantity": "1.0",
            "timestamp": 1.0,
        }
    )


def _balance(user_id="user-1", currency="USD") -> MockMessage:
    return MockMessage(
        {
            "user_id": user_id,
            "currency": currency,
            "available": "900.0",
            "locked": "100.0",
        }
    )


def _order_update(order_id, status="FILLED") -> MockMessage:
    return MockMessage(
        {"order_id": order_id, "status": status, "filled_quantity": "1.0"}
    )


@pytest.mark.asyncio
async def test_trade_batch_commits_exactly_once(mock_session, mock_repos):
    await process_orders(
        [_trade(), _trade(OTHER_TRADE_ID)],
        session=mock_session,
        topic="trades",
        **mock_repos,
    )

    # One commit for the whole batch, not one per row.
    assert mock_session.commit.await_count == 1
    mock_session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_trade_write_failure_rolls_back_without_committing(
    mock_session, mock_repos
):
    mock_repos["trade_repo"].upsert_bulk.side_effect = Exception("trade insert failed")

    with pytest.raises(Exception, match="trade insert failed"):
        await process_orders(
            [_trade()], session=mock_session, topic="trades", **mock_repos
        )

    # Nothing may be committed when part of the batch failed.
    mock_session.commit.assert_not_awaited()
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_balance_write_failure_rolls_back_without_committing(
    mock_session, mock_repos
):
    mock_repos["balance_repo"].upsert_bulk.side_effect = Exception("balance failed")

    with pytest.raises(Exception, match="balance failed"):
        await process_orders(
            [_balance()], session=mock_session, topic="balance_updates", **mock_repos
        )

    mock_session.commit.assert_not_awaited()
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_balance_upserts_are_skipped_without_a_balance_repo(
    mock_session, mock_repos
):
    mock_repos.pop("balance_repo")

    # Missing repo must not crash the batch (balance_repo is optional).
    await process_orders(
        [_balance()], session=mock_session, topic="balance_updates", **mock_repos
    )

    assert mock_session.commit.await_count == 1


@pytest.mark.asyncio
async def test_symbol_event_shares_the_batch_commit(mock_session, mock_repos):
    messages = [MockMessage({"type": "SYMBOL_CREATED", "symbol": "ETH/USD"})]

    await process_orders(
        messages, session=mock_session, topic="system_events", **mock_repos
    )

    mock_repos["symbol_repo"].upsert.assert_awaited_once_with(mock_session, "ETH/USD")
    assert mock_session.commit.await_count == 1


@pytest.mark.asyncio
async def test_symbol_event_failure_rolls_back_the_whole_batch(
    mock_session, mock_repos
):
    mock_repos["symbol_repo"].upsert.side_effect = Exception("symbol failed")
    messages = [MockMessage({"type": "SYMBOL_CREATED", "symbol": "ETH/USD"})]

    with pytest.raises(Exception, match="symbol failed"):
        await process_orders(
            messages, session=mock_session, topic="system_events", **mock_repos
        )

    mock_session.commit.assert_not_awaited()
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_ids_are_deduplicated_within_the_batch(
    mock_session, mock_repos
):
    # Kafka can redeliver; the last copy wins and only one row is written.
    await process_orders(
        [_trade(), _trade()], session=mock_session, topic="trades", **mock_repos
    )

    args, _ = mock_repos["trade_repo"].upsert_bulk.call_args
    assert len(args[1]) == 1
    assert mock_session.commit.await_count == 1


@pytest.mark.asyncio
async def test_order_update_bulk_failure_falls_back_to_individual_rows(
    mock_session, mock_repos
):
    # The bulk path fails on eventual consistency (update arrives before the
    # insert), so each row is retried on its own.
    mock_repos["order_repo"].update_status_bulk.side_effect = Exception("stale data")

    await process_orders(
        [_order_update(ORDER_ID), _order_update(OTHER_ORDER_ID)],
        session=mock_session,
        topic="order_updates",
        **mock_repos,
    )

    assert mock_repos["order_repo"].update_status.await_count == 2
    # One rollback for the failed bulk attempt, then a commit per row plus the
    # final batch commit.
    mock_session.rollback.assert_awaited_once()
    assert mock_session.commit.await_count == 3


@pytest.mark.asyncio
async def test_order_update_fallback_isolates_a_failing_row(mock_session, mock_repos):
    mock_repos["order_repo"].update_status_bulk.side_effect = Exception("stale data")

    def _fail_middle_row(session, order_id, *args):
        if order_id == OTHER_ORDER_ID:
            raise Exception("row still missing")

    mock_repos["order_repo"].update_status.side_effect = _fail_middle_row

    # A single unwritable row must not abort the rest of the batch.
    await process_orders(
        [
            _order_update(ORDER_ID),
            _order_update(OTHER_ORDER_ID),
            _order_update(THIRD_ORDER_ID),
        ],
        session=mock_session,
        topic="order_updates",
        **mock_repos,
    )

    assert mock_repos["order_repo"].update_status.await_count == 3
    # Bulk rollback + the failing row's rollback.
    assert mock_session.rollback.await_count == 2
    # Two successful rows plus the final batch commit.
    assert mock_session.commit.await_count == 3


@pytest.mark.asyncio
async def test_order_update_fallback_passes_all_fields(mock_session, mock_repos):
    mock_repos["order_repo"].update_status_bulk.side_effect = Exception("stale data")
    messages = [
        MockMessage(
            {
                "order_id": ORDER_ID,
                "status": "PARTIALLY_FILLED",
                "filled_quantity": "0.5",
                "average_fill_price": "49999.99",
            }
        )
    ]

    await process_orders(
        messages, session=mock_session, topic="order_updates", **mock_repos
    )

    from decimal import Decimal

    assert mock_repos["order_repo"].update_status.await_args == call(
        mock_session,
        ORDER_ID,
        "PARTIALLY_FILLED",
        Decimal("0.5"),
        Decimal("49999.99"),
    )


@pytest.mark.asyncio
async def test_order_updates_do_not_run_through_the_atomic_block(
    mock_session, mock_repos
):
    # Order updates are the only path allowed to commit mid-batch; nothing
    # else may be written when the topic only carries updates.
    await process_orders(
        [_order_update(ORDER_ID)],
        session=mock_session,
        topic="order_updates",
        **mock_repos,
    )

    mock_repos["order_repo"].upsert_bulk.assert_not_awaited()
    mock_repos["trade_repo"].upsert_bulk.assert_not_awaited()
    mock_repos["balance_repo"].upsert_bulk.assert_not_awaited()
    assert mock_session.commit.await_count == 1


@pytest.mark.asyncio
async def test_invalid_rows_are_dropped_before_the_transaction(
    mock_session, mock_repos
):
    # Non-UUID ids would violate the DB schema; they are filtered out so one
    # bad message cannot roll back a whole valid batch.
    messages = [
        _trade(trade_id="not-a-uuid"),
        _trade(),
        MockMessage({"order_id": ORDER_ID}),  # no trade_id
    ]

    await process_orders(messages, session=mock_session, topic="trades", **mock_repos)

    args, _ = mock_repos["trade_repo"].upsert_bulk.call_args
    assert [row["id"] for row in args[1]] == [TRADE_ID]
    assert mock_session.commit.await_count == 1
    mock_session.rollback.assert_not_awaited()
