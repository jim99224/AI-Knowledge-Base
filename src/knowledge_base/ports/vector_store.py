from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class VectorRecord:
    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def ensure_collection(self, collection_name: str, dimension: int) -> None: ...

    async def upsert(
        self, collection_name: str, records: Sequence[VectorRecord]
    ) -> None: ...

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorMatch]: ...

    async def delete(self, collection_name: str, ids: Sequence[str]) -> None: ...
