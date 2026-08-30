from knowledge_base.domain.models import Base


def test_expected_tables_are_registered() -> None:
    assert {"repositories", "documents", "chunks", "index_jobs"}.issubset(Base.metadata.tables)
