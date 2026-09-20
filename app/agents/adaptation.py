from app.agents.assessment import BIAS_THRESHOLD
from app.domain.assessment import AssessmentFlag, AssessmentResult
from app.domain.decisions import ActionType, AdaptationAction
from app.domain.nutrition_plan import (
    NutritionPlan,
    build_meal_structure,
    calculate_calorie_target,
    calculate_macro_targets,
)
from app.domain.user_profile import GoalType, UserProfile

MAX_ADJUSTMENT_RATIO = 0.10
NEGLIGIBLE_CHANGE_RATIO = 0.03


class AdaptationAgent:
    """Rule-based selection of the next action. Deterministic, no LLM."""

    async def decide(
        self, profile: UserProfile, plan: NutritionPlan, assessment: AssessmentResult
    ) -> AdaptationAction:
        if assessment.proposed_flag == AssessmentFlag.REFER_SPECIALIST:
            return AdaptationAction(
                action_type=ActionType.REFER_SPECIALIST,
                reason="Η αξιολόγηση υποδεικνύει ανάγκη παραπομπής σε ειδικό.",
            )

        if assessment.proposed_flag == AssessmentFlag.EXTRA_SUPPORT:
            return AdaptationAction(
                action_type=ActionType.EXTRA_SUPPORT,
                reason="Χαμηλή τήρηση ή ελλιπής καταγραφή — απαιτείται επιπλέον υποστήριξη.",
            )

        sustainable = self._update_sustainable_target(profile, plan, assessment)
        desired_target, rationale = self._desired_target(profile, sustainable)
        delta = desired_target - plan.calorie_target

        if abs(delta) / plan.calorie_target < NEGLIGIBLE_CHANGE_RATIO:
            return AdaptationAction(
                action_type=ActionType.CONTINUE,
                reason="Ο τρέχων θερμιδικός στόχος παραμένει κατάλληλος — διατήρηση του πλάνου.",
            )

        new_target = self._bounded_target(plan.calorie_target, delta)
        return AdaptationAction(
            action_type=ActionType.ADJUST_PLAN,
            reason=(
                f"Προσαρμογή θερμιδικού στόχου από {plan.calorie_target} σε {new_target} kcal "
                f"({rationale})."
            ),
            new_plan=self._rebuild_plan(profile, plan, new_target, sustainable),
        )

    def _update_sustainable_target(
        self, profile: UserProfile, plan: NutritionPlan, assessment: AssessmentResult
    ) -> int | None:
        """Learn (or forget) what this user can actually sustain.

        A steady deviation in the demanding direction is evidence that the plan asks for
        more than the user can hold; a steady deviation the other way is evidence that the
        limit learned earlier was too generous.
        """
        if profile.goal_type == GoalType.MAINTENANCE:
            return None

        bias_ratio = (assessment.average_daily_kcal - plan.calorie_target) / plan.calorie_target
        too_demanding = (
            bias_ratio > BIAS_THRESHOLD
            if profile.goal_type == GoalType.WEIGHT_LOSS
            else bias_ratio < -BIAS_THRESHOLD
        )
        if too_demanding:
            return round(assessment.average_daily_kcal)
        if abs(bias_ratio) > BIAS_THRESHOLD:
            return None
        return plan.sustainable_target_kcal

    def _desired_target(
        self, profile: UserProfile, sustainable_target: int | None
    ) -> tuple[float, str]:
        """The goal-anchored target, never harder than what the user has shown they sustain.

        Re-anchoring on the goal uses the user's *current* weight, which recovers the
        deficit that a falling metabolic rate would otherwise erase.
        """
        goal_target = float(calculate_calorie_target(profile))
        if sustainable_target is None:
            return goal_target, "επαναϋπολογισμός βάσει τρέχοντος βάρους"

        if profile.goal_type == GoalType.WEIGHT_LOSS:
            desired = max(goal_target, float(sustainable_target))
        else:
            desired = min(goal_target, float(sustainable_target))

        if desired != goal_target:
            return desired, f"προσαρμογή στο βιώσιμο επίπεδο {sustainable_target} kcal"
        return desired, "επαναϋπολογισμός βάσει τρέχοντος βάρους"

    def _bounded_target(self, current_target: int, delta: float) -> int:
        max_step = current_target * MAX_ADJUSTMENT_RATIO
        return round(current_target + max(-max_step, min(max_step, delta)))

    def _rebuild_plan(
        self,
        profile: UserProfile,
        plan: NutritionPlan,
        new_target: int,
        sustainable_target: int | None,
    ) -> NutritionPlan:
        return NutritionPlan(
            user_id=plan.user_id,
            calorie_target=new_target,
            macro_targets=calculate_macro_targets(new_target, profile),
            meal_structure=build_meal_structure(new_target),
            rationale=f"Αναπροσαρμογή πλάνου έκδοσης {plan.version} βάσει καταγεγραμμένης πρόσληψης.",
            sustainable_target_kcal=sustainable_target,
        )
