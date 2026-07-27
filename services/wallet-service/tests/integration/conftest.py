import pytest


class FakeAsyncRedis:
    def __init__(self):
        self.storage = {}

    async def hgetall(self, name: str):
        return self.storage.get(name, {}).copy()

    async def hset(
        self, name: str, key: str = None, value: str = None, mapping: dict = None
    ):
        if name not in self.storage:
            self.storage[name] = {}
        if mapping:
            for k, v in mapping.items():
                self.storage[name][k] = v
        elif key is not None and value is not None:
            self.storage[name][key] = value
        return 1

    async def close(self):
        pass


@pytest.fixture
def fake_redis():
    return FakeAsyncRedis()
