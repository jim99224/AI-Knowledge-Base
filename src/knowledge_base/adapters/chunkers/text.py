from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from knowledge_base.domain.models import Chunk, Document

_TOKEN_PATTERN = re.compile(r"(?:[\u3400-\u9fff]|[^\s\u3400-\u9fff]+)\s*")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class _Block:
    content: str
    heading_path: tuple[str, ...]
    structural_key: str
    start_line: int
    end_line: int


class PlainTextChunker:
    version = "plain-text-v1"

    def __init__(self, max_tokens: int = 800, overlap_tokens: int = 100) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be between zero and max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, document: Document) -> list[Chunk]:
        block = _Block(
            content=document.raw_text,
            heading_path=(),
            structural_key="document",
            start_line=1,
            end_line=max(1, len(document.raw_text.splitlines())),
        )
        return self._chunks_from_blocks(document, [block])

    def _chunks_from_blocks(
        self, document: Document, blocks: list[_Block]
    ) -> list[Chunk]:
        pending: list[tuple[_Block, str, int]] = []
        for block in blocks:
            parts = self._split_tokens(block.content)
            pending.extend((block, part, index) for index, part in enumerate(parts))

        chunks: list[Chunk] = []
        part_counts: dict[str, int] = {}
        for block, _, _ in pending:
            part_counts[block.structural_key] = (
                part_counts.get(block.structural_key, 0) + 1
            )
        for chunk_index, (block, content, part_index) in enumerate(pending):
            chunk_id = _digest(
                ":".join(
                    (
                        document.id,
                        block.structural_key,
                        str(part_index),
                        self.version,
                    )
                )
            )
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document.id,
                    repository_id=document.repository_id,
                    chunk_index=chunk_index,
                    content=content,
                    content_hash=_digest(content),
                    commit_sha=document.commit_sha,
                    heading_path=block.heading_path,
                    token_count=self.count_tokens(content),
                    start_line=block.start_line,
                    end_line=block.end_line,
                    structural_key=block.structural_key,
                    chunker_version=self.version,
                    part_index=part_index,
                    part_count=part_counts[block.structural_key],
                    metadata={"path": document.path},
                )
            )
        return chunks

    def _split_tokens(self, text: str) -> list[str]:
        tokens = _TOKEN_PATTERN.findall(text)
        if not tokens:
            return []
        parts: list[str] = []
        step = self.max_tokens - self.overlap_tokens
        for start in range(0, len(tokens), step):
            part = "".join(tokens[start : start + self.max_tokens]).strip()
            if part:
                parts.append(part)
            if start + self.max_tokens >= len(tokens):
                break
        return parts

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(_TOKEN_PATTERN.findall(text))


class MarkdownChunker(PlainTextChunker):
    version = "markdown-heading-v1"

    def chunk(self, document: Document) -> list[Chunk]:
        return self._chunks_from_blocks(
            document, self._parse_sections(document.raw_text)
        )

    @staticmethod
    def _parse_sections(text: str) -> list[_Block]:
        lines = text.splitlines()
        if not lines:
            return []
        headings: list[str] = []
        blocks: list[_Block] = []
        current_lines: list[str] = []
        current_path: tuple[str, ...] = ()
        start_line = 1

        def flush(end_line: int) -> None:
            content = "\n".join(current_lines).strip()
            if not content:
                return
            key = (
                f"heading:{'/'.join(current_path)}@{start_line}"
                if current_path
                else "preamble"
            )
            blocks.append(
                _Block(
                    content, current_path, key, start_line, max(start_line, end_line)
                )
            )

        for line_number, line in enumerate(lines, start=1):
            match = _HEADING_PATTERN.match(line)
            if not match:
                current_lines.append(line)
                continue
            flush(line_number - 1)
            level = len(match.group(1))
            title = match.group(2).strip()
            headings[level - 1 :] = [title]
            current_path = tuple(headings)
            current_lines = [line]
            start_line = line_number
        flush(len(lines))
        return blocks
