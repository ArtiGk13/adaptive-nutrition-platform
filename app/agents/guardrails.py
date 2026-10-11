from dataclasses import dataclass

from app.config import settings
from app.domain.log_entry import LogEntry, WeightLogEntry
from app.domain.nutrition_plan import (
    DRI_RANGES,
    SUPPORTED_AGE_RANGE,
    NutritionPlan,
    calculate_bmr,
    calculate_tdee,
)
from app.domain.user_profile import GoalType, Sex, UserProfile

MIN_HEALTHY_BMI = 18.5
MAX_WEEKLY_LOSS_KG = 1.0
MACRO_ROUNDING_TOLERANCE = 0.01


@dataclass
class GuardrailResult:
    passed: bool
    code: str
    message: str


def minimum_calories_for(sex: Sex) -> int:
    return settings.min_calories_male if sex == Sex.MALE else settings.min_calories_female


def check_min_calories(calorie_target: int, sex: Sex) -> GuardrailResult:
    minimum = minimum_calories_for(sex)
    if calorie_target < minimum:
        return GuardrailResult(
            passed=False,
            code="min_calories",
            message=f"Calorie target {calorie_target} kcal is below the safe floor of {minimum} kcal.",
        )
    return GuardrailResult(True, "min_calories", "Calorie target is within safe limits.")


def check_max_deficit_rate(calorie_target: int, profile: UserProfile) -> GuardrailResult:
    bmr = calculate_bmr(profile.sex, profile.weight_kg, profile.height_cm, profile.age)
    tdee = calculate_tdee(bmr, profile.activity_level)
    deficit_ratio = (tdee - calorie_target) / tdee
    if deficit_ratio > settings.max_deficit_ratio:
        return GuardrailResult(
            passed=False,
            code="max_deficit",
            message=(
                f"Deficit of {deficit_ratio:.0%} exceeds the permitted "
                f"{settings.max_deficit_ratio:.0%} of daily energy expenditure."
            ),
        )
    return GuardrailResult(True, "max_deficit", "Deficit is within permitted limits.")


def check_underweight_goal(profile: UserProfile) -> GuardrailResult:
    if profile.bmi < MIN_HEALTHY_BMI and profile.goal_type == GoalType.WEIGHT_LOSS:
        return GuardrailResult(
            passed=False,
            code="underweight_weight_loss",
            message=f"BMI {profile.bmi:.1f} is below {MIN_HEALTHY_BMI} with a weight-loss goal.",
        )
    return GuardrailResult(True, "underweight_weight_loss", "BMI is compatible with the goal.")


def check_rapid_weight_loss(profile: UserProfile, logs: list[LogEntry]) -> GuardrailResult:
    weight_logs = sorted(
        (entry for entry in logs if isinstance(entry, WeightLogEntry)),
        key=lambda entry: entry.timestamp,
    )
    if len(weight_logs) >= 2:
        first, last = weight_logs[0], weight_logs[-1]
        days = (last.timestamp - first.timestamp).days
        if days > 0:
            weekly_change = (first.weight_kg - last.weight_kg) / days * 7
            if weekly_change > MAX_WEEKLY_LOSS_KG:
                return GuardrailResult(
                    passed=False,
                    code="rapid_weight_loss",
                    message=f"Loss rate of {weekly_change:.1f} kg/week exceeds the safe limit.",
                )

    return GuardrailResult(True, "rapid_weight_loss", "Weight change rate is within safe limits.")


def check_supported_age(profile: UserProfile) -> GuardrailResult:
    """The reference values the planner uses are defined for adults only (WHO, 2004).

    Different classification tables apply over 65 (NEMO, 2019), and under 18 growth makes
    them inapplicable, so the system must hand these users over instead of planning.
    """
    low, high = SUPPORTED_AGE_RANGE
    if not (low <= profile.age <= high):
        return GuardrailResult(
            passed=False,
            code="age_out_of_range",
            message=(
                f"Age {profile.age} is outside the supported range of {low}-{high}. "
                "Assessment by a specialist is required."
            ),
        )
    return GuardrailResult(True, "age_out_of_range", "Age is within the supported range.")


def check_macro_distribution(plan: NutritionPlan) -> GuardrailResult:
    """Macros must stay inside the acceptable distribution ranges (DRIs, 2010)."""
    shares = {
        "protein": plan.macro_targets.protein_g * 4 / plan.calorie_target,
        "fat": plan.macro_targets.fat_g * 9 / plan.calorie_target,
        "carbs": plan.macro_targets.carbs_g * 4 / plan.calorie_target,
    }
    breaches = [
        f"{name} at {shares[name]:.0%} outside {low:.0%}-{high:.0%}"
        for name, (low, high) in DRI_RANGES.items()
        if not (low - MACRO_ROUNDING_TOLERANCE <= shares[name] <= high + MACRO_ROUNDING_TOLERANCE)
    ]
    if breaches:
        return GuardrailResult(
            passed=False,
            code="macro_distribution",
            message="Macronutrient distribution outside recommended ranges: " + ", ".join(breaches),
        )
    return GuardrailResult(
        True, "macro_distribution", "Macronutrient distribution is within recommended ranges."
    )


def run_profile_checks(profile: UserProfile, logs: list[LogEntry]) -> list[GuardrailResult]:
    """Checks about the person, which apply whether or not a new plan is being proposed."""
    return [
        check_supported_age(profile),
        check_underweight_goal(profile),
        check_rapid_weight_loss(profile, logs),
    ]


def run_plan_checks(plan: NutritionPlan, profile: UserProfile) -> list[GuardrailResult]:
    """Checks about the numbers inside a proposed plan."""
    return [
        check_min_calories(plan.calorie_target, profile.sex),
        check_max_deficit_rate(plan.calorie_target, profile),
        check_macro_distribution(plan),
    ]


def failed(results: list[GuardrailResult]) -> list[GuardrailResult]:
    return [result for result in results if not result.passed]
