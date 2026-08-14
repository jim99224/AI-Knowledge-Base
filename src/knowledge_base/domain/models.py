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


@dataclass(frozen=True, slots=True)
class Repository:
    id: str
    owner: str
    name: str
    default_branch: str = "main"
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
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_status: IndexStatus = IndexStatus.PENDING
    vector_index_version: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
