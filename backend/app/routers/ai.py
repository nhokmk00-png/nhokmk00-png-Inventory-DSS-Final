from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.ai_service import chat, general_chat, generate_insight

router = APIRouter(prefix="/api/gemini", tags=["Gemini"])


class ChatRequest(BaseModel):
    product_id: str | None = None
    question: str = Field(min_length=3)


@router.post("/insight/{product_id}")
def insight(product_id: str, force: bool = False) -> dict:
    try:
        return generate_insight(product_id.upper(), force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy sản phẩm {exc.args[0]}") from exc


@router.post("/chat")
def chat_with_gemini(payload: ChatRequest) -> dict:
    try:
        if payload.product_id:
            return chat(payload.product_id.upper(), payload.question)
        return general_chat(payload.question)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy sản phẩm {exc.args[0]}") from exc
