from app.domain.nutrition_plan import (
    NutritionPlan,
    build_meal_structure,
    calculate_calorie_target,
    calculate_macro_targets,
)
from app.domain.user_profile import UserProfile


class PlannerAgent:
    """Builds the initial structured nutrition plan. Fully deterministic, no LLM."""

    async def create_initial_plan(self, profile: UserProfile) -> NutritionPlan:
        calorie_target = calculate_calorie_target(profile)
        return NutritionPlan(
            user_id=profile.user_id,
            calorie_target=calorie_target,
            macro_targets=calculate_macro_targets(calorie_target, profile),
            meal_structure=build_meal_structure(calorie_target),
            rationale=(
                f"Initial plan from Mifflin-St Jeor for goal "
                f"'{profile.goal_type.value}' and activity level "
                f"'{profile.activity_level.value}'."
            ),
        )
