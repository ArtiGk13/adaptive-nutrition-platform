from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import UserCreate, UserRead
from app.db.database import get_session
from app.services import profile_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> UserRead:
    profile = profile_service.create_profile(session, payload.to_domain())
    return UserRead.from_domain(profile)


@router.get("", response_model=list[UserRead])
def list_users(session: Session = Depends(get_session)) -> list[UserRead]:
    return [UserRead.from_domain(profile) for profile in profile_service.list_profiles(session)]


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)) -> UserRead:
    profile = profile_service.get_profile(session, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return UserRead.from_domain(profile)
