from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from knowledge_base.domain.models import Chunk
from knowledge_base.ports.document_store import DocumentStore
from knowledge_base.ports.embedding_provider import EmbeddingProvider
from knowledge_base.ports.vector_store import VectorRecord, VectorStore


@dataclass(slots=True)
class IndexingService:
    document_store: DocumentStore
    vector_store: VectorStore
    embedding_provider: EmbeddingProvider
    collection_name: str
    index_version: str

    async def index_chunks(self, chunks: Sequence[Chunk]) -> int:
        """Persist, embed, index, then mark chunks indexed in canonical storage."""
        if not chunks:
            return 0
        await self.document_store.upsert_chunks(chunks)
        vectors = await self.embedding_provider.embed_documents(
            [chunk.content for chunk in chunks]
        )
        if len(vectors) != len(chunks):
            raise ValueError("embedding provider returned an unexpected vector count")
        await self.vector_store.ensure_collection(
            self.collection_name, self.embedding_provider.dimension
        )
        await self.vector_store.upsert(
            self.collection_name,
            [
                VectorRecord(
                    id=chunk.id,
                    vector=vector,
                    metadata={
                        "document_id": chunk.document_id,
                        "repository_id": chunk.repository_id,
                        "commit_sha": chunk.commit_sha,
                        "index_version": self.index_version,
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )
        await self.document_store.mark_chunks_indexed(
            [chunk.id for chunk in chunks],
            self.index_version,
            self.embedding_provider.model_id,
            self.embedding_provider.dimension,
        )
        return len(chunks)
