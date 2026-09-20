from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ActivityLogCreate, LogRead, MealLogCreate, WeightLogCreate
from app.db.database import get_session
from app.services import profile_service

router = APIRouter(prefix="/users/{user_id}/logs", tags=["logs"])


def _require_user(session: Session, user_id: int) -> None:
    if profile_service.get_profile(session, user_id) is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")


@router.post("/meal", response_model=LogRead, status_code=201)
def log_meal(
    user_id: int, payload: MealLogCreate, session: Session = Depends(get_session)
) -> LogRead:
    _require_user(session, user_id)
    return LogRead.from_domain(profile_service.add_log(session, payload.to_domain(user_id)))


@router.post("/weight", response_model=LogRead, status_code=201)
def log_weight(
    user_id: int, payload: WeightLogCreate, session: Session = Depends(get_session)
) -> LogRead:
    _require_user(session, user_id)
    return LogRead.from_domain(profile_service.add_log(session, payload.to_domain(user_id)))


@router.post("/activity", response_model=LogRead, status_code=201)
def log_activity(
    user_id: int, payload: ActivityLogCreate, session: Session = Depends(get_session)
) -> LogRead:
    _require_user(session, user_id)
    return LogRead.from_domain(profile_service.add_log(session, payload.to_domain(user_id)))


@router.get("", response_model=list[LogRead])
def list_logs(user_id: int, session: Session = Depends(get_session)) -> list[LogRead]:
    _require_user(session, user_id)
    return [LogRead.from_domain(entry) for entry in profile_service.get_logs(session, user_id)]
