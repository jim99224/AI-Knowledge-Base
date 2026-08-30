from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    pgvector_enabled: bool = Field(default=True, alias="PGVECTOR_ENABLED")
    age_enabled: bool = Field(default=True, alias="AGE_ENABLED")
    age_graph_name: str = Field(default="ai_knowledge_graph", alias="AGE_GRAPH_NAME")
    embedding_dimension: int = Field(default=1024, alias="EMBEDDING_DIMENSION", gt=0)
    embedding_index_version: str = Field(default="embedding-v1", alias="EMBEDDING_INDEX_VERSION")
    general_llm_model_id: str = Field(default="general-llm", alias="GENERAL_LLM_MODEL_ID")
    kubernetes_runtime_enabled: bool = Field(default=False, alias="KUBERNETES_RUNTIME_ENABLED")


@lru_cache
def get_settings() -> Settings:
    return Settings()
