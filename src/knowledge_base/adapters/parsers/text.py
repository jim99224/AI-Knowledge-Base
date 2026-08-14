from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from knowledge_base.domain.models import Document, SourceFile


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PlainTextParser:
    document_type = "plain_text"

    def parse(self, source: SourceFile) -> Document:
        return Document(
            id=_digest(f"{source.repository_id}:{source.path}"),
            repository_id=source.repository_id,
            path=source.path,
            title=PurePosixPath(source.path).name,
            document_type=self.document_type,
            branch=source.ref,
            commit_sha=source.ref,
            content_hash=_digest(source.content),
            raw_text=source.content,
        )


class MarkdownParser(PlainTextParser):
    document_type = "markdown"
