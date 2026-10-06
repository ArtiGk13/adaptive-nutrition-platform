import pytest

from app.agents.planner import PlannerAgent
from app.domain.nutrition_plan import (
    DESIRABLE_BMI_RANGE,
    STAGED_BMI_WHEN_OVERWEIGHT,
    calculate_ideal_weight,
    target_bmi_for,
)
from app.domain.user_profile import Sex


def test_normal_weight_user_targets_the_desirable_range(sample_profile):
    sample_profile.sex = Sex.FEMALE
    sample_profile.weight_kg = 62.0  # BMI ~22.0
    low, high = DESIRABLE_BMI_RANGE[Sex.FEMALE]
    assert low <= target_bmi_for(sample_profile) <= high


@pytest.mark.parametrize("sex", list(Sex))
def test_overweight_user_gets_the_staged_target(sample_profile, sex):
    sample_profile.sex = sex
    sample_profile.weight_kg = 95.0  # BMI ~33.7 at 168 cm
    assert target_bmi_for(sample_profile) == STAGED_BMI_WHEN_OVERWEIGHT[sex]


def test_staged_target_is_above_the_desirable_range(sample_profile):
    """The overweight value is an initial milestone, not the final goal."""
    for sex in Sex:
        assert STAGED_BMI_WHEN_OVERWEIGHT[sex] > DESIRABLE_BMI_RANGE[sex][1]


def test_ideal_weight_follows_height(sample_profile):
    sample_profile.sex = Sex.FEMALE
    sample_profile.weight_kg = 62.0
    sample_profile.height_cm = 170.0
    taller = calculate_ideal_weight(sample_profile)

    sample_profile.height_cm = 160.0
    shorter = calculate_ideal_weight(sample_profile)

    assert taller > shorter


def test_ideal_weight_is_below_current_weight_for_an_overweight_user(sample_profile):
    sample_profile.weight_kg = 95.0
    assert calculate_ideal_weight(sample_profile) < sample_profile.weight_kg


def test_target_lowers_once_the_user_is_no_longer_overweight(sample_profile):
    sample_profile.sex = Sex.FEMALE
    sample_profile.height_cm = 168.0

    sample_profile.weight_kg = 95.0
    while_overweight = calculate_ideal_weight(sample_profile)

    sample_profile.weight_kg = 68.0  # BMI ~24.1, no longer overweight
    after_progress = calculate_ideal_weight(sample_profile)

    assert after_progress < while_overweight


async def test_planner_records_the_target_weight(sample_profile):
    sample_profile.user_id = 1
    plan = await PlannerAgent().create_initial_plan(sample_profile)
    assert plan.target_weight_kg == calculate_ideal_weight(sample_profile)
