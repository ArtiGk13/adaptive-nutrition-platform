from datetime import datetime, timezone

import pytest

from app.agents.adaptation import MAX_ADJUSTMENT_RATIO, AdaptationAgent
from app.domain.assessment import AssessmentFlag, AssessmentResult
from app.domain.decisions import ActionType
from app.domain.nutrition_plan import (
    MacroTargets,
    MealSlot,
    NutritionPlan,
    calculate_calorie_target,
)


@pytest.fixture
def plan(sample_profile) -> NutritionPlan:
    """A plan consistent with the profile — i.e. what the Planner would have produced."""
    target = calculate_calorie_target(sample_profile)
    return NutritionPlan(
        plan_id=1,
        user_id=1,
        calorie_target=target,
        macro_targets=MacroTargets(protein_g=130, carbs_g=159, fat_g=50),
        meal_structure=[MealSlot(slot_name="lunch", target_kcal=round(target * 0.35))],
        rationale="test plan",
    )


def build_assessment(flag: AssessmentFlag, average_daily_kcal: float) -> AssessmentResult:
    return AssessmentResult(
        user_id=1,
        plan_id=1,
        timestamp=datetime.now(timezone.utc),
        adherence_score=0.6,
        average_daily_kcal=average_daily_kcal,
        proposed_flag=flag,
    )


async def test_on_target_user_keeps_current_plan(sample_profile, plan):
    action = await AdaptationAgent().decide(
        sample_profile, plan, build_assessment(AssessmentFlag.CONTINUE, plan.calorie_target)
    )
    assert action.action_type == ActionType.CONTINUE
    assert not action.requires_change


async def test_systematic_bias_converges_target_toward_actual_intake(sample_profile, plan):
    observed = round(plan.calorie_target * 1.09)
    action = await AdaptationAgent().decide(
        sample_profile, plan, build_assessment(AssessmentFlag.ADJUST, observed)
    )
    assert action.action_type == ActionType.ADJUST_PLAN
    assert action.new_plan.calorie_target == observed


async def test_adjustment_step_is_bounded(sample_profile, plan):
    action = await AdaptationAgent().decide(
        sample_profile, plan, build_assessment(AssessmentFlag.ADJUST, plan.calorie_target * 2)
    )
    max_target = plan.calorie_target * (1 + MAX_ADJUSTMENT_RATIO)
    assert action.new_plan.calorie_target == pytest.approx(max_target, abs=1)


async def test_plan_is_rebaselined_after_weight_loss(sample_profile, plan):
    """A compliant user whose weight dropped needs a lower target, or progress stalls."""
    sample_profile.weight_kg -= 6.0
    action = await AdaptationAgent().decide(
        sample_profile, plan, build_assessment(AssessmentFlag.CONTINUE, plan.calorie_target)
    )
    assert action.action_type == ActionType.ADJUST_PLAN
    assert action.new_plan.calorie_target < plan.calorie_target
    assert action.new_plan.calorie_target >= calculate_calorie_target(sample_profile)


async def test_extra_support_flag_requests_support_without_plan_change(sample_profile, plan):
    action = await AdaptationAgent().decide(
        sample_profile, plan, build_assessment(AssessmentFlag.EXTRA_SUPPORT, 900)
    )
    assert action.action_type == ActionType.EXTRA_SUPPORT
    assert not action.requires_change
    assert action.needs_explanation
