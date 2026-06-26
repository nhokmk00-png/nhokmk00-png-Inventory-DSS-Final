from __future__ import annotations

import uuid
from datetime import datetime

import httpx

from backend.app.config import settings
from backend.app.database import connect, transaction
from backend.app.services.recommendation_service import get_recommendation, latest_recommendations
from backend.app.services.report_service import build_recommendation_report


def now_text() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _send_text(message: str) -> tuple[str, str | None]:
    if settings.telegram_mode == "disabled" or not settings.telegram_bot_token or not settings.telegram_chat_id:
        return "SKIPPED", "Telegram chưa cấu hình; thông báo được lưu vào lịch sử."
    if settings.telegram_mode == "mock":
        return "SENT", None
    payload = {"chat_id": settings.telegram_chat_id, "text": message}
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
            timeout=settings.telegram_timeout_seconds,
        )
        data = response.json()
        if response.is_success and data.get("ok"):
            return "SENT", None
        return "FAILED", data.get("description") or response.text[:400]
    except Exception as exc:
        return "FAILED", str(exc)[:400]


def _send_document(message: str, content: bytes, filename: str) -> tuple[str, str | None]:
    if settings.telegram_mode == "disabled" or not settings.telegram_bot_token or not settings.telegram_chat_id:
        return "SKIPPED", "Telegram chưa cấu hình; báo cáo được tạo và thông báo được lưu vào lịch sử."
    if settings.telegram_mode == "mock":
        return "SENT", None
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument",
            data={"chat_id": settings.telegram_chat_id, "caption": message},
            files={"document": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=settings.telegram_timeout_seconds,
        )
        data = response.json()
        if response.is_success and data.get("ok"):
            return "SENT", None
        return "FAILED", data.get("description") or response.text[:400]
    except Exception as exc:
        return "FAILED", str(exc)[:400]


def build_approval_message(rec: dict) -> str:
    internal_text = rec["internal_status"]
    final_qty = rec["final_quantity"] if rec["final_quantity"] is not None else rec["proposed_quantity"]
    if rec["recommendation_type"] == "RESTOCK":
        action = f"Số lượng đề xuất/đã xử lý: {rec['proposed_quantity']} → {final_qty}"
    else:
        action = f"Phương án xử lý: {rec['action_strategy']}"
    return (
        f"📌 Thông báo xử lý tồn kho\n"
        f"Sản phẩm: {rec['product_id']} - {rec['product_name']}\n"
        f"Tình trạng: {rec['business_status']}\n"
        f"Xử lý nội bộ: {internal_text}\n"
        f"{action}\n"
        f"Người xử lý: {rec.get('processed_by') or 'Chưa ghi nhận'}\n"
        f"Lý do: {rec.get('internal_reason') or rec.get('trigger_reason') or ''}\n"
    )


def send_approved_recommendation(recommendation_id: str, force: bool = False) -> dict:
    rec = get_recommendation(recommendation_id)
    if not rec:
        raise KeyError(recommendation_id)
    if rec["internal_status"] == "Chờ xử lý" and not force:
        raise ValueError("Cần duyệt, điều chỉnh hoặc hủy nội bộ trước khi gửi Telegram.")
    message = build_approval_message(rec)
    status, error = _send_text(message)
    with transaction() as connection:
        alert_id = f"ALT_{uuid.uuid4().hex[:12].upper()}"
        connection.execute(
            """
            INSERT INTO alerts VALUES (?, 'APPROVAL', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (alert_id, recommendation_id, rec["product_id"], rec["product_name"], rec["business_status"], message, status, now_text() if status == "SENT" else None, error, now_text()),
        )
        connection.execute("UPDATE recommendations SET telegram_status=? WHERE recommendation_id=?", ("Đã gửi" if status == "SENT" else ("Bỏ qua" if status == "SKIPPED" else "Lỗi"), recommendation_id))
    return {"recommendation_id": recommendation_id, "send_status": status, "error_message": error, "message": message}


def send_summary(force: bool = False) -> dict:
    rows = latest_recommendations(only_actionable=True)
    pending = [r for r in rows if r["internal_status"] == "Chờ xử lý"]
    approved = [r for r in rows if r["internal_status"] in {"Đã duyệt", "Đã điều chỉnh"} and r["telegram_status"] == "Chưa gửi"]
    restock = [r for r in rows if r["recommendation_type"] == "RESTOCK" and r["business_status"] in {"Nguy cấp", "Cần nhập"}]
    strategy = [r for r in rows if r["business_status"] in {"Dư tồn", "Bán chậm"}]
    top_restock = ", ".join([f"{r['product_id']}" for r in restock[:5]]) or "không có"
    top_strategy = ", ".join([f"{r['product_id']}" for r in strategy[:5]]) or "không có"
    report_bytes = build_recommendation_report()
    message = (
        f"📊 Báo cáo tồn kho {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"Cần nhập: {len(restock)} SP ({top_restock}).\n"
        f"Dư tồn/bán chậm: {len(strategy)} SP ({top_strategy}).\n"
        f"Chờ xử lý nội bộ: {len(pending)}. Sẵn sàng gửi thông báo: {len(approved)}.\n"
        f"Chi tiết nằm trong file Excel đính kèm."
    )
    status, error = _send_document(message, report_bytes, "bao_cao_xu_ly_ton_kho.xlsx")
    with transaction() as connection:
        alert_id = f"ALT_{uuid.uuid4().hex[:12].upper()}"
        connection.execute("INSERT INTO alerts VALUES (?, 'SUMMARY', NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?)", (alert_id, message, status, now_text() if status == "SENT" else None, error, now_text()))
    return {"send_status": status, "error_message": error, "message": message, "report_attached": True, "report_file": "bao_cao_xu_ly_ton_kho.xlsx"}


def list_alerts(limit: int = 80) -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]
