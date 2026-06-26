from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.notification_service import send_approved_recommendation
from backend.app.services.recommendation_service import get_recommendation, latest_recommendations, process_internal_decision

router = APIRouter(prefix="/api/approval", tags=["Xử lý đề xuất"])


class InternalDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVE|ADJUST|REJECT)$")
    final_quantity: int | None = Field(default=None, ge=0)
    reason: str = ""
    processed_by: str = "Quản lý kho"


@router.get("/pending")
def pending() -> dict:
    items = [row for row in latest_recommendations(only_actionable=True) if row["internal_status"] == "Chờ xử lý"]
    return {"items": items, "total": len(items)}


@router.get("/all")
def all_items() -> dict:
    items = latest_recommendations(only_actionable=True)
    return {"items": items, "total": len(items)}


@router.get("/{recommendation_id}")
def detail(recommendation_id: str) -> dict:
    item = get_recommendation(recommendation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề xuất")
    return item


@router.post("/{recommendation_id}/internal")
def internal_decision(recommendation_id: str, payload: InternalDecisionRequest) -> dict:
    try:
        return process_internal_decision(recommendation_id, payload.decision, payload.final_quantity, payload.reason, payload.processed_by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đề xuất {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{recommendation_id}/send-telegram")
def send_telegram(recommendation_id: str) -> dict:
    try:
        return send_approved_recommendation(recommendation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đề xuất {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
