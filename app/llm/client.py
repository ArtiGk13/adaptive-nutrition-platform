from app.config import settings

MOCK_RESPONSE = (
    "You are keeping up with your plan consistently. Stay at this pace and keep "
    "logging your meals the way you did this week."
)


class LLMClient:
    """Thin wrapper isolating non-deterministic text generation from the core logic.

    Only the Tutor/Content agent uses this; plan calculations, adaptation rules and
    guardrails stay deterministic in code.
    """

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.provider = provider or settings.llm_provider
        self.model = model or settings.llm_model

    async def generate(self, prompt: str) -> str:
        if self.provider == "mock":
            return MOCK_RESPONSE
        raise NotImplementedError(
            f"LLM provider '{self.provider}' is not wired up yet. "
            "Add the provider call here and set LLM_PROVIDER in .env."
        )
