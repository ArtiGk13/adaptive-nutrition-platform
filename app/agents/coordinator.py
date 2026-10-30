from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.adaptation import AdaptationAgent
from app.agents.assessment import AssessmentAgent
from app.agents.planner import PlannerAgent
from app.agents.supervisor import SupervisorAgent
from app.agents.tutor import TutorContentAgent
from app.db import repository
from app.domain.assessment import AssessmentResult
from app.domain.decisions import ActionType, AdaptationAction, SupervisorDecision
from app.domain.log_entry import WeightLogEntry
from app.domain.nutrition_plan import NutritionPlan
from app.domain.user_profile import UserProfile
from app.llm.client import LLMClient


@dataclass
class CycleResult:
    plan: NutritionPlan
    assessment: AssessmentResult
    action: AdaptationAction
    decision: SupervisorDecision
    feedback_text: str | None = None
    support_text: str | None = None


class Coordinator:
    """Sequential pipeline over the five agents. State is passed explicitly."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.planner = PlannerAgent()
        self.assessor = AssessmentAgent()
        self.adapter = AdaptationAgent()
        self.tutor = TutorContentAgent(llm_client)
        self.supervisor = SupervisorAgent()

    async def run_onboarding(
        self, session: Session, profile: UserProfile
    ) -> tuple[NutritionPlan | None, SupervisorDecision]:
        plan = await self.planner.create_initial_plan(profile)
        decision = await self.supervisor.validate_plan(plan, profile)
        repository.save_decision(session, decision)

        if not decision.approved:
            return None, decision

        saved_plan = repository.save_plan(session, plan, decision)
        return saved_plan, decision

    async def run_cycle(self, session: Session, user_id: int) -> CycleResult:
        profile, plan, logs = repository.load_state(session, user_id)
        if profile is None:
            raise LookupError(f"User {user_id} not found.")
        if plan is None:
            raise LookupError(f"User {user_id} has no active plan.")

        self._sync_weight(session, profile, logs)

        assessment = await self.assessor.evaluate(profile, plan, logs)
        action = await self.adapter.decide(profile, plan, assessment)
        decision = await self.supervisor.review(action, profile, logs)

        repository.save_assessment(session, assessment)
        repository.save_decision(session, decision)
        repository.update_user_adherence(
            session, user_id, assessment.adherence_score, assessment.detected_difficulties
        )

        resulting_plan = plan
        if decision.approved and action.requires_change:
            resulting_plan = repository.save_plan(session, action.new_plan, decision)

        feedback_text = None
        if action.needs_explanation:
            feedback_text = await self.tutor.generate_feedback(action, assessment)

        return CycleResult(
            plan=resulting_plan,
            assessment=assessment,
            action=action,
            decision=decision,
            feedback_text=feedback_text,
            support_text=await self._support(profile, action, assessment, resulting_plan),
        )

    async def _support(self, profile, action, assessment, plan) -> str | None:
        """The content the Tutor offers when the chosen action is to offer support.

        Without this the action named support and delivered none: the agent could write
        it, and nothing asked it to. The slot passed is the largest in the plan, where a
        change to a meal makes the most difference to a day; that is a presentational
        choice and carries no clinical claim.
        """
        if action.action_type != ActionType.EXTRA_SUPPORT:
            return None
        if not assessment.detected_difficulties or plan is None:
            return None
        slot = max(plan.meal_structure, key=lambda s: s.target_kcal, default=None)
        if slot is None:
            return None
        return await self.tutor.generate_content(
            profile, assessment.detected_difficulties[0], slot.slot_name
        )

    def _sync_weight(self, session: Session, profile: UserProfile, logs: list) -> None:
        """Guardrails and calorie targets are only as safe as the weight they are based on."""
        weight_logs = [entry for entry in logs if isinstance(entry, WeightLogEntry)]
        if not weight_logs:
            return

        latest = max(weight_logs, key=lambda entry: entry.timestamp)
        if abs(latest.weight_kg - profile.weight_kg) < 0.1:
            return

        profile.weight_kg = latest.weight_kg
        repository.update_user_weight(session, profile.user_id, latest.weight_kg)
