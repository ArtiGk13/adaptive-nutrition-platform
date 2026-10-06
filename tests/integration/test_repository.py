from datetime import datetime, timezone

import pytest

from app.db import repository
from app.db.repository import SupervisorApprovalRequired
from app.domain.decisions import DecisionType, SupervisorDecision
from app.domain.log_entry import MealLogEntry, WeightLogEntry
from app.domain.nutrition_plan import MacroTargets, MealSlot, NutritionPlan, PlanStatus


def approved_decision(user_id: int) -> SupervisorDecision:
    return SupervisorDecision(
        user_id=user_id,
        cycle_timestamp=datetime.now(timezone.utc),
        decision_type=DecisionType.APPROVE_PLAN,
        guardrail_checks_passed=True,
        notes="ok",
    )


def rejected_decision(user_id: int) -> SupervisorDecision:
    return SupervisorDecision(
        user_id=user_id,
        cycle_timestamp=datetime.now(timezone.utc),
        decision_type=DecisionType.HOLD,
        guardrail_checks_passed=False,
        notes="unsafe",
        failed_checks=["min_calories"],
    )


def build_plan(user_id: int, calorie_target: int = 1900) -> NutritionPlan:
    return NutritionPlan(
        user_id=user_id,
        calorie_target=calorie_target,
        macro_targets=MacroTargets(protein_g=130, carbs_g=190, fat_g=59),
        meal_structure=[MealSlot(slot_name="lunch", target_kcal=700)],
        rationale="test",
    )


def test_user_roundtrip(session, sample_profile):
    created = repository.create_user(session, sample_profile)
    assert created.user_id is not None

    fetched = repository.get_user(session, created.user_id)
    assert fetched.name == sample_profile.name
    assert fetched.goal_type == sample_profile.goal_type


def test_save_plan_requires_supervisor_approval(session, sample_profile):
    user = repository.create_user(session, sample_profile)
    with pytest.raises(SupervisorApprovalRequired):
        repository.save_plan(session, build_plan(user.user_id), rejected_decision(user.user_id))
    assert repository.get_active_plan(session, user.user_id) is None


def test_new_plan_supersedes_previous_and_increments_version(session, sample_profile):
    user = repository.create_user(session, sample_profile)
    first = repository.save_plan(
        session, build_plan(user.user_id, 1900), approved_decision(user.user_id)
    )
    second = repository.save_plan(
        session, build_plan(user.user_id, 1800), approved_decision(user.user_id)
    )

    assert first.version == 1
    assert second.version == 2

    active = repository.get_active_plan(session, user.user_id)
    assert active.plan_id == second.plan_id
    assert active.status == PlanStatus.ACTIVE

    profile = repository.get_user(session, user.user_id)
    assert profile.current_plan_id == second.plan_id


def test_log_entries_roundtrip_by_type(session, sample_profile):
    user = repository.create_user(session, sample_profile)
    now = datetime.now(timezone.utc)

    repository.add_log_entry(
        session,
        MealLogEntry(
            user_id=user.user_id,
            timestamp=now,
            meal_slot="lunch",
            food_description="Chicken salad",
            estimated_kcal=550,
            estimated_macros={"protein_g": 40},
        ),
    )
    repository.add_log_entry(
        session, WeightLogEntry(user_id=user.user_id, timestamp=now, weight_kg=71.4)
    )

    logs = repository.get_logs(session, user.user_id)
    assert len(logs) == 2
    assert isinstance(logs[0], MealLogEntry) or isinstance(logs[1], MealLogEntry)
    meal = next(entry for entry in logs if isinstance(entry, MealLogEntry))
    assert meal.estimated_kcal == 550
    assert meal.estimated_macros == {"protein_g": 40}
