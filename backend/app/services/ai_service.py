from __future__ import annotations

import json
import re
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AiLog, Product, Recommendation
from .inventory_service import stock_on_hand

LIVE_MODES = {"live", "enabled", "on", "true", "1"}


def clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def answer_inventory_question(db: Session, question: str) -> dict:
    q = (question or "").strip()
    if not q:
        q = "Hãy tóm tắt tình hình tồn kho hiện tại."

    recs = db.scalars(
        select(Recommendation)
        .join(Product)
        .where(Product.is_active == 1)
        .order_by(Recommendation.recommendation_id)
    ).all()

    codes = re.findall(r"SP\d{3}", q.upper())
    if codes:
        selected = [r for r in recs if r.product_id in codes]
    else:
        selected = recs

    fallback = build_fallback_answer(selected)
    settings = get_settings()
    enabled = (
        (settings.gemini_mode or "").strip().lower() in LIVE_MODES
        and bool((settings.gemini_api_key or "").strip())
    )

    answer = fallback
    generation_status = "FALLBACK"
    model_name = "Python fallback"

    if enabled:
        try:
            gemini_payload = call_gemini(q, selected)
            answer = merge_gemini_answer(gemini_payload, selected, fallback)
            generation_status = "LIVE"
            model_name = settings.gemini_model
        except (requests.RequestException, ValueError, KeyError, TypeError, json.JSONDecodeError):
            # Giữ nguyên phản hồi Python để lỗi Gemini không làm gián đoạn hệ thống.
            answer = fallback
            generation_status = "FALLBACK"
            model_name = "Python fallback"

    answer["generation_status"] = generation_status
    answer["model_name"] = model_name

    product_id = codes[0] if len(codes) == 1 and any(r.product_id == codes[0] for r in selected) else None
    db.add(
        AiLog(
            product_id=product_id,
            question=q,
            answer_json=json.dumps(answer, ensure_ascii=False),
            generation_status=generation_status,
        )
    )
    db.commit()
    return answer


def build_fallback_answer(selected: list[Recommendation]) -> dict:
    need = [r for r in selected if r.business_status in ["Nguy cấp", "Cần nhập"]]
    over = [r for r in selected if r.business_status in ["Dư tồn", "Bán chậm"]]
    high_value = sorted(
        selected,
        key=lambda r: stock_on_hand(r.product) * r.product.purchase_price,
        reverse=True,
    )[:5]
    return {
        "summary": "Kết quả được tổng hợp từ dữ liệu tồn kho và trình bày theo nhóm để quản lý dễ đọc.",
        "need_restock": [short_rec(r) for r in need[:8]],
        "transfer_or_promotion": [short_rec(r) for r in over[:8]],
        "high_inventory_value": [short_rec(r) for r in high_value],
        "suggested_action": build_action_text(need, over),
        "management_note": "Số liệu được lấy từ hệ thống; quyết định cuối cùng do quản lý xác nhận.",
    }


def call_gemini(question: str, selected: list[Recommendation]) -> dict[str, Any]:
    settings = get_settings()
    model = (settings.gemini_model or "gemini-2.5-flash").strip()
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        raise ValueError("Thiếu Gemini API key")

    context = [gemini_context(r) for r in selected]
    prompt_data = {
        "question": question,
        "inventory_data": context,
        "instructions": {
            "language": "vi",
            "do_not_invent_numbers": True,
            "only_use_product_ids_from_inventory_data": True,
            "return_product_ids_only_in_lists": True,
        },
    }

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "summary": {"type": "STRING"},
            "need_restock_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            "transfer_or_promotion_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            "high_inventory_value_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            "suggested_action": {"type": "STRING"},
            "management_note": {"type": "STRING"},
        },
        "required": [
            "summary",
            "need_restock_ids",
            "transfer_or_promotion_ids",
            "high_inventory_value_ids",
            "suggested_action",
            "management_note",
        ],
    }

    system_instruction = (
        "Bạn là trợ lý quản trị tồn kho của Inventory DSS. "
        "Chỉ trả lời dựa trên dữ liệu JSON được cung cấp. "
        "Không tự tạo số liệu, không thay đổi số lượng đề xuất và không quyết định thay quản lý. "
        "Hãy trả lời tự nhiên, ngắn gọn, rõ ràng bằng tiếng Việt. "
        "Các danh sách chỉ được chứa mã sản phẩm có trong inventory_data."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(prompt_data, ensure_ascii=False)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=max(5, int(settings.gemini_timeout_seconds or 30)),
    )
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            detail = response.text
        raise ValueError(f"Gemini API: {detail}")

    body = response.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini không trả về nội dung")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(str(part.get("text") or "") for part in parts).strip()
    if not text:
        raise ValueError("Gemini trả về nội dung rỗng")
    return parse_json_text(text)


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Phản hồi Gemini không đúng cấu trúc")
    return data


def merge_gemini_answer(
    gemini_payload: dict[str, Any],
    selected: list[Recommendation],
    fallback: dict,
) -> dict:
    product_map = {r.product_id: r for r in selected}

    def map_ids(key: str, fallback_key: str, limit: int) -> list[dict]:
        raw_ids = gemini_payload.get(key)
        if not isinstance(raw_ids, list):
            return fallback[fallback_key]
        result: list[dict] = []
        seen: set[str] = set()
        for raw_id in raw_ids:
            product_id = str(raw_id or "").strip().upper()
            if product_id in product_map and product_id not in seen:
                result.append(short_rec(product_map[product_id]))
                seen.add(product_id)
            if len(result) >= limit:
                break
        return result

    summary = clean_markdown(str(gemini_payload.get("summary") or "")) or fallback["summary"]
    suggested_action = clean_markdown(str(gemini_payload.get("suggested_action") or "")) or fallback["suggested_action"]
    management_note = clean_markdown(str(gemini_payload.get("management_note") or "")) or fallback["management_note"]

    return {
        "summary": summary,
        "need_restock": map_ids("need_restock_ids", "need_restock", 8),
        "transfer_or_promotion": map_ids("transfer_or_promotion_ids", "transfer_or_promotion", 8),
        "high_inventory_value": map_ids("high_inventory_value_ids", "high_inventory_value", 5),
        "suggested_action": suggested_action,
        "management_note": management_note,
    }


def gemini_context(r: Recommendation) -> dict:
    product = r.product
    final_quantity = int(r.final_quantity or 0)
    return {
        "product_id": r.product_id,
        "product_name": product.product_name,
        "category": product.category,
        "supplier_name": product.supplier_name,
        "business_status": r.business_status,
        "stock_on_hand": stock_on_hand(product),
        "reserved_quantity": product.inventory.reserved_quantity if product.inventory else product.reserved_quantity,
        "inbound_quantity": product.inventory.confirmed_inbound_quantity if product.inventory else product.inbound_quantity,
        "inventory_position": r.inventory_position,
        "reorder_point": r.reorder_point,
        "forecast_7_days": product.forecast_7_days,
        "purchase_price": product.purchase_price,
        "unit_price": product.unit_price,
        "inventory_purchase_value": stock_on_hand(product) * product.purchase_price,
        "proposed_quantity": r.proposed_quantity,
        "transfer_quantity": r.transfer_quantity,
        "final_quantity": final_quantity,
        "internal_status": r.internal_status,
        "trigger_reason": clean_markdown(r.trigger_reason),
        "action_strategy": clean_markdown(r.action_strategy),
    }


def short_rec(r: Recommendation) -> dict:
    return {
        "product_id": r.product_id,
        "product_name": r.product.product_name,
        "status": r.business_status,
        "stock_on_hand": stock_on_hand(r.product),
        "reorder_point": r.product.reorder_point,
        "forecast_7_days": round(r.product.forecast_7_days, 1),
        "proposed_quantity": r.proposed_quantity,
        "transfer_quantity": r.transfer_quantity,
        "action": clean_markdown(r.action_strategy),
    }


def build_action_text(need: list[Recommendation], over: list[Recommendation]) -> str:
    parts = []
    if need:
        parts.append(
            f"Ưu tiên xử lý {len(need)} sản phẩm thiếu hàng/cần nhập, "
            f"tổng đề xuất nhập {sum(r.proposed_quantity for r in need)} sản phẩm."
        )
    if over:
        parts.append(
            f"Có {len(over)} sản phẩm dư tồn/bán chậm, nên xem xét điều chuyển hoặc khuyến mãi; "
            f"tổng điều chuyển gợi ý {sum(r.transfer_quantity for r in over)} sản phẩm."
        )
    if not parts:
        parts.append("Tồn kho nhìn chung ổn định, tiếp tục theo dõi định kỳ.")
    return " ".join(parts)
