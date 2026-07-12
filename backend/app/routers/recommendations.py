from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.inventory_service import list_recommendations, process_decision
from ..services.notification_service import send_recommendation

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class DecisionPayload(BaseModel):
    decision: str
    final_quantity: int | None = None
    reason: str = ""
    processed_by: str = "Quản lý kho"


@router.get("")
def recommendations(search: str = "", status: str = "Tất cả", internal_status: str = "Tất cả", page: int = 1, page_size: int = 8, db: Session = Depends(get_db)):
    return list_recommendations(db, search=search, status=status, internal_status=internal_status, page=page, page_size=page_size)


@router.post("/{recommendation_id}/decision")
def decision(recommendation_id: int, payload: DecisionPayload, db: Session = Depends(get_db)):
    try:
        return process_decision(db, recommendation_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{recommendation_id}/send")
def send(recommendation_id: int, db: Session = Depends(get_db)):
    try:
        return send_recommendation(db, recommendation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
