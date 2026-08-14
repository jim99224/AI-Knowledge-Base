from typing import Protocol

from knowledge_base.domain.models import Document, SourceFile


class DocumentParser(Protocol):
    @property
    def document_type(self) -> str: ...

    def parse(self, source: SourceFile) -> Document: ...
