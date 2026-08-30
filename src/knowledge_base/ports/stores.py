from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(slots=True)
class VectorMatch:
    chunk_id: str
    score: float
    metadata: dict


class DocumentStore(Protocol):
    async def get_chunks(self, chunk_ids: Sequence[str]) -> list[object]: ...


class VectorStore(Protocol):
    async def search(
        self,
        query_vector: Sequence[float],
        top_k: int,
        repository_ids: Sequence[str] | None = None,
    ) -> list[VectorMatch]: ...


class GraphStore(Protocol):
    async def upsert_entities(self, entities: Sequence[object]) -> None: ...
    async def upsert_relations(self, relations: Sequence[object]) -> None: ...
    async def neighbors(self, entity_id: str) -> list[object]: ...
    async def traverse(self, start_id: str, max_depth: int = 3) -> list[object]: ...


class MemoryStore(Protocol):
    async def add(self, memory: object) -> None: ...
    async def search(self, query: str, limit: int = 10) -> Sequence[object]: ...
    async def invalidate(self, memory_id: str) -> None: ...
