from __future__ import annotations

import hashlib
from collections.abc import Sequence

from knowledge_base.ports.llm_provider import ChatMessage


class FakeEmbeddingProvider:
    """Stable, local embeddings for unit tests; not intended for retrieval quality."""

    def __init__(self, dimension: int = 8, model_id: str = "fake-embedding") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.shake_256(text.encode("utf-8")).digest(self._dimension)
        return [(value - 127.5) / 127.5 for value in digest]


class FakeLLMProvider:
    def __init__(
        self,
        response: str = "fake response",
        model_id: str = "fake-llm",
    ) -> None:
        self.response = response
        self._model_id = model_id
        self.calls: list[tuple[tuple[ChatMessage, ...], float]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        temperature: float = 0.0,
    ) -> str:
        self.calls.append((tuple(messages), temperature))
        return self.response
