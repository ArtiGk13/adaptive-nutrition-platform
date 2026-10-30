import pytest

from app.agents.guardrails import (
    check_declared_conditions,
    check_eating_disorder_signals,
    failed,
    run_profile_checks,
)
from app.domain.user_profile import GoalType


def test_declared_condition_refers(sample_profile):
    sample_profile.medical_conditions = ["type 2 diabetes"]
    result = check_declared_conditions(sample_profile)
    assert not result.passed
    assert result.code == "declared_condition"
    assert "type 2 diabetes" in result.message


def test_no_condition_passes(sample_profile):
    assert check_declared_conditions(sample_profile).passed


def test_medication_alone_does_not_refer(sample_profile):
    """No rule was given for medication, so none was invented."""
    sample_profile.medications = ["levothyroxine"]
    assert check_declared_conditions(sample_profile).passed


@pytest.mark.parametrize(
    "field", ["difficult_relationship_with_food", "recent_weight_fluctuation"]
)
def test_any_single_screening_signal_refers(sample_profile, field):
    setattr(sample_profile, field, True)
    result = check_eating_disorder_signals(sample_profile)
    assert not result.passed
    assert result.code == "eating_disorder_signal"


def test_body_image_mismatch_refers(sample_profile):
    """Feeling overweight while underweight is the case the dietitian described."""
    sample_profile.weight_kg = 45.0
    sample_profile.perceives_self_as_overweight = True
    result = check_eating_disorder_signals(sample_profile)
    assert not result.passed
    assert "perceives self as overweight" in result.message


def test_feeling_overweight_at_a_healthy_weight_does_not_refer(sample_profile):
    sample_profile.perceives_self_as_overweight = True
    assert check_eating_disorder_signals(sample_profile).passed


def test_previous_attempts_are_recorded_but_not_thresholded(sample_profile):
    """No threshold was supplied, so the count must not trigger a referral on its own."""
    sample_profile.previous_diet_attempts = 12
    assert check_eating_disorder_signals(sample_profile).passed


def test_clean_profile_passes_every_profile_check(sample_profile):
    assert not failed(run_profile_checks(sample_profile, []))


def test_screening_checks_run_before_any_logging_exists(sample_profile):
    sample_profile.goal_type = GoalType.WEIGHT_LOSS
    sample_profile.medical_conditions = ["coeliac disease"]
    codes = {r.code for r in run_profile_checks(sample_profile, []) if not r.passed}
    assert "declared_condition" in codes


def test_a_decision_reports_every_check_not_only_the_failures(sample_profile):
    """A passing decision could say limits had been checked and not say which, because
    the Supervisor computed them all and kept only the failures."""
    import asyncio

    from app.agents.supervisor import SupervisorAgent
    from app.agents.planner import PlannerAgent

    async def run():
        plan = await PlannerAgent().create_initial_plan(sample_profile)
        return await SupervisorAgent().validate_plan(plan, sample_profile, [])

    decision = asyncio.run(run())

    assert decision.approved
    codes = {check.code for check in decision.checks}
    assert {"age_out_of_range", "declared_condition", "min_calories"} <= codes
    assert all(check.message for check in decision.checks)
    assert all(check.passed for check in decision.checks)
