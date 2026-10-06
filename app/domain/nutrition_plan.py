from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.user_profile import ActivityLevel, GoalType, Sex, UserProfile

ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

GOAL_CALORIE_ADJUSTMENTS: dict[GoalType, float] = {
    GoalType.WEIGHT_LOSS: -0.20,
    GoalType.MAINTENANCE: 0.0,
    GoalType.MUSCLE_GAIN: 0.10,
}

PROTEIN_G_PER_KG: dict[GoalType, float] = {
    GoalType.WEIGHT_LOSS: 1.8,
    GoalType.MAINTENANCE: 1.4,
    GoalType.MUSCLE_GAIN: 2.0,
}

FAT_CALORIE_RATIO = 0.28

# Acceptable Macronutrient Distribution Ranges (DRIs, 2010), as shares of total energy.
DRI_RANGES: dict[str, tuple[float, float]] = {
    "protein": (0.10, 0.35),
    "fat": (0.20, 0.35),
    "carbs": (0.45, 0.65),
}

SUPPORTED_AGE_RANGE = (18, 65)

MEAL_SLOT_RATIOS: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.35,
    "dinner": 0.30,
    "snack": 0.10,
}


class PlanStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


@dataclass
class MacroTargets:
    protein_g: int
    carbs_g: int
    fat_g: int


@dataclass
class MealSlot:
    slot_name: str
    target_kcal: int


@dataclass
class NutritionPlan:
    user_id: int
    calorie_target: int
    macro_targets: MacroTargets
    meal_structure: list[MealSlot]
    rationale: str
    version: int = 1
    plan_id: int | None = None
    status: PlanStatus = PlanStatus.ACTIVE
    created_at: datetime | None = None
    # What the user has demonstrated they can actually sustain. Without remembering this,
    # re-anchoring on the goal would keep undoing every adjustment made for sustainability.
    sustainable_target_kcal: int | None = None


def calculate_bmr(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor equation."""
    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    return base + 5 if sex == Sex.MALE else base - 161


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


def calculate_calorie_target(profile: UserProfile) -> int:
    bmr = calculate_bmr(profile.sex, profile.weight_kg, profile.height_cm, profile.age)
    tdee = calculate_tdee(bmr, profile.activity_level)
    adjustment = GOAL_CALORIE_ADJUSTMENTS[profile.goal_type]
    return round(tdee * (1 + adjustment))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calculate_macro_targets(calorie_target: int, profile: UserProfile) -> MacroTargets:
    """Protein from body weight and fat as a share of energy, held inside the DRI ranges.

    Protein prescribed per kilogram inflates as a share of energy when calories are cut,
    which pushes carbohydrates below the recommended range. Energy is therefore moved back
    out of protein first, then fat, until carbohydrates reach their lower bound.
    """
    protein_low, protein_high = (ratio * calorie_target for ratio in DRI_RANGES["protein"])
    fat_low, fat_high = (ratio * calorie_target for ratio in DRI_RANGES["fat"])
    carbs_low, carbs_high = (ratio * calorie_target for ratio in DRI_RANGES["carbs"])

    protein_kcal = _clamp(
        PROTEIN_G_PER_KG[profile.goal_type] * profile.weight_kg * 4, protein_low, protein_high
    )
    fat_kcal = _clamp(calorie_target * FAT_CALORIE_RATIO, fat_low, fat_high)
    carbs_kcal = calorie_target - protein_kcal - fat_kcal

    if carbs_kcal < carbs_low:
        shortfall = carbs_low - carbs_kcal
        from_protein = min(shortfall, protein_kcal - protein_low)
        protein_kcal -= from_protein
        fat_kcal -= min(shortfall - from_protein, fat_kcal - fat_low)
    elif carbs_kcal > carbs_high:
        surplus = carbs_kcal - carbs_high
        to_protein = min(surplus, protein_high - protein_kcal)
        protein_kcal += to_protein
        fat_kcal += min(surplus - to_protein, fat_high - fat_kcal)

    carbs_kcal = calorie_target - protein_kcal - fat_kcal
    return MacroTargets(
        protein_g=round(protein_kcal / 4),
        carbs_g=round(carbs_kcal / 4),
        fat_g=round(fat_kcal / 9),
    )


def build_meal_structure(calorie_target: int) -> list[MealSlot]:
    return [
        MealSlot(slot_name=name, target_kcal=round(calorie_target * ratio))
        for name, ratio in MEAL_SLOT_RATIOS.items()
    ]
