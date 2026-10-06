from datetime import datetime, timedelta, timezone

import pytest

from app.agents.guardrails import (
    check_macro_distribution,
    check_max_deficit_rate,
    check_min_calories,
    check_supported_age,
    check_suspicious_pattern,
)
from app.domain.log_entry import WeightLogEntry
from app.domain.nutrition_plan import (
    MacroTargets,
    NutritionPlan,
    calculate_calorie_target,
    calculate_macro_targets,
)
from app.domain.user_profile import GoalType, Sex


def test_min_calories_rejects_unsafe_target():
    result = check_min_calories(900, Sex.FEMALE)
    assert not result.passed
    assert result.code == "min_calories"


def test_min_calories_accepts_safe_target():
    assert check_min_calories(1800, Sex.FEMALE).passed


def test_max_deficit_rejects_aggressive_target(sample_profile):
    normal_target = calculate_calorie_target(sample_profile)
    assert not check_max_deficit_rate(round(normal_target * 0.5), sample_profile).passed


def test_max_deficit_accepts_planned_target(sample_profile):
    target = calculate_calorie_target(sample_profile)
    assert check_max_deficit_rate(target, sample_profile).passed


def test_suspicious_pattern_flags_underweight_weight_loss(sample_profile):
    sample_profile.weight_kg = 45.0
    sample_profile.goal_type = GoalType.WEIGHT_LOSS
    result = check_suspicious_pattern(sample_profile, [])
    assert not result.passed
    assert result.code == "underweight_weight_loss"


def test_suspicious_pattern_flags_rapid_weight_loss(sample_profile):
    now = datetime.now(timezone.utc)
    logs = [
        WeightLogEntry(user_id=1, timestamp=now - timedelta(days=7), weight_kg=72.0),
        WeightLogEntry(user_id=1, timestamp=now, weight_kg=69.0),
    ]
    result = check_suspicious_pattern(sample_profile, logs)
    assert not result.passed
    assert result.code == "rapid_weight_loss"


@pytest.mark.parametrize("age", [16, 17, 66, 80])
def test_age_outside_supported_range_is_rejected(sample_profile, age):
    sample_profile.age = age
    result = check_supported_age(sample_profile)
    assert not result.passed
    assert result.code == "age_out_of_range"


@pytest.mark.parametrize("age", [18, 30, 65])
def test_supported_adult_age_is_accepted(sample_profile, age):
    sample_profile.age = age
    assert check_supported_age(sample_profile).passed


def test_macro_distribution_accepts_planned_macros(sample_profile):
    target = calculate_calorie_target(sample_profile)
    plan = NutritionPlan(
        user_id=1,
        calorie_target=target,
        macro_targets=calculate_macro_targets(target, sample_profile),
        meal_structure=[],
        rationale="test",
    )
    assert check_macro_distribution(plan).passed


def test_macro_distribution_rejects_carbohydrate_shortfall():
    plan = NutritionPlan(
        user_id=1,
        calorie_target=2000,
        macro_targets=MacroTargets(protein_g=175, carbs_g=150, fat_g=78),
        meal_structure=[],
        rationale="test",
    )
    result = check_macro_distribution(plan)
    assert not result.passed
    assert result.code == "macro_distribution"


def test_suspicious_pattern_accepts_healthy_progress(sample_profile):
    now = datetime.now(timezone.utc)
    logs = [
        WeightLogEntry(user_id=1, timestamp=now - timedelta(days=7), weight_kg=72.0),
        WeightLogEntry(user_id=1, timestamp=now, weight_kg=71.5),
    ]
    assert check_suspicious_pattern(sample_profile, logs).passed
