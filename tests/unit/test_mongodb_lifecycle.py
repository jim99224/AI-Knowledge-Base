from typing import Any

from knowledge_base.adapters.document_stores.mongodb import MongoDocumentStore


class FakeAdmin:
    def __init__(self) -> None:
        self.pings = 0

    async def command(self, command: str) -> dict[str, int]:
        assert command == "ping"
        self.pings += 1
        return {"ok": 1}


class FakeClient:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.admin = FakeAdmin()
        self.closed = False

    def __getitem__(self, name: str) -> dict[str, Any]:
        return {"name": name}

    def close(self) -> None:
        self.closed = True


async def test_mongodb_connect_ping_and_close_are_explicit() -> None:
    clients: list[FakeClient] = []

    def factory(uri: str) -> FakeClient:
        client = FakeClient(uri)
        clients.append(client)
        return client

    store = MongoDocumentStore("mongodb://test", "kb", client_factory=factory)
    assert not store.connected

    await store.connect()
    await store.connect()
    assert store.connected
    assert await store.ping()
    assert clients[0].admin.pings == 2

    await store.close()
    await store.close()
    assert not store.connected
    assert clients[0].closed
