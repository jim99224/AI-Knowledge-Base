import pytest

from knowledge_base.domain.exceptions import ConfigurationError
from knowledge_base.settings import IndexWorkerSettings


def test_index_worker_settings_load_required_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "MONGODB_URI": "mongodb://db.example/kb",
        "MONGODB_DATABASE": "kb",
        "GITHUB_OWNER": "acme",
        "GITHUB_REPOSITORY": "orders",
        "EMBEDDING_BASE_URL": "http://embedding",
        "EMBEDDING_MODEL_ID": "embed-v1",
        "EMBEDDING_DIMENSION": "4",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = IndexWorkerSettings.from_env()

    assert settings.github_ref == "main"
    assert settings.embedding_dimension == 4
    assert settings.vector_collection == "knowledge_chunks_v1"


def test_index_worker_settings_reject_missing_required_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)

    with pytest.raises(ConfigurationError, match="MONGODB_URI"):
        IndexWorkerSettings.from_env()
