import pytest

from knowledge_base.adapters.vector_stores.memory import InMemoryVectorStore
from knowledge_base.domain.exceptions import DimensionMismatchError
from knowledge_base.ports.vector_store import VectorRecord


async def test_search_ranks_and_filters_records() -> None:
    store = InMemoryVectorStore()
    await store.connect()
    await store.ensure_collection("chunks", 2)
    await store.upsert(
        "chunks",
        [
            VectorRecord("a", [1.0, 0.0], {"repository_id": "one"}),
            VectorRecord("b", [0.0, 1.0], {"repository_id": "two"}),
        ],
    )

    matches = await store.search(
        "chunks", [0.9, 0.1], top_k=5, filters={"repository_id": "one"}
    )

    assert [match.id for match in matches] == ["a"]
    assert matches[0].score > 0.9


async def test_dimension_mismatch_is_rejected() -> None:
    store = InMemoryVectorStore()
    await store.connect()
    await store.ensure_collection("chunks", 2)

    with pytest.raises(DimensionMismatchError):
        await store.upsert("chunks", [VectorRecord("a", [1.0], {})])
