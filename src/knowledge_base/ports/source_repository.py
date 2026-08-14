from collections.abc import Sequence
from typing import Protocol

from knowledge_base.domain.models import FileChange, Repository, SourceFile


class SourceRepository(Protocol):
    async def get_repository(self) -> Repository: ...

    async def resolve_commit(self, ref: str) -> str: ...

    async def list_files(self, ref: str) -> Sequence[str]: ...

    async def compare(
        self, base_commit: str, target_commit: str
    ) -> Sequence[FileChange]: ...

    async def fetch_file(self, path: str, ref: str) -> SourceFile: ...
