import pytest

from app.db import repository
from app.db.models import UserProfileORM
from app.domain.decisions import ActionType, DecisionType
from app.domain.user_profile import GoalType
from app.services import cycle_service


async def test_onboarding_creates_approved_plan(session, sample_profile):
    user = repository.create_user(session, sample_profile)
    plan, decision = await cycle_service.create_initial_plan(session, user.user_id)

    assert decision.decision_type == DecisionType.APPROVE_PLAN
    assert decision.guardrail_checks_passed
    assert plan.plan_id is not None
    assert repository.get_active_plan(session, user.user_id).plan_id == plan.plan_id


async def test_cycle_with_on_target_logs_continues(session, sample_profile, meal_logs_factory):
    user = repository.create_user(session, sample_profile)
    plan, _ = await cycle_service.create_initial_plan(session, user.user_id)

    for entry in meal_logs_factory(user.user_id, plan.calorie_target):
        repository.add_log_entry(session, entry)

    result = await cycle_service.run_cycle(session, user.user_id)

    assert result.assessment.adherence_score == pytest.approx(1.0)
    assert result.action.action_type == ActionType.CONTINUE
    assert result.decision.approved
    assert result.plan.plan_id == plan.plan_id
    assert result.feedback_text is None


async def test_cycle_with_overshooting_logs_adjusts_plan(
    session, sample_profile, meal_logs_factory
):
    user = repository.create_user(session, sample_profile)
    plan, _ = await cycle_service.create_initial_plan(session, user.user_id)

    for entry in meal_logs_factory(user.user_id, round(plan.calorie_target * 1.25)):
        repository.add_log_entry(session, entry)

    result = await cycle_service.run_cycle(session, user.user_id)

    assert result.action.action_type == ActionType.ADJUST_PLAN
    assert result.decision.approved
    assert result.plan.version == 2
    assert result.plan.calorie_target > plan.calorie_target
    assert result.feedback_text


async def test_cycle_without_logs_requests_extra_support(session, sample_profile):
    user = repository.create_user(session, sample_profile)
    await cycle_service.create_initial_plan(session, user.user_id)

    result = await cycle_service.run_cycle(session, user.user_id)

    assert result.assessment.adherence_score == 0.0
    assert result.action.action_type == ActionType.EXTRA_SUPPORT
    assert result.feedback_text


async def test_cycle_flags_referral_for_unsafe_profile(session, sample_profile):
    user = repository.create_user(session, sample_profile)
    await cycle_service.create_initial_plan(session, user.user_id)

    row = session.get(UserProfileORM, user.user_id)
    row.weight_kg = 45.0
    row.goal_type = GoalType.WEIGHT_LOSS.value
    session.commit()

    result = await cycle_service.run_cycle(session, user.user_id)

    assert result.decision.decision_type == DecisionType.FLAG_REFERRAL
    assert not result.decision.guardrail_checks_passed
    assert result.plan.version == 1


async def test_cycle_for_unknown_user_raises(session):
    with pytest.raises(LookupError):
        await cycle_service.run_cycle(session, 999)
