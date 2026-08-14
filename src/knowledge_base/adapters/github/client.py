from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from knowledge_base.domain.exceptions import FullReconcileRequired
from knowledge_base.domain.models import (
    FileChange,
    FileChangeType,
    Repository,
    SourceFile,
)


class GitHubSourceRepository:
    """Read-only GitHub REST adapter for one configured repository."""

    def __init__(
        self,
        *,
        owner: str,
        repository: str,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.github.com",
    ) -> None:
        self.owner = owner
        self.repository = repository
        self.repository_id = f"{owner}/{repository}"
        self._owns_client = client is None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=30.0
        )

    async def get_repository(self) -> Repository:
        payload = await self._get_json(self._repo_path)
        return Repository(
            id=self.repository_id,
            owner=self.owner,
            name=self.repository,
            default_branch=payload["default_branch"],
        )

    async def resolve_commit(self, ref: str) -> str:
        payload = await self._get_json(
            f"{self._repo_path}/commits/{quote(ref, safe='')}"
        )
        return str(payload["sha"])

    async def list_files(self, ref: str) -> list[str]:
        payload = await self._get_json(
            f"{self._repo_path}/git/trees/{quote(ref, safe='')}?recursive=1"
        )
        if payload.get("truncated"):
            raise RuntimeError("GitHub recursive tree response was truncated")
        return [
            str(item["path"])
            for item in payload.get("tree", [])
            if item.get("type") == "blob"
        ]

    async def compare(self, base_commit: str, target_commit: str) -> list[FileChange]:
        comparison = f"{quote(base_commit, safe='')}...{quote(target_commit, safe='')}"
        payload = await self._get_json(f"{self._repo_path}/compare/{comparison}")
        if len(payload.get("files", [])) >= 300:
            raise FullReconcileRequired(
                "GitHub compare reached the 300-file API limit; run full reconcile"
            )
        changes: list[FileChange] = []
        for item in payload.get("files", []):
            status = str(item["status"])
            change_type = {
                "added": FileChangeType.ADDED,
                "modified": FileChangeType.MODIFIED,
                "removed": FileChangeType.DELETED,
                "renamed": FileChangeType.RENAMED,
            }.get(status, FileChangeType.MODIFIED)
            changes.append(
                FileChange(
                    path=str(item["filename"]),
                    change_type=change_type,
                    previous_path=item.get("previous_filename"),
                )
            )
        return changes

    async def fetch_file(self, path: str, ref: str) -> SourceFile:
        encoded_path = quote(path, safe="/")
        response = await self._client.get(
            f"{self._repo_path}/contents/{encoded_path}",
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        response.raise_for_status()
        return SourceFile(self.repository_id, path, ref, response.text)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def _repo_path(self) -> str:
        return f"/repos/{quote(self.owner, safe='')}/{quote(self.repository, safe='')}"

    async def _get_json(self, path: str) -> dict[str, Any]:
        response = await self._client.get(path)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return payload
