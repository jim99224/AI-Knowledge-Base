from typing import Protocol

from knowledge_base.domain.models import Chunk, Document


class Chunker(Protocol):
    @property
    def version(self) -> str: ...

    def chunk(self, document: Document) -> list[Chunk]: ...
