import json

import httpx
import pytest

from app.agents.tutor import TutorContentAgent
from app.llm.client import MOCK_RESPONSE, LLMClient, LLMUnavailable


def transport_returning(payload: dict, status_code: int = 200) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status_code, json=payload))


async def test_mock_provider_needs_no_service():
    assert await LLMClient(provider="mock").generate("anything") == MOCK_RESPONSE


async def test_ollama_response_is_unwrapped():
    client = LLMClient(
        provider="ollama",
        model="test-model",
        transport=transport_returning({"response": "  Keep logging your meals.  "}),
    )
    assert await client.generate("prompt") == "Keep logging your meals."


async def test_ollama_sends_the_configured_model_and_prompt():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"response": "ok"})

    client = LLMClient(provider="ollama", model="test-model", transport=httpx.MockTransport(handler))
    await client.generate("my prompt")

    assert captured["model"] == "test-model"
    assert captured["prompt"] == "my prompt"
    assert captured["stream"] is False


async def test_empty_ollama_response_is_an_error():
    client = LLMClient(provider="ollama", transport=transport_returning({"response": "   "}))
    with pytest.raises(LLMUnavailable):
        await client.generate("prompt")


async def test_service_error_is_wrapped():
    client = LLMClient(provider="ollama", transport=transport_returning({}, status_code=500))
    with pytest.raises(LLMUnavailable):
        await client.generate("prompt")


async def test_unknown_provider_is_rejected():
    with pytest.raises(LLMUnavailable):
        await LLMClient(provider="gpt-9000").generate("prompt")


async def test_tutor_degrades_instead_of_failing_the_cycle(sample_profile):
    """The plan decision must survive an unavailable model — only the wording is lost."""
    tutor = TutorContentAgent(
        LLMClient(provider="ollama", transport=transport_returning({}, status_code=503))
    )
    assert await tutor.generate_content(sample_profile, "evening snacking", "dinner") is None
