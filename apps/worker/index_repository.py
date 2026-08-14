from __future__ import annotations

import asyncio
import json

from knowledge_base.adapters.chunkers.text import MarkdownChunker, PlainTextChunker
from knowledge_base.adapters.document_stores.mongodb import MongoDocumentStore
from knowledge_base.adapters.github.client import GitHubSourceRepository
from knowledge_base.adapters.models.http import HttpEmbeddingProvider
from knowledge_base.adapters.parsers.text import MarkdownParser, PlainTextParser
from knowledge_base.adapters.vector_stores.memory import InMemoryVectorStore
from knowledge_base.application.file_classifier import FileClassifier
from knowledge_base.application.indexing_orchestrator import IndexingOrchestrator
from knowledge_base.application.indexing_service import IndexingService
from knowledge_base.settings import IndexWorkerSettings


async def run() -> None:
    settings = IndexWorkerSettings.from_env()
    documents = MongoDocumentStore(
        settings.mongodb_uri,
        settings.mongodb_database,
    )
    vectors = InMemoryVectorStore()
    embeddings = HttpEmbeddingProvider(
        base_url=settings.embedding_base_url,
        endpoint=settings.embedding_endpoint,
        model_id=settings.embedding_model_id,
        dimension=settings.embedding_dimension,
        api_key=settings.embedding_api_key,
    )
    source = GitHubSourceRepository(
        owner=settings.github_owner,
        repository=settings.github_repository,
        token=settings.github_token,
    )
    try:
        await documents.connect()
        await vectors.connect()
        indexing = IndexingService(
            document_store=documents,
            vector_store=vectors,
            embedding_provider=embeddings,
            collection_name=settings.vector_collection,
            index_version=settings.embedding_index_version,
        )
        orchestrator = IndexingOrchestrator(
            source_repository=source,
            document_store=documents,
            job_store=documents,
            indexing_service=indexing,
            classifier=FileClassifier(),
            parsers={"markdown": MarkdownParser(), "plain_text": PlainTextParser()},
            chunkers={
                "markdown": MarkdownChunker(),
                "plain_text": PlainTextChunker(),
            },
        )
        job = await orchestrator.run(
            base_commit=settings.github_base_commit,
            target_ref=settings.github_ref,
        )
        print(
            json.dumps(
                {
                    "job_id": job.id,
                    "status": job.status,
                    "target_commit": job.target_commit,
                    "files_scanned": job.files_scanned,
                    "documents_updated": job.documents_updated,
                    "chunks_created": job.chunks_created,
                }
            )
        )
    finally:
        await source.close()
        await embeddings.close()
        await vectors.close()
        await documents.close()


if __name__ == "__main__":
    asyncio.run(run())
