from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import settings
from backend.app.services.notification_service import list_alerts, send_summary

router = APIRouter(prefix="/api/notifications", tags=["Thông báo"])


@router.get("/status")
def status() -> dict:
    return {"telegram_mode": settings.telegram_mode, "configured": bool(settings.telegram_bot_token and settings.telegram_chat_id), "note": "Đề xuất được gửi sau bước duyệt/điều chỉnh/hủy nội bộ."}


@router.post("/summary")
def summary() -> dict:
    return send_summary()


@router.get("")
def alerts() -> dict:
    items = list_alerts()
    return {"items": items, "total": len(items)}
