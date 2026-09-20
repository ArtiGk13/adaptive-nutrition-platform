from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CycleResponse
from app.db.database import get_session
from app.services import cycle_service

router = APIRouter(prefix="/users/{user_id}/cycle", tags=["cycle"])


@router.post("", response_model=CycleResponse)
async def run_cycle(user_id: int, session: Session = Depends(get_session)) -> CycleResponse:
    try:
        result = await cycle_service.run_cycle(session, user_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CycleResponse.from_domain(result)
