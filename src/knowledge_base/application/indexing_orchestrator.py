from __future__ import annotations

import uuid
from dataclasses import replace

from knowledge_base.application.file_classifier import FileClassifier
from knowledge_base.application.indexing_service import IndexingService
from knowledge_base.domain.exceptions import FullReconcileRequired
from knowledge_base.domain.models import (
    FileChange,
    FileChangeType,
    IndexJob,
    IndexJobStatus,
    utc_now,
)
from knowledge_base.ports.chunker import Chunker
from knowledge_base.ports.document_parser import DocumentParser
from knowledge_base.ports.document_store import DocumentStore
from knowledge_base.ports.index_job_store import IndexJobStore
from knowledge_base.ports.source_repository import SourceRepository


class IndexingOrchestrator:
    def __init__(
        self,
        *,
        source_repository: SourceRepository,
        document_store: DocumentStore,
        job_store: IndexJobStore,
        indexing_service: IndexingService,
        classifier: FileClassifier,
        parsers: dict[str, DocumentParser],
        chunkers: dict[str, Chunker],
    ) -> None:
        self.source_repository = source_repository
        self.document_store = document_store
        self.job_store = job_store
        self.indexing_service = indexing_service
        self.classifier = classifier
        self.parsers = parsers
        self.chunkers = chunkers

    async def run(
        self,
        *,
        base_commit: str | None,
        target_ref: str,
        _retry_count: int = 0,
    ) -> IndexJob:
        repository = await self.source_repository.get_repository()
        target_commit = await self.source_repository.resolve_commit(target_ref)
        job = IndexJob(
            id=str(uuid.uuid4()),
            repository_id=repository.id,
            base_commit=base_commit,
            target_commit=target_commit,
            status=IndexJobStatus.RUNNING,
            retry_count=_retry_count,
            started_at=utc_now(),
        )
        await self.job_store.create_index_job(job)
        try:
            changes = await self._changes(base_commit, target_commit)
            documents_updated = 0
            chunks_created = 0
            for change in changes:
                updated, created = await self._process_change(change, target_commit)
                documents_updated += updated
                chunks_created += created
            job = replace(
                job,
                status=IndexJobStatus.COMPLETED,
                files_scanned=len(changes),
                documents_updated=documents_updated,
                chunks_created=chunks_created,
                finished_at=utc_now(),
                updated_at=utc_now(),
            )
        except Exception as error:
            job = replace(
                job,
                status=IndexJobStatus.FAILED,
                retry_count=job.retry_count + 1,
                error=str(error),
                finished_at=utc_now(),
                updated_at=utc_now(),
            )
            await self.job_store.save_index_job(job)
            raise
        await self.job_store.save_index_job(job)
        return job

    async def retry(self, job_id: str) -> IndexJob:
        previous = await self.job_store.get_index_job(job_id)
        if previous is None:
            raise KeyError(f"index job {job_id!r} does not exist")
        if previous.status is not IndexJobStatus.FAILED:
            raise ValueError("only failed index jobs can be retried")
        return await self.run(
            base_commit=previous.base_commit,
            target_ref=previous.target_commit,
            _retry_count=previous.retry_count,
        )

    async def _changes(
        self, base_commit: str | None, target_commit: str
    ) -> list[FileChange]:
        if base_commit is not None:
            try:
                return list(
                    await self.source_repository.compare(base_commit, target_commit)
                )
            except FullReconcileRequired:
                pass
        return [
            FileChange(path, FileChangeType.ADDED)
            for path in await self.source_repository.list_files(target_commit)
        ]

    async def _process_change(
        self, change: FileChange, target_commit: str
    ) -> tuple[int, int]:
        if change.change_type is FileChangeType.RENAMED and change.previous_path:
            await self._delete_path(change.previous_path)
        if change.change_type is FileChangeType.DELETED:
            await self._delete_path(change.path)
            return (1, 0)
        document_type = self.classifier.classify(change.path)
        if document_type is None:
            return (0, 0)
        source = await self.source_repository.fetch_file(change.path, target_commit)
        document = self.parsers[document_type].parse(source)
        existing = await self.document_store.get_document_by_path(
            document.repository_id, document.path
        )
        if existing is not None and existing.content_hash == document.content_hash:
            return (0, 0)
        old_ids = (
            await self.document_store.get_document_chunk_ids(existing.id)
            if existing is not None
            else []
        )
        chunks = self.chunkers[document_type].chunk(document)
        await self.document_store.upsert_documents([document])
        await self.indexing_service.index_chunks(chunks)
        new_ids = {chunk.id for chunk in chunks}
        stale_ids = [chunk_id for chunk_id in old_ids if chunk_id not in new_ids]
        if stale_ids:
            await self.indexing_service.delete_chunks(stale_ids)
            await self.document_store.delete_chunks(stale_ids)
        return (1, len(chunks))

    async def _delete_path(self, path: str) -> None:
        repository = await self.source_repository.get_repository()
        document = await self.document_store.get_document_by_path(repository.id, path)
        if document is None:
            return
        chunk_ids = await self.document_store.get_document_chunk_ids(document.id)
        if chunk_ids:
            await self.indexing_service.delete_chunks(chunk_ids)
        await self.document_store.delete_document_chunks(document.id)
        await self.document_store.mark_document_deleted(document.id)
