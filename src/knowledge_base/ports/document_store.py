from collections.abc import Sequence
from typing import Protocol

from knowledge_base.domain.models import Chunk, Document


class DocumentStore(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def ping(self) -> bool: ...

    async def upsert_documents(self, documents: Sequence[Document]) -> None: ...

    async def upsert_chunks(self, chunks: Sequence[Chunk]) -> None: ...

    async def get_chunk(self, chunk_id: str) -> Chunk | None: ...

    async def get_chunks(self, chunk_ids: Sequence[str]) -> list[Chunk]: ...

    async def delete_document_chunks(self, document_id: str) -> None: ...

    async def mark_chunks_indexed(
        self,
        chunk_ids: Sequence[str],
        index_version: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None: ...
