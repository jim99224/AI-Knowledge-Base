from pathlib import Path

from knowledge_base.config import SecretSettings, load_settings


def test_settings_load_yaml_and_build_database_url(tmp_path: Path) -> None:
    config_file = tmp_path / "app.yml"
    config_file.write_text(
        """
database:
  host: postgres.internal
  port: 5433
  name: kb_test
  echo: true
pgvector:
  enabled: true
age:
  enabled: true
  graph_name: test_graph
embedding:
  dimension: 768
""".strip(),
        encoding="utf-8",
    )

    secrets = SecretSettings(
        POSTGRES_USER="kb-user",
        POSTGRES_PASSWORD="p@ss word",
    )
    settings = load_settings(config_file, secrets=secrets)

    assert settings.database.host == "postgres.internal"
    assert settings.database.port == 5433
    assert settings.database.echo is True
    assert settings.pgvector.enabled is True
    assert settings.age.graph_name == "test_graph"
    assert settings.embedding.dimension == 768
    assert settings.database_url == (
        "postgresql+asyncpg://kb-user:p%40ss+word@postgres.internal:5433/kb_test"
    )
