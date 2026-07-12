from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_service import answer_inventory_question

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatPayload(BaseModel):
    question: str


@router.post("/chat")
def chat(payload: ChatPayload, db: Session = Depends(get_db)):
    return answer_inventory_question(db, payload.question)
