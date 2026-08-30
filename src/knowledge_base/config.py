from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    driver: str = "postgresql+asyncpg"
    host: str = "localhost"
    port: int = 5432
    name: str = "ai_knowledge_base"
    echo: bool = False
    pool_size: int = Field(default=10, gt=0)
    max_overflow: int = Field(default=20, ge=0)
    pool_pre_ping: bool = True


class PgVectorConfig(BaseModel):
    enabled: bool = True


class AgeConfig(BaseModel):
    enabled: bool = True
    graph_name: str = "ai_knowledge_graph"


class EmbeddingConfig(BaseModel):
    model_id: str = "text-embedding-model"
    dimension: int = Field(default=1024, gt=0)
    index_version: str = "embedding-v1"


class LLMConfig(BaseModel):
    model_id: str = "general-llm"


class KubernetesConfig(BaseModel):
    runtime_enabled: bool = False


class AppConfig(BaseModel):
    name: str = "ai-knowledge-base"


class SecretSettings(BaseSettings):
    """Sensitive values are read only from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")
    embedding_api_key: str | None = Field(default=None, alias="EMBEDDING_API_KEY")
    general_llm_api_key: str | None = Field(default=None, alias="GENERAL_LLM_API_KEY")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    pgvector: PgVectorConfig = Field(default_factory=PgVectorConfig)
    age: AgeConfig = Field(default_factory=AgeConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    kubernetes: KubernetesConfig = Field(default_factory=KubernetesConfig)
    secrets: SecretSettings

    @property
    def database_url(self) -> str:
        user = quote_plus(self.secrets.postgres_user)
        password = quote_plus(self.secrets.postgres_password)
        return (
            f"{self.database.driver}://{user}:{password}"
            f"@{self.database.host}:{self.database.port}/{self.database.name}"
        )


def load_settings(
    config_path: str | Path = "config/app.yml",
    secrets: SecretSettings | None = None,
) -> Settings:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}

    return Settings(**raw_config, secrets=secrets or SecretSettings())


@lru_cache
def get_settings() -> Settings:
    return load_settings()
