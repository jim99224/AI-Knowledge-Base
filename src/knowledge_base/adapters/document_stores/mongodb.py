from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from knowledge_base.domain.exceptions import StoreNotConnectedError
from knowledge_base.domain.models import (
    Chunk,
    Document,
    IndexJob,
    IndexJobStatus,
    IndexStatus,
    utc_now,
)

ClientFactory = Callable[[str], Any]


class MongoDocumentStore:
    """MongoDB document store with explicit, idempotent lifecycle methods."""

    def __init__(
        self,
        uri: str,
        database_name: str,
        *,
        client_factory: ClientFactory = AsyncIOMotorClient,
        ensure_indexes: bool = True,
    ) -> None:
        self._uri = uri
        self._database_name = database_name
        self._client_factory = client_factory
        self._ensure_indexes_on_connect = ensure_indexes
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
        if self._ensure_indexes_on_connect:
            try:
                await self._ensure_indexes()
            except Exception:
                await self.close()
                raise

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

    async def get_document_by_path(
        self, repository_id: str, path: str
    ) -> Document | None:
        database = self._require_connected()
        item = await database.documents.find_one(
            {"repository_id": repository_id, "path": path, "deleted_at": None}
        )
        return self._deserialize_document(item) if item else None

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

    async def get_document_chunk_ids(self, document_id: str) -> list[str]:
        database = self._require_connected()
        items = await database.chunks.find(
            {"document_id": document_id}, {"_id": 1}
        ).to_list(length=None)
        return [str(item["_id"]) for item in items]

    async def delete_chunks(self, chunk_ids: Sequence[str]) -> None:
        database = self._require_connected()
        if chunk_ids:
            await database.chunks.delete_many({"_id": {"$in": list(chunk_ids)}})

    async def mark_document_deleted(self, document_id: str) -> None:
        database = self._require_connected()
        await database.documents.update_one(
            {"_id": document_id},
            {"$set": {"deleted_at": utc_now(), "updated_at": utc_now()}},
        )

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

    async def mark_chunks_failed(self, chunk_ids: Sequence[str], error: str) -> None:
        database = self._require_connected()
        if not chunk_ids:
            return
        await database.chunks.update_many(
            {"_id": {"$in": list(chunk_ids)}},
            {
                "$set": {
                    "vector_status": IndexStatus.FAILED,
                    "metadata.last_error": error,
                    "updated_at": utc_now(),
                },
                "$inc": {"retry_count": 1},
            },
        )

    async def create_index_job(self, job: IndexJob) -> None:
        database = self._require_connected()
        data = asdict(job)
        data["_id"] = data.pop("id")
        await database.index_jobs.insert_one(data)

    async def save_index_job(self, job: IndexJob) -> None:
        database = self._require_connected()
        data = asdict(job)
        data["_id"] = data.pop("id")
        await database.index_jobs.replace_one({"_id": job.id}, data, upsert=True)

    async def get_index_job(self, job_id: str) -> IndexJob | None:
        database = self._require_connected()
        item = await database.index_jobs.find_one({"_id": job_id})
        return self._deserialize_index_job(item) if item else None

    def _require_connected(self) -> Any:
        if self._database is None:
            raise StoreNotConnectedError("MongoDB document store is not connected")
        return self._database

    async def _ensure_indexes(self) -> None:
        database = self._require_connected()
        await database.documents.create_index(
            [("repository_id", 1), ("path", 1)], unique=True
        )
        await database.chunks.create_index([("document_id", 1), ("chunk_index", 1)])
        await database.chunks.create_index([("repository_id", 1), ("vector_status", 1)])
        await database.index_jobs.create_index(
            [("repository_id", 1), ("status", 1), ("created_at", -1)]
        )

    @staticmethod
    def _deserialize_chunk(item: dict[str, Any]) -> Chunk:
        data = dict(item)
        data["id"] = data.pop("_id")
        data["heading_path"] = tuple(data.get("heading_path", ()))
        if isinstance(data.get("vector_status"), str):
            data["vector_status"] = IndexStatus(data["vector_status"])
        return Chunk(**data)

    @staticmethod
    def _deserialize_document(item: dict[str, Any]) -> Document:
        data = dict(item)
        data["id"] = data.pop("_id")
        data.pop("deleted_at", None)
        if isinstance(data.get("index_status"), str):
            data["index_status"] = IndexStatus(data["index_status"])
        return Document(**data)

    @staticmethod
    def _deserialize_index_job(item: dict[str, Any]) -> IndexJob:
        data = dict(item)
        data["id"] = data.pop("_id")
        if isinstance(data.get("status"), str):
            data["status"] = IndexJobStatus(data["status"])
        return IndexJob(**data)
