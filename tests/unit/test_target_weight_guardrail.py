import pytest

from app.agents.guardrails import check_target_weight_reached, failed, run_plan_checks
from app.domain.nutrition_plan import (
    MacroTargets,
    NutritionPlan,
    build_meal_structure,
    calculate_calorie_target,
    calculate_ideal_weight,
    calculate_macro_targets,
)
from app.domain.user_profile import GoalType


def plan_for(profile) -> NutritionPlan:
    target = calculate_calorie_target(profile)
    return NutritionPlan(
        user_id=1,
        calorie_target=target,
        macro_targets=calculate_macro_targets(target, profile),
        meal_structure=build_meal_structure(target),
        rationale="test",
        target_weight_kg=calculate_ideal_weight(profile),
    )


def test_user_above_target_passes(sample_profile):
    plan = plan_for(sample_profile)
    assert sample_profile.weight_kg > plan.target_weight_kg
    assert check_target_weight_reached(plan, sample_profile).passed


def test_reaching_the_target_stops_further_loss(sample_profile):
    plan = plan_for(sample_profile)
    sample_profile.weight_kg = plan.target_weight_kg
    result = check_target_weight_reached(plan, sample_profile)
    assert not result.passed
    assert result.code == "target_weight_reached"


def test_falling_below_the_target_stops_further_loss(sample_profile):
    plan = plan_for(sample_profile)
    sample_profile.weight_kg = plan.target_weight_kg - 3.0
    assert not check_target_weight_reached(plan, sample_profile).passed


@pytest.mark.parametrize("goal", [GoalType.MAINTENANCE, GoalType.MUSCLE_GAIN])
def test_other_goals_are_unaffected(sample_profile, goal):
    """Being at or below the derived weight is only a concern while still cutting."""
    plan = plan_for(sample_profile)
    sample_profile.goal_type = goal
    sample_profile.weight_kg = (plan.target_weight_kg or 60.0) - 3.0
    assert check_target_weight_reached(plan, sample_profile).passed


def test_plan_without_a_target_weight_passes(sample_profile):
    plan = NutritionPlan(
        user_id=1,
        calorie_target=1800,
        macro_targets=MacroTargets(protein_g=120, carbs_g=200, fat_g=56),
        meal_structure=[],
        rationale="test",
        target_weight_kg=None,
    )
    assert check_target_weight_reached(plan, sample_profile).passed


def test_the_check_runs_as_part_of_plan_validation(sample_profile):
    plan = plan_for(sample_profile)
    sample_profile.weight_kg = plan.target_weight_kg - 1.0
    codes = {r.code for r in failed(run_plan_checks(plan, sample_profile))}
    assert "target_weight_reached" in codes
