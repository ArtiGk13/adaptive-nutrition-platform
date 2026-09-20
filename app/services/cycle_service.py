from sqlalchemy.orm import Session

from app.agents.coordinator import Coordinator, CycleResult
from app.db import repository
from app.domain.decisions import SupervisorDecision
from app.domain.nutrition_plan import NutritionPlan

default_coordinator = Coordinator()


async def create_initial_plan(
    session: Session, user_id: int, coordinator: Coordinator | None = None
) -> tuple[NutritionPlan | None, SupervisorDecision]:
    profile = repository.get_user(session, user_id)
    if profile is None:
        raise LookupError(f"User {user_id} not found.")
    return await (coordinator or default_coordinator).run_onboarding(session, profile)


async def run_cycle(
    session: Session, user_id: int, coordinator: Coordinator | None = None
) -> CycleResult:
    return await (coordinator or default_coordinator).run_cycle(session, user_id)
