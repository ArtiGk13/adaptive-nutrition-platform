from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import DecisionRead, PlanCreateResponse, PlanRead
from app.db import repository
from app.db.database import get_session
from app.services import cycle_service

router = APIRouter(prefix="/users/{user_id}/plan", tags=["plans"])


@router.post("", response_model=PlanCreateResponse, status_code=201)
async def create_initial_plan(
    user_id: int, session: Session = Depends(get_session)
) -> PlanCreateResponse:
    try:
        plan, decision = await cycle_service.create_initial_plan(session, user_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return PlanCreateResponse(
        plan=PlanRead.from_domain(plan) if plan else None,
        supervisor_decision=DecisionRead.from_domain(decision),
    )


@router.get("", response_model=PlanRead)
def get_active_plan(user_id: int, session: Session = Depends(get_session)) -> PlanRead:
    plan = repository.get_active_plan(session, user_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"No active plan for user {user_id}")
    return PlanRead.from_domain(plan)
