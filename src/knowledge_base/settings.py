from __future__ import annotations

import os
from dataclasses import dataclass

from knowledge_base.domain.exceptions import ConfigurationError


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"required environment variable {name} is missing")
    return value


@dataclass(frozen=True, slots=True)
class IndexWorkerSettings:
    mongodb_uri: str
    mongodb_database: str
    github_owner: str
    github_repository: str
    github_token: str | None
    github_ref: str
    github_base_commit: str | None
    embedding_base_url: str
    embedding_endpoint: str
    embedding_model_id: str
    embedding_dimension: int
    embedding_api_key: str | None
    vector_collection: str
    embedding_index_version: str

    @classmethod
    def from_env(cls) -> IndexWorkerSettings:
        mongodb_uri = _required("MONGODB_URI")
        mongodb_database = _required("MONGODB_DATABASE")
        github_owner = _required("GITHUB_OWNER")
        github_repository = _required("GITHUB_REPOSITORY")
        embedding_base_url = _required("EMBEDDING_BASE_URL")
        embedding_model_id = _required("EMBEDDING_MODEL_ID")
        try:
            dimension = int(_required("EMBEDDING_DIMENSION"))
        except ValueError as error:
            raise ConfigurationError(
                "EMBEDDING_DIMENSION must be an integer"
            ) from error
        return cls(
            mongodb_uri=mongodb_uri,
            mongodb_database=mongodb_database,
            github_owner=github_owner,
            github_repository=github_repository,
            github_token=os.getenv("GITHUB_TOKEN") or None,
            github_ref=os.getenv("GITHUB_REF", "main"),
            github_base_commit=os.getenv("GITHUB_BASE_COMMIT") or None,
            embedding_base_url=embedding_base_url,
            embedding_endpoint=os.getenv("EMBEDDING_ENDPOINT", "/v1/embeddings"),
            embedding_model_id=embedding_model_id,
            embedding_dimension=dimension,
            embedding_api_key=os.getenv("EMBEDDING_API_KEY") or None,
            vector_collection=os.getenv("VECTOR_COLLECTION", "knowledge_chunks_v1"),
            embedding_index_version=os.getenv(
                "EMBEDDING_INDEX_VERSION", "embedding-v1"
            ),
        )
