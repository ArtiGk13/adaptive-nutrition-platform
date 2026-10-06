import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal, create_tables  # noqa: E402
from app.db.repository import add_log_entry, create_user  # noqa: E402
from app.domain.log_entry import MealLogEntry, WeightLogEntry  # noqa: E402
from app.domain.user_profile import (  # noqa: E402
    ActivityLevel,
    GoalType,
    Sex,
    UserProfile,
)
from app.services.cycle_service import create_initial_plan  # noqa: E402

SYNTHETIC_PROFILE = UserProfile(
    name="Synthetic User 1",
    age=30,
    sex=Sex.FEMALE,
    height_cm=168.0,
    weight_kg=72.0,
    activity_level=ActivityLevel.LIGHT,
    goal_type=GoalType.WEIGHT_LOSS,
)

MEALS = [
    ("breakfast", "Yoghurt with oats and fruit", 420),
    ("lunch", "Chicken with rice and salad", 640),
    ("dinner", "Vegetable omelette", 480),
]


async def main() -> None:
    create_tables()
    session = SessionLocal()
    try:
        profile = create_user(session, SYNTHETIC_PROFILE)
        print(f"Created user {profile.user_id} ({profile.name})")

        now = datetime.now(timezone.utc)
        for day_offset in range(3):
            day = now - timedelta(days=day_offset)
            for slot, description, kcal in MEALS:
                add_log_entry(
                    session,
                    MealLogEntry(
                        user_id=profile.user_id,
                        timestamp=day,
                        meal_slot=slot,
                        food_description=description,
                        estimated_kcal=kcal,
                    ),
                )
            add_log_entry(
                session,
                WeightLogEntry(
                    user_id=profile.user_id,
                    timestamp=day,
                    weight_kg=profile.weight_kg - (0.05 * (2 - day_offset)),
                ),
            )
        print("Seeded 9 meal logs and 3 weight logs")

        plan, decision = await create_initial_plan(session, profile.user_id)
        if plan is None:
            print(f"Supervisor rejected the initial plan: {decision.notes}")
            return
        print(
            f"Initial plan v{plan.version}: {plan.calorie_target} kcal "
            f"(P{plan.macro_targets.protein_g}/C{plan.macro_targets.carbs_g}/"
            f"F{plan.macro_targets.fat_g}) | supervisor={decision.decision_type.value}"
        )
        print(f"Run a cycle with: POST /users/{profile.user_id}/cycle")
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
