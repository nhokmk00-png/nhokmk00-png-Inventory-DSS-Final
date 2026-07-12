from __future__ import annotations

from datetime import datetime

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Notification, Product, Recommendation
from .inventory_service import effective_action_strategy, recommendation_dict
from .report_service import build_recommendations_workbook

LIVE_MODES = {"live", "enabled", "on", "true", "1"}


def _telegram_config() -> tuple[bool, str, str]:
    settings = get_settings()
    mode = (settings.telegram_mode or "").strip().lower()
    token = (settings.telegram_bot_token or "").strip()
    chat_id = (settings.telegram_chat_id or "").strip()
    return mode in LIVE_MODES and bool(token) and bool(chat_id), token, chat_id


def _send_telegram_message(message: str) -> tuple[str, str]:
    enabled, token, chat_id = _telegram_config()
    if not enabled:
        return "SAVED", "Telegram chưa được bật hoặc còn thiếu Bot Token/Chat ID."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
        if response.ok:
            return "SENT", ""
        try:
            detail = response.json().get("description", response.text)
        except ValueError:
            detail = response.text
        return "FAILED", f"Telegram sendMessage: {detail}"
    except requests.RequestException as exc:
        return "FAILED", f"Telegram sendMessage: {exc}"


def _send_telegram_document(content: bytes, filename: str, caption: str) -> tuple[str, str]:
    enabled, token, chat_id = _telegram_config()
    if not enabled:
        return "SAVED", "Telegram chưa được bật hoặc còn thiếu Bot Token/Chat ID."

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {
        "document": (
            filename,
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {"chat_id": chat_id, "caption": caption}
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        if response.ok:
            return "SENT", ""
        try:
            detail = response.json().get("description", response.text)
        except ValueError:
            detail = response.text
        return "FAILED", f"Telegram sendDocument: {detail}"
    except requests.RequestException as exc:
        return "FAILED", f"Telegram sendDocument: {exc}"


def build_recommendation_message(rec: Recommendation) -> str:
    data = recommendation_dict(rec)
    processed = data["internal_status"] in {"Đã duyệt", "Đã điều chỉnh"}
    lines = [
        "📌 THÔNG BÁO XỬ LÝ TỒN KHO",
        f"Sản phẩm: {data['product_id']} - {data['product_name']}",
        f"Tình trạng: {data['business_status']}",
        (
            f"Tồn hiện tại: {data['stock_on_hand']} | "
            f"Điểm đặt hàng lại: {data['reorder_point']} | "
            f"Dự báo 7 ngày: {data['forecast_7_days']}"
        ),
    ]

    if data["business_status"] in {"Dư tồn", "Bán chậm"}:
        if processed:
            lines.append(f"Số lượng xử lý theo quyết định quản lý: {data['final_quantity']}")
        else:
            lines.append(f"Số lượng điều chuyển hệ thống gợi ý: {data['transfer_quantity']}")
    elif data["business_status"] in {"Nguy cấp", "Cần nhập"}:
        if processed:
            lines.append(f"Số lượng nhập theo quyết định quản lý: {data['final_quantity']}")
        else:
            lines.append(f"Số lượng hệ thống đề xuất nhập: {data['proposed_quantity']}")
            if data["transfer_quantity"]:
                lines.append(f"Số lượng điều chuyển gợi ý: {data['transfer_quantity']}")
    else:
        lines.append("Số lượng cần xử lý: 0")

    lines.extend(
        [
            f"Xử lý nội bộ: {data['internal_status']}",
            f"Phương án thực hiện: {effective_action_strategy(rec)}",
            f"Người xử lý: {data['processed_by'] or 'Chưa ghi nhận'}",
            f"Lý do: {data['internal_reason'] or 'Chưa ghi nhận'}",
        ]
    )
    return "\n".join(lines)


def send_recommendation(db: Session, recommendation_id: int) -> dict:
    rec = db.get(Recommendation, recommendation_id)
    if not rec:
        raise ValueError("Không tìm thấy đề xuất")

    message = build_recommendation_message(rec)
    status, error = _send_telegram_message(message)

    if status == "SENT":
        rec.telegram_status = "Đã gửi"
    elif status == "FAILED":
        rec.telegram_status = "Gửi thất bại"
    else:
        rec.telegram_status = "Đã lưu thông báo"

    notification = Notification(
        product_id=rec.product_id,
        recommendation_id=rec.recommendation_id,
        notification_type="DETAIL",
        product_name_snapshot=rec.product.product_name if rec.product else rec.product_id,
        business_status_snapshot=rec.business_status,
        message=message,
        send_status=status,
        sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "SENT" else "",
        error_message=error,
    )
    db.add(notification)
    db.commit()
    return {"send_status": status, "message": message, "error_message": error}


def send_summary(db: Session) -> dict:
    recs = db.scalars(
        select(Recommendation)
        .join(Product)
        .where(Product.is_active == 1)
        .order_by(Recommendation.recommendation_id)
    ).all()
    need = [r for r in recs if r.business_status in {"Nguy cấp", "Cần nhập"}]
    strategy = [r for r in recs if r.business_status in {"Dư tồn", "Bán chậm"}]
    waiting = [r for r in recs if r.internal_status == "Chờ xử lý"]

    urgent_codes = ", ".join(r.product_id for r in need[:8]) or "Không có"
    strategy_codes = ", ".join(r.product_id for r in strategy[:8]) or "Không có"

    effective_need = sum(
        (r.final_quantity if r.internal_status in {"Đã duyệt", "Đã điều chỉnh"} else r.proposed_quantity)
        for r in need
    )
    effective_transfer = sum(
        (r.final_quantity if r.internal_status in {"Đã duyệt", "Đã điều chỉnh"} else r.transfer_quantity)
        for r in strategy
    )

    message = "\n".join(
        [
            "📊 BÁO CÁO TỒN KHO TỔNG HỢP",
            f"Cần nhập/nguy cấp: {len(need)} SP ({urgent_codes})",
            f"Dư tồn/bán chậm: {len(strategy)} SP ({strategy_codes})",
            f"Chờ xử lý nội bộ: {len(waiting)} đề xuất",
            f"Tổng số lượng nhập theo đề xuất/quyết định: {effective_need} sản phẩm",
            f"Tổng số lượng điều chuyển/xử lý: {effective_transfer} sản phẩm",
            "File Excel chi tiết được gửi kèm ngay sau tin nhắn này.",
        ]
    )

    message_status, message_error = _send_telegram_message(message)
    document_status = "SAVED"
    document_error = ""

    if message_status == "SENT":
        report_bytes = build_recommendations_workbook(db)
        document_status, document_error = _send_telegram_document(
            report_bytes,
            "bao_cao_xu_ly_ton_kho.xlsx",
            "Báo cáo xử lý tồn kho chi tiết",
        )
    elif message_status == "SAVED":
        document_status = "SAVED"
        document_error = "Telegram chưa được bật nên file Excel chỉ có thể tải trên Dashboard."

    if message_status == "SENT" and document_status == "SENT":
        overall_status = "SENT"
    elif message_status == "SAVED":
        overall_status = "SAVED"
    elif message_status == "SENT" and document_status == "FAILED":
        overall_status = "PARTIAL"
    else:
        overall_status = "FAILED"

    errors = "; ".join(item for item in [message_error, document_error] if item)
    notification = Notification(
        notification_type="SUMMARY",
        message=message,
        send_status=overall_status,
        sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S") if overall_status in {"SENT", "PARTIAL"} else "",
        error_message=errors,
    )
    db.add(notification)
    db.commit()

    return {
        "send_status": overall_status,
        "message_status": message_status,
        "document_status": document_status,
        "message": message,
        "error_message": errors,
    }


def list_notifications(db: Session) -> dict:
    items = db.scalars(select(Notification).order_by(Notification.alert_id.desc()).limit(100)).all()
    return {"items": [notification_dict(item) for item in items]}


def notification_dict(notification: Notification) -> dict:
    return {
        "alert_id": notification.alert_id,
        "product_id": notification.product_id,
        "recommendation_id": notification.recommendation_id,
        "notification_type": notification.notification_type,
        "message": notification.message,
        "send_status": notification.send_status,
        "sent_at": notification.sent_at,
        "error_message": notification.error_message,
        "created_at": notification.created_at,
    }
