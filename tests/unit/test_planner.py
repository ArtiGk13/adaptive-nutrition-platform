from app.agents.planner import PlannerAgent
from app.domain.nutrition_plan import PlanStatus, calculate_calorie_target


async def test_initial_plan_uses_deterministic_target(sample_profile):
    sample_profile.user_id = 1
    plan = await PlannerAgent().create_initial_plan(sample_profile)

    assert plan.user_id == 1
    assert plan.version == 1
    assert plan.status == PlanStatus.ACTIVE
    assert plan.calorie_target == calculate_calorie_target(sample_profile)
    assert len(plan.meal_structure) == 4
    assert plan.macro_targets.protein_g > 0
    assert "Mifflin-St Jeor" in plan.rationale
