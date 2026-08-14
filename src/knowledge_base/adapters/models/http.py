from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from knowledge_base.domain.exceptions import ConfigurationError, DimensionMismatchError
from knowledge_base.ports.llm_provider import ChatMessage


def _headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


class HttpEmbeddingProvider:
    """Adapter for an OpenAI-compatible embeddings endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model_id: str,
        dimension: int,
        endpoint: str = "/v1/embeddings",
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        if dimension <= 0:
            raise ConfigurationError("embedding dimension must be positive")
        self._model_id = model_id
        self._dimension = dimension
        self._endpoint = endpoint
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=_headers(api_key), timeout=timeout
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.post(
            self._endpoint, json={"model": self.model_id, "input": list(texts)}
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        data = sorted(payload["data"], key=lambda item: item.get("index", 0))
        vectors = [[float(value) for value in item["embedding"]] for item in data]
        if len(vectors) != len(texts):
            raise ValueError("embedding response count does not match input count")
        for vector in vectors:
            if len(vector) != self.dimension:
                raise DimensionMismatchError(
                    f"model returned dimension {len(vector)}, expected {self.dimension}"
                )
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> HttpEmbeddingProvider:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


class HttpLLMProvider:
    """Adapter for an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model_id: str,
        endpoint: str = "/v1/chat/completions",
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._model_id = model_id
        self._endpoint = endpoint
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=_headers(api_key), timeout=timeout
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        temperature: float = 0.0,
    ) -> str:
        response = await self._client.post(
            self._endpoint,
            json={
                "model": self.model_id,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("LLM response content must be a string")
        return content

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> HttpLLMProvider:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
