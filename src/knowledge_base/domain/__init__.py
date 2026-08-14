"""Domain objects shared by application services and adapters."""

from knowledge_base.domain.models import Chunk, Document, IndexStatus, Repository

__all__ = ["Chunk", "Document", "IndexStatus", "Repository"]
