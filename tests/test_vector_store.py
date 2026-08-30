import pytest

from knowledge_base.adapters.postgres.vector_store import PgVectorStore


class EmptySessionFactory:
    def __call__(self):
        raise AssertionError("database session should not be opened for top_k <= 0")


@pytest.mark.asyncio
async def test_vector_search_skips_db_for_non_positive_top_k() -> None:
    store = PgVectorStore(EmptySessionFactory())  # type: ignore[arg-type]

    assert await store.search([0.1, 0.2], top_k=0) == []
