import json

import httpx

from knowledge_base.adapters.github.client import GitHubSourceRepository
from knowledge_base.domain.models import FileChangeType


async def test_github_adapter_resolves_repository_diff_and_raw_file() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/acme/orders":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/acme/orders/commits/main":
            return httpx.Response(200, json={"sha": "target-sha"})
        if path == "/repos/acme/orders/compare/base...target-sha":
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"filename": "README.md", "status": "modified"},
                        {"filename": "old.md", "status": "removed"},
                    ]
                },
            )
        if path == "/repos/acme/orders/contents/README.md":
            assert request.url.params["ref"] == "target-sha"
            return httpx.Response(200, text="# Orders")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.test"
    )
    source = GitHubSourceRepository(owner="acme", repository="orders", client=client)

    repository = await source.get_repository()
    target = await source.resolve_commit("main")
    changes = await source.compare("base", target)
    file = await source.fetch_file("README.md", target)

    assert repository.id == "acme/orders"
    assert target == "target-sha"
    assert [change.change_type for change in changes] == [
        FileChangeType.MODIFIED,
        FileChangeType.DELETED,
    ]
    assert file.content == "# Orders"
    await client.aclose()


async def test_github_adapter_rejects_truncated_recursive_tree() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=json.dumps({"truncated": True, "tree": []})
            )
        ),
        base_url="https://api.github.test",
    )
    source = GitHubSourceRepository(owner="acme", repository="orders", client=client)

    try:
        await source.list_files("abc123")
    except RuntimeError as error:
        assert "truncated" in str(error)
    else:
        raise AssertionError("expected a truncated tree failure")
    await client.aclose()
