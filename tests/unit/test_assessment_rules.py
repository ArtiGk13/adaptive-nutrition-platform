from datetime import datetime, timedelta, timezone

import pytest

from app.agents.assessment import ASSESSMENT_WINDOW_DAYS, AssessmentAgent
from app.domain.assessment import AssessmentFlag
from app.domain.log_entry import MealLogEntry
from app.domain.nutrition_plan import MacroTargets, MealSlot, NutritionPlan


@pytest.fixture
def plan() -> NutritionPlan:
    return NutritionPlan(
        plan_id=1,
        user_id=1,
        calorie_target=2000,
        macro_targets=MacroTargets(protein_g=130, carbs_g=200, fat_g=62),
        meal_structure=[MealSlot(slot_name="lunch", target_kcal=700)],
        rationale="test plan",
    )


def logs(daily_kcal: int, days: int, offset_days: int = 0) -> list[MealLogEntry]:
    now = datetime.now(timezone.utc)
    return [
        MealLogEntry(
            user_id=1,
            timestamp=now - timedelta(days=offset_days + day),
            meal_slot="lunch",
            food_description="test",
            estimated_kcal=daily_kcal,
        )
        for day in range(days)
    ]


async def test_no_logs_requests_extra_support(sample_profile, plan):
    result = await AssessmentAgent().evaluate(sample_profile, plan, [])
    assert result.proposed_flag == AssessmentFlag.EXTRA_SUPPORT
    assert result.adherence_score == 0.0


async def test_on_target_logs_continue(sample_profile, plan):
    result = await AssessmentAgent().evaluate(sample_profile, plan, logs(2000, 7))
    assert result.proposed_flag == AssessmentFlag.CONTINUE
    assert result.average_daily_kcal == 2000


async def test_small_steady_overshoot_triggers_adjustment(sample_profile, plan):
    """Adherence still scores as acceptable, but the gap is one-directional."""
    result = await AssessmentAgent().evaluate(sample_profile, plan, logs(2200, 7))
    assert result.adherence_score >= 0.8
    assert result.proposed_flag == AssessmentFlag.ADJUST


async def test_severe_deviation_requests_extra_support(sample_profile, plan):
    result = await AssessmentAgent().evaluate(sample_profile, plan, logs(3200, 7))
    assert result.proposed_flag == AssessmentFlag.EXTRA_SUPPORT


async def test_only_recent_logs_are_evaluated(sample_profile, plan):
    stale = logs(3000, 7, offset_days=ASSESSMENT_WINDOW_DAYS + 5)
    recent = logs(2000, 7)
    result = await AssessmentAgent().evaluate(sample_profile, plan, stale + recent)
    assert result.average_daily_kcal == 2000
    assert result.proposed_flag == AssessmentFlag.CONTINUE
