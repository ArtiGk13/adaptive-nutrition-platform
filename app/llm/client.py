import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# A fixed string is returned whatever the prompt, so it must not assert anything about
# the user. An earlier version congratulated them on their consistency, which contradicted
# the assessment whenever adherence was poor.
MOCK_RESPONSE = (
    "Explanatory text is not generated in this configuration. The assessment and the "
    "decision it accompanies are unaffected."
)


class LLMUnavailable(RuntimeError):
    """The configured language model could not be reached or returned nothing usable."""


class LLMClient:
    """Thin wrapper isolating non-deterministic text generation from the core logic.

    Only the Tutor/Content agent uses this; plan calculations, adaptation rules and
    guardrails stay deterministic in code.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._transport = transport

    # Resolved per call rather than at construction: clients are built once at import time,
    # so caching here would freeze whatever configuration happened to be loaded first.
    @property
    def provider(self) -> str:
        return self._provider or settings.llm_provider

    @property
    def model(self) -> str:
        return self._model or settings.llm_model

    async def generate(self, prompt: str) -> str:
        if self.provider == "mock":
            return MOCK_RESPONSE
        if self.provider == "ollama":
            return await self._generate_ollama(prompt)
        raise LLMUnavailable(
            f"LLM provider '{self.provider}' is not supported. "
            "Set LLM_PROVIDER to 'ollama' or 'mock' in .env."
        )

    async def _generate_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": settings.llm_temperature,
                "num_predict": settings.llm_max_tokens,
            },
        }
        try:
            async with httpx.AsyncClient(
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
                text = response.json().get("response", "").strip()
        except httpx.HTTPError as error:
            raise LLMUnavailable(f"Ollama request failed: {error}") from error

        if not text:
            raise LLMUnavailable("Ollama returned an empty response.")
        return text
