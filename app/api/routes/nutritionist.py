from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import UserHistoryRead, UserOverviewRead
from app.db import repository
from app.db.database import get_session
from app.domain.user_profile import Role, UserProfile
from app.services import nutritionist_service

router = APIRouter(prefix="/nutritionist", tags=["nutritionist"])


def require_nutritionist(
    x_user_id: int = Header(..., description="Id of the calling user"),
    session: Session = Depends(get_session),
) -> UserProfile:
    """Identify the caller from a header and check their role.

    Deliberately minimal: there are no credentials, sessions or tokens, so this
    demonstrates role separation rather than providing real access control.
    Authentication is out of scope for the thesis and is stated as such.
    """
    caller = repository.get_user(session, x_user_id)
    if caller is None:
        raise HTTPException(status_code=401, detail=f"Unknown user {x_user_id}")
    if caller.role != Role.NUTRITIONIST:
        raise HTTPException(
            status_code=403, detail="This endpoint is restricted to the nutritionist role"
        )
    return caller


@router.get("/users", response_model=list[UserOverviewRead])
def list_users(
    session: Session = Depends(get_session),
    caller: UserProfile = Depends(require_nutritionist),
) -> list[UserOverviewRead]:
    return [
        UserOverviewRead.from_domain(overview)
        for overview in nutritionist_service.list_overviews(session)
    ]


@router.get("/flagged", response_model=list[UserOverviewRead])
def list_flagged(
    session: Session = Depends(get_session),
    caller: UserProfile = Depends(require_nutritionist),
) -> list[UserOverviewRead]:
    return [
        UserOverviewRead.from_domain(overview)
        for overview in nutritionist_service.list_flagged(session)
    ]


@router.get("/users/{user_id}", response_model=UserHistoryRead)
def get_user_history(
    user_id: int,
    session: Session = Depends(get_session),
    caller: UserProfile = Depends(require_nutritionist),
) -> UserHistoryRead:
    history = nutritionist_service.get_history(session, user_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return UserHistoryRead.from_domain(history)
