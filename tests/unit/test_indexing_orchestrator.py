from __future__ import annotations

from dataclasses import replace
from typing import Any

from knowledge_base.adapters.chunkers.text import MarkdownChunker, PlainTextChunker
from knowledge_base.adapters.models.fake import FakeEmbeddingProvider
from knowledge_base.adapters.parsers.text import MarkdownParser, PlainTextParser
from knowledge_base.adapters.vector_stores.memory import InMemoryVectorStore
from knowledge_base.application.file_classifier import FileClassifier
from knowledge_base.application.indexing_orchestrator import IndexingOrchestrator
from knowledge_base.application.indexing_service import IndexingService
from knowledge_base.domain.exceptions import FullReconcileRequired
from knowledge_base.domain.models import (
    Chunk,
    Document,
    FileChange,
    FileChangeType,
    IndexJob,
    IndexJobStatus,
    IndexStatus,
    Repository,
    SourceFile,
)


class FakeSourceRepository:
    def __init__(self, content: str) -> None:
        self.content = content
        self.changes = [FileChange("README.md", FileChangeType.MODIFIED)]
        self.require_full_reconcile = False

    async def get_repository(self) -> Repository:
        return Repository("acme/orders", "acme", "orders")

    async def resolve_commit(self, ref: str) -> str:
        return "target-sha"

    async def list_files(self, ref: str) -> list[str]:
        return ["README.md"]

    async def compare(self, base_commit: str, target_commit: str) -> list[FileChange]:
        if self.require_full_reconcile:
            raise FullReconcileRequired("diff is incomplete")
        return self.changes

    async def fetch_file(self, path: str, ref: str) -> SourceFile:
        return SourceFile("acme/orders", path, ref, self.content)


class FakePersistence:
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, Chunk] = {}
        self.jobs: dict[str, IndexJob] = {}

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def ping(self) -> bool:
        return True

    async def upsert_documents(self, documents: list[Document]) -> None:
        self.documents.update({document.id: document for document in documents})

    async def upsert_chunks(self, chunks: list[Chunk]) -> None:
        self.chunks.update({chunk.id: chunk for chunk in chunks})

    async def get_document_by_path(
        self, repository_id: str, path: str
    ) -> Document | None:
        return next(
            (
                document
                for document in self.documents.values()
                if document.repository_id == repository_id and document.path == path
            ),
            None,
        )

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)

    async def get_chunks(self, chunk_ids: list[str]) -> list[Chunk]:
        return [self.chunks[item] for item in chunk_ids if item in self.chunks]

    async def delete_document_chunks(self, document_id: str) -> None:
        self.chunks = {
            key: chunk
            for key, chunk in self.chunks.items()
            if chunk.document_id != document_id
        }

    async def get_document_chunk_ids(self, document_id: str) -> list[str]:
        return [
            chunk.id
            for chunk in self.chunks.values()
            if chunk.document_id == document_id
        ]

    async def delete_chunks(self, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self.chunks.pop(chunk_id, None)

    async def mark_document_deleted(self, document_id: str) -> None:
        self.documents.pop(document_id, None)

    async def mark_chunks_indexed(
        self,
        chunk_ids: list[str],
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

    async def mark_chunks_failed(self, chunk_ids: list[str], error: str) -> None:
        for chunk_id in chunk_ids:
            self.chunks[chunk_id] = replace(
                self.chunks[chunk_id], vector_status=IndexStatus.FAILED
            )

    async def create_index_job(self, job: IndexJob) -> None:
        self.jobs[job.id] = job

    async def save_index_job(self, job: IndexJob) -> None:
        self.jobs[job.id] = job

    async def get_index_job(self, job_id: str) -> IndexJob | None:
        return self.jobs.get(job_id)


def build_orchestrator(
    source: FakeSourceRepository, persistence: FakePersistence, vectors: Any
) -> IndexingOrchestrator:
    service = IndexingService(
        document_store=persistence,
        vector_store=vectors,
        embedding_provider=FakeEmbeddingProvider(dimension=4),
        collection_name="chunks",
        index_version="embedding-v1",
    )
    return IndexingOrchestrator(
        source_repository=source,
        document_store=persistence,
        job_store=persistence,
        indexing_service=service,
        classifier=FileClassifier(),
        parsers={"markdown": MarkdownParser(), "plain_text": PlainTextParser()},
        chunkers={
            "markdown": MarkdownChunker(max_tokens=20, overlap_tokens=2),
            "plain_text": PlainTextChunker(max_tokens=20, overlap_tokens=2),
        },
    )


async def test_incremental_pipeline_indexes_and_skips_unchanged_content() -> None:
    source = FakeSourceRepository("# Orders\nSearch by customer id")
    persistence = FakePersistence()
    vectors = InMemoryVectorStore()
    await vectors.connect()
    orchestrator = build_orchestrator(source, persistence, vectors)

    first = await orchestrator.run(base_commit="base-sha", target_ref="main")
    chunk_ids = list(persistence.chunks)
    second = await orchestrator.run(base_commit="base-sha", target_ref="main")

    assert first.status is IndexJobStatus.COMPLETED
    assert first.documents_updated == 1
    assert first.chunks_created == 1
    assert second.documents_updated == 0
    assert list(persistence.chunks) == chunk_ids


async def test_deleted_file_removes_document_chunks_and_vectors() -> None:
    source = FakeSourceRepository("# Orders\nSearch by customer id")
    persistence = FakePersistence()
    vectors = InMemoryVectorStore()
    await vectors.connect()
    orchestrator = build_orchestrator(source, persistence, vectors)
    await orchestrator.run(base_commit="base-sha", target_ref="main")
    source.changes = [FileChange("README.md", FileChangeType.DELETED)]

    job = await orchestrator.run(base_commit="target-sha", target_ref="main")

    assert job.status is IndexJobStatus.COMPLETED
    assert persistence.documents == {}
    assert persistence.chunks == {}


async def test_failed_job_can_be_retried_from_stored_commits() -> None:
    source = FakeSourceRepository("# Orders\nSearch by customer id")
    persistence = FakePersistence()
    failed = IndexJob(
        id="failed-job",
        repository_id="acme/orders",
        base_commit="base-sha",
        target_commit="target-sha",
        status=IndexJobStatus.FAILED,
        retry_count=1,
        error="temporary failure",
    )
    persistence.jobs[failed.id] = failed
    vectors = InMemoryVectorStore()
    await vectors.connect()
    orchestrator = build_orchestrator(source, persistence, vectors)

    retried = await orchestrator.retry(failed.id)

    assert retried.status is IndexJobStatus.COMPLETED
    assert retried.retry_count == 1
    assert retried.base_commit == "base-sha"


async def test_incomplete_incremental_diff_falls_back_to_full_file_listing() -> None:
    source = FakeSourceRepository("# Orders\nSearch by customer id")
    source.require_full_reconcile = True
    persistence = FakePersistence()
    vectors = InMemoryVectorStore()
    await vectors.connect()
    orchestrator = build_orchestrator(source, persistence, vectors)

    job = await orchestrator.run(base_commit="base-sha", target_ref="main")

    assert job.status is IndexJobStatus.COMPLETED
    assert job.files_scanned == 1
    assert job.documents_updated == 1
