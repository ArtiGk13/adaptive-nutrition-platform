"""A plan carries a target weight only where the notion applies.

The blind review of generated output found the defect these tests close: the reviewer was
shown a muscle-gain plan whose target weight sat below the user's current weight and asked
why a user trying to gain was being told to lose.
"""

import pytest

from app.agents.planner import PlannerAgent
from app.domain.nutrition_plan import calculate_ideal_weight, plan_target_weight
from app.domain.user_profile import GoalType


def test_weight_loss_keeps_its_target(sample_profile):
    sample_profile.goal_type = GoalType.WEIGHT_LOSS
    assert plan_target_weight(sample_profile) == calculate_ideal_weight(sample_profile)


@pytest.mark.parametrize("goal", [GoalType.MUSCLE_GAIN, GoalType.MAINTENANCE])
def test_other_goals_carry_no_target(sample_profile, goal):
    sample_profile.goal_type = goal
    assert plan_target_weight(sample_profile) is None


@pytest.mark.parametrize("goal", [GoalType.MUSCLE_GAIN, GoalType.MAINTENANCE])
async def test_planner_never_states_a_target_below_current_weight_for_these_goals(
    sample_profile, goal
):
    """The defect itself: a BMI-derived target is below current weight for these users."""
    sample_profile.user_id = 1
    sample_profile.goal_type = goal
    assert calculate_ideal_weight(sample_profile) < sample_profile.weight_kg

    plan = await PlannerAgent().create_initial_plan(sample_profile)
    assert plan.target_weight_kg is None


async def test_muscle_gain_plan_is_not_refused_for_reaching_a_target(sample_profile):
    """With no target weight there is nothing for the target-weight guardrail to fire on."""
    from app.agents.guardrails import check_target_weight_reached

    sample_profile.user_id = 1
    sample_profile.goal_type = GoalType.MUSCLE_GAIN
    plan = await PlannerAgent().create_initial_plan(sample_profile)
    assert check_target_weight_reached(plan, sample_profile).passed
