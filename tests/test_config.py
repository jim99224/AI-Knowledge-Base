from knowledge_base.config import Settings


def test_settings_accept_database_url() -> None:
    settings = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/kb")

    assert settings.database_url.endswith("/kb")
    assert settings.pgvector_enabled is True
    assert settings.age_graph_name == "ai_knowledge_graph"
    assert settings.embedding_dimension == 1024
