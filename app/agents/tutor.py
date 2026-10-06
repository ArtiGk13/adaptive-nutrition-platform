import logging

from app.domain.assessment import AssessmentResult
from app.domain.decisions import AdaptationAction
from app.domain.user_profile import UserProfile
from app.llm.client import LLMClient, LLMUnavailable
from app.llm.prompts import CONTENT_PROMPT, FEEDBACK_PROMPT

logger = logging.getLogger(__name__)


class TutorContentAgent:
    """The only agent that uses the LLM — phrasing feedback and educational content."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    async def generate_feedback(
        self, action: AdaptationAction, assessment: AssessmentResult
    ) -> str | None:
        prompt = FEEDBACK_PROMPT.format(
            action_type=action.action_type.value,
            reason=action.reason,
            adherence_score=assessment.adherence_score,
            deviations="; ".join(assessment.deviations) or "none",
        )
        return await self._generate(prompt)

    async def generate_content(
        self, profile: UserProfile, difficulty: str, meal_slot: str
    ) -> str | None:
        prompt = CONTENT_PROMPT.format(
            difficulty=difficulty,
            goal_type=profile.goal_type.value,
            meal_slot=meal_slot,
        )
        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> str | None:
        """Wording is optional: a cycle must still complete when the model is unavailable."""
        try:
            return await self.llm.generate(prompt)
        except LLMUnavailable as error:
            logger.warning("Falling back to no generated text: %s", error)
            return None
