import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_wallet_repo():
    return AsyncMock()


@pytest.fixture
def mock_consumer():
    with patch("app.services.kafka_consumer.AIOKafkaConsumer") as mock:
        yield mock


@pytest.mark.asyncio
async def test_consume_balance_updates(mock_wallet_repo, mock_consumer):
    from app.services.kafka_consumer import BalanceUpdateConsumer

    # create a mock message
    msg = MagicMock()
    msg.value = json.dumps(
        {
            "user_id": "user1",
            "currency": "USD",
            "available": "2000.0",
            "locked": "100.0",
        }
    ).encode("utf-8")

    class MockConsumer:
        def __init__(self, msg):
            self.msg = msg
            self.yielded = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.yielded:
                self.yielded = True
                return self.msg
            raise __import__("asyncio").CancelledError()

        async def commit(self):
            pass

    consumer_instance = MockConsumer(msg)

    consumer = BalanceUpdateConsumer()
    consumer.consumer = consumer_instance

    # Patch _update_redis so we can verify the call
    with patch.object(consumer, "_update_redis", new_callable=AsyncMock) as mock_update:
        # We need to manually call consume.
        task = __import__("asyncio").create_task(consumer.consume())
        await __import__("asyncio").sleep(0.1)  # let it run
        task.cancel()
        try:
            await task
        except __import__("asyncio").CancelledError:
            pass

        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        assert args[1] == "user1"
        assert args[2] == "USD"


@pytest.mark.asyncio
async def test_consumer_corrupted_message_handling():
    """QA Resilience: Консьюмер не должен падать при некорректном сообщении."""
    from app.services.kafka_consumer import BalanceUpdateConsumer

    corrupted_msg = MagicMock()
    corrupted_msg.value = b"NOT_A_JSON_PAYLOAD"

    class MockConsumer:
        def __init__(self, msg):
            self.msg = msg
            self.yielded = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.yielded:
                self.yielded = True
                return self.msg
            raise __import__("asyncio").CancelledError()

        async def commit(self):
            pass

    consumer = BalanceUpdateConsumer()
    consumer.consumer = MockConsumer(corrupted_msg)

    with patch("app.services.kafka_consumer.logger.error") as mock_logger:
        task = __import__("asyncio").create_task(consumer.consume())
        await __import__("asyncio").sleep(0.1)
        task.cancel()
        try:
            await task
        except __import__("asyncio").CancelledError:
            pass

        mock_logger.assert_called()
        assert any(
            "Error processing balance update" in str(call)
            for call in mock_logger.call_args_list
        )


@pytest.mark.asyncio
async def test_consumer_retry_on_redis_failure():
    """QA Resilience: Проверка автоповтора _update_redis через tenacity."""
    from decimal import Decimal

    from app.services.kafka_consumer import BalanceUpdateConsumer

    consumer = BalanceUpdateConsumer()
    mock_repo = AsyncMock()

    mock_repo.update_wallet_balance.side_effect = [
        ConnectionError("Redis temporary timeout 1"),
        ConnectionError("Redis temporary timeout 2"),
        None,
    ]

    await consumer._update_redis(
        mock_repo, "user_retry", "USD", Decimal("100.0"), Decimal("0.0")
    )
    assert mock_repo.update_wallet_balance.call_count == 3
