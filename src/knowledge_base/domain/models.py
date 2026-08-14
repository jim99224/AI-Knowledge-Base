"""Storage-agnostic domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


class IndexStatus(StrEnum):
    PENDING = "pending"
    EMBEDDING = "embedding"
    VECTOR_UPSERT = "vector_upsert"
    INDEXED = "indexed"
    FAILED = "failed"


class IndexJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FileChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True, slots=True)
class Repository:
    id: str
    owner: str
    name: str
    default_branch: str = "main"
    last_indexed_commit: str | None = None
    enabled: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    repository_id: str
    path: str
    title: str
    document_type: str
    branch: str
    commit_sha: str
    content_hash: str
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    index_status: IndexStatus = IndexStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    repository_id: str
    chunk_index: int
    content: str
    content_hash: str
    commit_sha: str
    heading_path: tuple[str, ...] = ()
    token_count: int = 0
    start_line: int | None = None
    end_line: int | None = None
    structural_key: str = "document"
    chunker_version: str = "1"
    part_index: int = 0
    part_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_status: IndexStatus = IndexStatus.PENDING
    vector_index_version: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class SourceFile:
    repository_id: str
    path: str
    ref: str
    content: str


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    change_type: FileChangeType
    previous_path: str | None = None


@dataclass(frozen=True, slots=True)
class IndexJob:
    id: str
    repository_id: str
    target_commit: str
    base_commit: str | None = None
    status: IndexJobStatus = IndexJobStatus.PENDING
    files_scanned: int = 0
    documents_updated: int = 0
    chunks_created: int = 0
    retry_count: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
