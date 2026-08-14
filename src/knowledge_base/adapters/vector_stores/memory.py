from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from typing import Any

from knowledge_base.domain.exceptions import (
    DimensionMismatchError,
    StoreNotConnectedError,
)
from knowledge_base.ports.vector_store import VectorMatch, VectorRecord


class InMemoryVectorStore:
    """Deterministic development adapter using cosine similarity."""

    def __init__(self) -> None:
        self._connected = False
        self._dimensions: dict[str, int] = {}
        self._records: dict[str, dict[str, VectorRecord]] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def ensure_collection(self, collection_name: str, dimension: int) -> None:
        self._require_connected()
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        async with self._lock:
            existing = self._dimensions.get(collection_name)
            if existing is not None and existing != dimension:
                raise DimensionMismatchError(
                    f"collection {collection_name!r} has dimension {existing}, "
                    f"not {dimension}"
                )
            self._dimensions[collection_name] = dimension
            self._records.setdefault(collection_name, {})

    async def upsert(
        self, collection_name: str, records: Sequence[VectorRecord]
    ) -> None:
        self._require_connected()
        dimension = self._collection_dimension(collection_name)
        for record in records:
            self._validate_dimension(record.vector, dimension)
        async with self._lock:
            collection = self._records[collection_name]
            collection.update({record.id: record for record in records})

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        self._require_connected()
        if top_k <= 0:
            return []
        dimension = self._collection_dimension(collection_name)
        self._validate_dimension(query_vector, dimension)
        records = list(self._records[collection_name].values())
        matches = [
            VectorMatch(
                id=record.id,
                score=self._cosine_similarity(query_vector, record.vector),
                metadata=dict(record.metadata),
            )
            for record in records
            if self._matches_filters(record.metadata, filters)
        ]
        return sorted(matches, key=lambda match: (-match.score, match.id))[:top_k]

    async def delete(self, collection_name: str, ids: Sequence[str]) -> None:
        self._require_connected()
        self._collection_dimension(collection_name)
        async with self._lock:
            for record_id in ids:
                self._records[collection_name].pop(record_id, None)

    def _require_connected(self) -> None:
        if not self._connected:
            raise StoreNotConnectedError("vector store is not connected")

    def _collection_dimension(self, collection_name: str) -> int:
        try:
            return self._dimensions[collection_name]
        except KeyError as error:
            raise KeyError(f"collection {collection_name!r} does not exist") from error

    @staticmethod
    def _validate_dimension(vector: list[float], dimension: int) -> None:
        if len(vector) != dimension:
            raise DimensionMismatchError(
                f"vector has dimension {len(vector)}, expected {dimension}"
            )

    @staticmethod
    def _matches_filters(
        metadata: dict[str, Any], filters: dict[str, Any] | None
    ) -> bool:
        return filters is None or all(
            metadata.get(key) == value for key, value in filters.items()
        )

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_norm * right_norm
        )
