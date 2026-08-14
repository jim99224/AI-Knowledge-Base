from collections.abc import Sequence
from dataclasses import replace

from knowledge_base.adapters.models.fake import FakeEmbeddingProvider
from knowledge_base.adapters.vector_stores.memory import InMemoryVectorStore
from knowledge_base.application.indexing_service import IndexingService
from knowledge_base.domain.models import Chunk, IndexStatus


class FakeDocumentStore:
    def __init__(self) -> None:
        self.chunks: dict[str, Chunk] = {}

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def ping(self) -> bool:
        return True

    async def upsert_documents(self, documents: Sequence[object]) -> None:
        pass

    async def upsert_chunks(self, chunks: Sequence[Chunk]) -> None:
        self.chunks.update({chunk.id: chunk for chunk in chunks})

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)

    async def get_chunks(self, chunk_ids: Sequence[str]) -> list[Chunk]:
        return [self.chunks[item] for item in chunk_ids if item in self.chunks]

    async def delete_document_chunks(self, document_id: str) -> None:
        self.chunks = {
            key: value
            for key, value in self.chunks.items()
            if value.document_id != document_id
        }

    async def mark_chunks_indexed(
        self,
        chunk_ids: Sequence[str],
        index_version: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        for chunk_id in chunk_ids:
            self.chunks[chunk_id] = replace(
                self.chunks[chunk_id],
                vector_status=IndexStatus.INDEXED,
                vector_index_version=index_version,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )


async def test_application_service_runs_with_fake_store() -> None:
    documents = FakeDocumentStore()
    vectors = InMemoryVectorStore()
    await vectors.connect()
    service = IndexingService(
        document_store=documents,
        vector_store=vectors,
        embedding_provider=FakeEmbeddingProvider(dimension=4),
        collection_name="chunks",
        index_version="embedding-v1",
    )
    chunk = Chunk(
        id="chunk-1",
        document_id="doc-1",
        repository_id="repo-1",
        chunk_index=0,
        content="MongoDB is canonical.",
        content_hash="hash",
        commit_sha="abc123",
    )

    assert await service.index_chunks([chunk]) == 1
    indexed = await documents.get_chunk("chunk-1")
    assert indexed is not None
    assert indexed.vector_status is IndexStatus.INDEXED
    query_vector = await FakeEmbeddingProvider(4).embed_query(chunk.content)
    matches = await vectors.search("chunks", query_vector, 1)
    assert matches[0].id == "chunk-1"
