import pytest

from app.domain.nutrition_plan import (
    build_meal_structure,
    calculate_bmr,
    calculate_calorie_target,
    calculate_macro_targets,
    calculate_tdee,
)
from app.domain.user_profile import ActivityLevel, GoalType, Sex


def test_bmr_male_matches_mifflin_st_jeor():
    assert calculate_bmr(Sex.MALE, weight_kg=80, height_cm=180, age=30) == pytest.approx(1780.0)


def test_bmr_female_matches_mifflin_st_jeor():
    assert calculate_bmr(Sex.FEMALE, weight_kg=65, height_cm=165, age=30) == pytest.approx(1370.25)


def test_tdee_applies_activity_multiplier():
    assert calculate_tdee(1780.0, ActivityLevel.MODERATE) == pytest.approx(2759.0)


def test_weight_loss_target_is_below_maintenance(sample_profile):
    sample_profile.goal_type = GoalType.MAINTENANCE
    maintenance = calculate_calorie_target(sample_profile)

    sample_profile.goal_type = GoalType.WEIGHT_LOSS
    weight_loss = calculate_calorie_target(sample_profile)

    assert weight_loss < maintenance
    assert weight_loss == pytest.approx(maintenance * 0.8, rel=0.01)


def test_macro_targets_sum_to_calorie_target(sample_profile):
    target = calculate_calorie_target(sample_profile)
    macros = calculate_macro_targets(target, sample_profile)
    total_kcal = macros.protein_g * 4 + macros.carbs_g * 4 + macros.fat_g * 9
    assert total_kcal == pytest.approx(target, abs=10)


def test_meal_structure_covers_full_target():
    slots = build_meal_structure(2000)
    assert {slot.slot_name for slot in slots} == {"breakfast", "lunch", "dinner", "snack"}
    assert sum(slot.target_kcal for slot in slots) == pytest.approx(2000, abs=5)
