from app.domain.assessment import AssessmentResult
from app.domain.decisions import AdaptationAction
from app.llm.client import LLMClient
from app.llm.prompts import CONTENT_PROMPT, FEEDBACK_PROMPT
from app.domain.user_profile import UserProfile


class TutorContentAgent:
    """The only agent that uses the LLM — phrasing feedback and educational content."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    async def generate_feedback(
        self, action: AdaptationAction, assessment: AssessmentResult
    ) -> str:
        prompt = FEEDBACK_PROMPT.format(
            action_type=action.action_type.value,
            reason=action.reason,
            adherence_score=assessment.adherence_score,
            deviations="; ".join(assessment.deviations) or "καμία",
        )
        return await self.llm.generate(prompt)

    async def generate_content(
        self, profile: UserProfile, difficulty: str, meal_slot: str
    ) -> str:
        prompt = CONTENT_PROMPT.format(
            difficulty=difficulty,
            goal_type=profile.goal_type.value,
            meal_slot=meal_slot,
        )
        return await self.llm.generate(prompt)
