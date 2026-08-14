from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from knowledge_base.domain.exceptions import StoreNotConnectedError
from knowledge_base.domain.models import Chunk, Document, IndexStatus, utc_now

ClientFactory = Callable[[str], Any]


class MongoDocumentStore:
    """MongoDB document store with explicit, idempotent lifecycle methods."""

    def __init__(
        self,
        uri: str,
        database_name: str,
        *,
        client_factory: ClientFactory = AsyncIOMotorClient,
    ) -> None:
        self._uri = uri
        self._database_name = database_name
        self._client_factory = client_factory
        self._client: Any | None = None
        self._database: Any | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        if self.connected:
            return
        client = self._client_factory(self._uri)
        try:
            await client.admin.command("ping")
        except Exception:
            client.close()
            raise
        self._client = client
        self._database = client[self._database_name]

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._database = None

    async def ping(self) -> bool:
        self._require_connected()
        client = self._client
        if client is None:
            raise StoreNotConnectedError("MongoDB document store is not connected")
        try:
            await client.admin.command("ping")
        except Exception:
            return False
        return True

    async def upsert_documents(self, documents: Sequence[Document]) -> None:
        database = self._require_connected()
        for document in documents:
            data = asdict(document)
            data["_id"] = data.pop("id")
            await database.documents.replace_one(
                {"_id": document.id}, data, upsert=True
            )

    async def upsert_chunks(self, chunks: Sequence[Chunk]) -> None:
        database = self._require_connected()
        for chunk in chunks:
            data = asdict(chunk)
            data["_id"] = data.pop("id")
            data["heading_path"] = list(chunk.heading_path)
            await database.chunks.replace_one({"_id": chunk.id}, data, upsert=True)

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        database = self._require_connected()
        item = await database.chunks.find_one({"_id": chunk_id})
        return self._deserialize_chunk(item) if item else None

    async def get_chunks(self, chunk_ids: Sequence[str]) -> list[Chunk]:
        database = self._require_connected()
        if not chunk_ids:
            return []
        items = await database.chunks.find({"_id": {"$in": list(chunk_ids)}}).to_list(
            length=len(chunk_ids)
        )
        by_id = {item["_id"]: self._deserialize_chunk(item) for item in items}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    async def delete_document_chunks(self, document_id: str) -> None:
        database = self._require_connected()
        await database.chunks.delete_many({"document_id": document_id})

    async def mark_chunks_indexed(
        self,
        chunk_ids: Sequence[str],
        index_version: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        database = self._require_connected()
        if not chunk_ids:
            return
        await database.chunks.update_many(
            {"_id": {"$in": list(chunk_ids)}},
            {
                "$set": {
                    "vector_status": IndexStatus.INDEXED,
                    "vector_index_version": index_version,
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                    "updated_at": utc_now(),
                }
            },
        )

    def _require_connected(self) -> Any:
        if self._database is None:
            raise StoreNotConnectedError("MongoDB document store is not connected")
        return self._database

    @staticmethod
    def _deserialize_chunk(item: dict[str, Any]) -> Chunk:
        data = dict(item)
        data["id"] = data.pop("_id")
        data["heading_path"] = tuple(data.get("heading_path", ()))
        if isinstance(data.get("vector_status"), str):
            data["vector_status"] = IndexStatus(data["vector_status"])
        return Chunk(**data)
