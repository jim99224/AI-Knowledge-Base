import httpx
import pytest

from knowledge_base.adapters.models.fake import FakeEmbeddingProvider, FakeLLMProvider
from knowledge_base.adapters.models.http import HttpEmbeddingProvider, HttpLLMProvider
from knowledge_base.domain.exceptions import DimensionMismatchError
from knowledge_base.ports.llm_provider import ChatMessage


async def test_fake_models_are_deterministic_and_record_calls() -> None:
    embeddings = FakeEmbeddingProvider(dimension=4)
    assert await embeddings.embed_query("same") == await embeddings.embed_query("same")

    llm = FakeLLMProvider(response="answer")
    result = await llm.generate([ChatMessage("user", "question")])
    assert result == "answer"
    assert len(llm.calls) == 1


async def test_http_embedding_adapter_parses_compatible_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://model"
    )
    provider = HttpEmbeddingProvider(
        base_url="http://model", model_id="embed", dimension=2, client=client
    )
    assert await provider.embed_query("hello") == [0.1, 0.2]
    await client.aclose()


async def test_http_embedding_adapter_validates_dimension() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": [{"embedding": [0.1]}]})
        ),
        base_url="http://model",
    )
    provider = HttpEmbeddingProvider(
        base_url="http://model", model_id="embed", dimension=2, client=client
    )
    with pytest.raises(DimensionMismatchError):
        await provider.embed_query("hello")
    await client.aclose()


async def test_http_llm_adapter_parses_compatible_response() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "grounded answer"}}]},
            )
        ),
        base_url="http://model",
    )
    provider = HttpLLMProvider(base_url="http://model", model_id="llm", client=client)
    result = await provider.generate([ChatMessage("user", "question")])
    assert result == "grounded answer"
    await client.aclose()
