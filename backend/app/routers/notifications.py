from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.notification_service import list_notifications, send_summary

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def notifications(db: Session = Depends(get_db)):
    return list_notifications(db)


@router.post("/summary/send")
def summary_send(db: Session = Depends(get_db)):
    return send_summary(db)
