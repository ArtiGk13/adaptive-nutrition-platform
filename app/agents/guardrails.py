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
            message=f"Θερμιδικός στόχος {calorie_target} kcal κάτω από το ασφαλές όριο {minimum} kcal.",
        )
    return GuardrailResult(True, "min_calories", "Θερμιδικός στόχος εντός ασφαλών ορίων.")


def check_max_deficit_rate(calorie_target: int, profile: UserProfile) -> GuardrailResult:
    bmr = calculate_bmr(profile.sex, profile.weight_kg, profile.height_cm, profile.age)
    tdee = calculate_tdee(bmr, profile.activity_level)
    deficit_ratio = (tdee - calorie_target) / tdee
    if deficit_ratio > settings.max_deficit_ratio:
        return GuardrailResult(
            passed=False,
            code="max_deficit",
            message=(
                f"Έλλειμμα {deficit_ratio:.0%} πάνω από το επιτρεπτό "
                f"{settings.max_deficit_ratio:.0%} της ημερήσιας δαπάνης."
            ),
        )
    return GuardrailResult(True, "max_deficit", "Έλλειμμα εντός επιτρεπτών ορίων.")


def check_suspicious_pattern(profile: UserProfile, logs: list[LogEntry]) -> GuardrailResult:
    if profile.bmi < MIN_HEALTHY_BMI and profile.goal_type == GoalType.WEIGHT_LOSS:
        return GuardrailResult(
            passed=False,
            code="underweight_weight_loss",
            message=f"BMI {profile.bmi:.1f} κάτω από {MIN_HEALTHY_BMI} με στόχο απώλειας βάρους.",
        )

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
                    message=f"Ρυθμός απώλειας {weekly_change:.1f} kg/εβδομάδα πάνω από το ασφαλές όριο.",
                )

    return GuardrailResult(True, "suspicious_pattern", "Δεν εντοπίστηκε ύποπτο μοτίβο.")


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
                f"Ηλικία {profile.age} ετών εκτός του υποστηριζόμενου εύρους {low}-{high}. "
                "Απαιτείται αξιολόγηση από ειδικό."
            ),
        )
    return GuardrailResult(True, "age_out_of_range", "Ηλικία εντός υποστηριζόμενου εύρους.")


def check_macro_distribution(plan: NutritionPlan) -> GuardrailResult:
    """Macros must stay inside the acceptable distribution ranges (DRIs, 2010)."""
    shares = {
        "protein": plan.macro_targets.protein_g * 4 / plan.calorie_target,
        "fat": plan.macro_targets.fat_g * 9 / plan.calorie_target,
        "carbs": plan.macro_targets.carbs_g * 4 / plan.calorie_target,
    }
    breaches = [
        f"{name} {shares[name]:.0%} εκτός {low:.0%}-{high:.0%}"
        for name, (low, high) in DRI_RANGES.items()
        if not (low - MACRO_ROUNDING_TOLERANCE <= shares[name] <= high + MACRO_ROUNDING_TOLERANCE)
    ]
    if breaches:
        return GuardrailResult(
            passed=False,
            code="macro_distribution",
            message="Κατανομή μακροθρεπτικών εκτός συνιστώμενων ορίων: " + ", ".join(breaches),
        )
    return GuardrailResult(True, "macro_distribution", "Κατανομή μακροθρεπτικών εντός ορίων.")


def run_plan_checks(plan: NutritionPlan, profile: UserProfile) -> list[GuardrailResult]:
    return [
        check_supported_age(profile),
        check_min_calories(plan.calorie_target, profile.sex),
        check_max_deficit_rate(plan.calorie_target, profile),
        check_macro_distribution(plan),
    ]


def failed(results: list[GuardrailResult]) -> list[GuardrailResult]:
    return [result for result in results if not result.passed]
