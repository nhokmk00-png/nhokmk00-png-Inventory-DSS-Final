from __future__ import annotations

import json
import uuid
from datetime import datetime

import httpx

from backend.app.config import settings
from backend.app.database import transaction
from backend.app.services.recommendation_service import latest_recommendations


def now_text() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _fallback(product: dict, question: str | None = None) -> dict:
    if question:
        if product["recommendation_type"] == "OVERSTOCK":
            answer = f"{product['product_name']} đang dư tồn. Tồn kho hiện {product['stock_on_hand']} sản phẩm, nên ưu tiên điều chuyển chi nhánh, khuyến mãi hoặc giảm nhập kỳ sau."
        elif product["recommendation_type"] == "SLOW_MOVING":
            answer = f"{product['product_name']} có dấu hiệu bán chậm. Nên hạn chế nhập thêm và cân nhắc chiến lược đẩy bán."
        else:
            answer = f"{product['product_name']} đang ở trạng thái {product['business_status']}. Vị thế tồn kho là {product['inventory_position']:.0f}, điểm đặt hàng lại là {product['reorder_point']:.0f}, số lượng đề xuất là {product['proposed_quantity']}."
        return {"answer": answer, "generation_status": "FALLBACK", "error_message": "Đang dùng nội dung hỗ trợ nội bộ."}
    return {
        "summary": f"{product['product_name']} đang ở trạng thái {product['business_status']}.",
        "reason": product["trigger_reason"],
        "suggested_action": product["action_strategy"],
        "management_note": "Thông tin này hỗ trợ quản lý chọn phương án xử lý phù hợp.",
        "generation_status": "FALLBACK",
        "error_message": "Đang dùng nội dung hỗ trợ nội bộ.",
    }


def _call_gemini(prompt: dict) -> str:
    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
        params={"key": settings.gemini_api_key},
        json={"contents": [{"parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}]},
        timeout=settings.gemini_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["candidates"][0]["content"]["parts"][0]["text"]


def generate_insight(product_id: str, force: bool = False) -> dict:
    products = latest_recommendations(search=product_id)
    product = next((row for row in products if row["product_id"] == product_id), None)
    if not product:
        raise KeyError(product_id)
    with transaction() as connection:
        if not force:
            existing = connection.execute("SELECT * FROM ai_insights WHERE recommendation_id=? ORDER BY created_at DESC LIMIT 1", (product["recommendation_id"],)).fetchone()
            if existing:
                return dict(existing)
        if settings.gemini_mode == "mock":
            content = _fallback(product)
            content["generation_status"] = "SUCCESS"
            content["error_message"] = None
        elif settings.gemini_mode == "live" and settings.gemini_api_key:
            try:
                text = _call_gemini({"role": "Trợ lý quản trị tồn kho", "data": product, "format": "JSON gồm summary, reason, suggested_action, management_note"})
                parsed = json.loads(text)
                content = {"summary": str(parsed["summary"]), "reason": str(parsed["reason"]), "suggested_action": str(parsed["suggested_action"]), "management_note": str(parsed["management_note"]), "generation_status": "SUCCESS", "error_message": None}
            except Exception as exc:
                content = _fallback(product)
                content["error_message"] = str(exc)[:400]
        else:
            content = _fallback(product)
        insight_id = f"AI_{uuid.uuid4().hex[:12].upper()}"
        connection.execute(
            "INSERT INTO ai_insights VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (insight_id, product["recommendation_id"], content["summary"], content["reason"], content["suggested_action"], content["management_note"], content["generation_status"], content.get("error_message"), now_text()),
        )
    content.update({"insight_id": insight_id, "recommendation_id": product["recommendation_id"], "created_at": now_text()})
    return content


def chat(product_id: str, question: str) -> dict:
    products = latest_recommendations(search=product_id)
    product = next((row for row in products if row["product_id"] == product_id), None)
    if not product:
        raise KeyError(product_id)
    if settings.gemini_mode == "mock":
        content = _fallback(product, question)
        content["generation_status"] = "SUCCESS"
        content["error_message"] = None
    elif settings.gemini_mode == "live" and settings.gemini_api_key:
        try:
            answer = _call_gemini({"role": "Trợ lý quản trị tồn kho", "question": question, "data": product})
            content = {"answer": answer, "generation_status": "SUCCESS", "error_message": None}
        except Exception as exc:
            content = _fallback(product, question)
            content["error_message"] = str(exc)[:400]
    else:
        content = _fallback(product, question)
    with transaction() as connection:
        message_id = f"MSG_{uuid.uuid4().hex[:12].upper()}"
        connection.execute("INSERT INTO ai_messages VALUES (?, ?, ?, ?, ?, ?)", (message_id, product_id, question, content["answer"], content["generation_status"], now_text()))
    content.update({"message_id": message_id, "product_id": product_id, "question": question, "created_at": now_text()})
    return content


def _fmt_money(value: float | int | None) -> str:
    return f"{int(round(value or 0)):,}".replace(",", ".") + "đ"


def general_chat(question: str) -> dict:
    rows = latest_recommendations(only_actionable=True)
    all_rows = latest_recommendations()
    restock = [r for r in rows if r["recommendation_type"] == "RESTOCK"]
    strategy = [r for r in rows if r["business_status"] in {"Dư tồn", "Bán chậm"}]
    low_margin = sorted(all_rows, key=lambda r: (r.get("gross_margin_per_unit") or 0))[:5]
    high_capital = sorted(all_rows, key=lambda r: (r.get("inventory_value_cost") or 0), reverse=True)[:5]
    best_profit = sorted(all_rows, key=lambda r: (r.get("forecast_gross_profit_7_days") or 0), reverse=True)[:5]

    if settings.gemini_mode == "live" and settings.gemini_api_key:
        try:
            answer = _call_gemini({
                "role": "Trợ lý quản trị tồn kho",
                "question": question,
                "dashboard_context": {
                    "restock": restock[:8],
                    "strategy": strategy[:8],
                    "high_capital": high_capital,
                    "best_profit": best_profit,
                    "low_margin": low_margin,
                },
            })
            return {"answer": answer, "generation_status": "SUCCESS", "error_message": None, "question": question, "created_at": now_text()}
        except Exception as exc:
            status = "FALLBACK"; error = str(exc)[:400]
        else:
            status = "SUCCESS"; error = None
    else:
        status = "FALLBACK"; error = "Đang dùng nội dung hỗ trợ nội bộ."

    q = question.lower()
    if any(k in q for k in ["giá", "ưu đãi", "khách hàng lớn", "discount", "chiết khấu"]):
        examples = "; ".join([f"{r['product_id']} {r['product_name']} giá bán {_fmt_money(r['unit_price'])}, giá nhập {_fmt_money(r['purchase_price'])}, lãi gộp/SP {_fmt_money(r['gross_margin_per_unit'])}" for r in best_profit[:4]])
        answer = f"Có thể linh hoạt giá xuất cho khách hàng lớn nếu vẫn đảm bảo lãi gộp. Nhóm đang có biên lợi nhuận tốt để cân nhắc ưu đãi: {examples}. Khi lập phiếu xuất, nên nhập đơn giá thực tế để hệ thống ghi nhận đúng doanh thu và lãi gộp."
    elif any(k in q for k in ["lợi nhuận", "lãi", "doanh thu"]):
        examples = "; ".join([f"{r['product_id']} {r['product_name']} lãi gộp dự báo 7 ngày {_fmt_money(r['forecast_gross_profit_7_days'])}" for r in best_profit[:5]])
        answer = f"Nếu ưu tiên lợi nhuận, nên tập trung các sản phẩm có lãi gộp dự báo cao: {examples}. Nhóm này nên được ưu tiên nhập/giữ hàng nếu tốc độ bán vẫn tốt."
    elif any(k in q for k in ["vốn", "tồn nhiều", "giữ vốn", "dư tồn"]):
        examples = "; ".join([f"{r['product_id']} {r['product_name']} vốn tồn {_fmt_money(r['inventory_value_cost'])}, trạng thái {r['business_status']}" for r in high_capital[:5]])
        answer = f"Nhóm đang giữ vốn nhiều nhất là: {examples}. Với sản phẩm dư tồn hoặc bán chậm, nên điều chuyển chi nhánh, combo/khuyến mãi hoặc tạm dừng nhập thêm để giảm vốn bị giữ trong kho."
    elif any(k in q for k in ["so sánh", "sp"]):
        mentioned = [r for r in all_rows if r['product_id'].lower() in q]
        if len(mentioned) >= 2:
            examples = "; ".join([f"{r['product_id']} {r['business_status']}, tồn {r['stock_on_hand']}, đề xuất {r['proposed_quantity']}, lãi gộp/SP {_fmt_money(r['gross_margin_per_unit'])}" for r in mentioned])
            answer = f"So sánh nhanh: {examples}. Nên ưu tiên sản phẩm vừa có rủi ro thiếu hàng vừa có lãi gộp tốt; sản phẩm dư tồn thì ưu tiên xử lý tồn trước khi nhập thêm."
        else:
            answer = "Bạn có thể nhập câu hỏi kiểu: so sánh SP001 và SP004 theo tồn kho, đề xuất nhập, giá trị vốn và lãi gộp."
    elif any(k in q for k in ["nhập", "ưu tiên", "cần mua"]):
        examples = "; ".join([f"{r['product_id']} {r['product_name']} ({r['business_status']}, đề xuất {r['proposed_quantity']})" for r in restock[:5]]) or "không có sản phẩm cần nhập"
        answer = f"Nhóm nên ưu tiên nhập gồm: {examples}. Khi duyệt, nên kiểm tra thêm ngân sách, giá nhập hiện tại và lãi gộp dự kiến trước khi gửi thông báo cho cấp trên."
    else:
        top_restock = "; ".join([f"{r['product_id']} {r['business_status']} đề xuất {r['proposed_quantity']}" for r in restock[:4]]) or "không có"
        top_strategy = "; ".join([f"{r['product_id']} {r['business_status']} tồn {r['stock_on_hand']}" for r in strategy[:4]]) or "không có"
        answer = f"Tình hình hiện tại: nhóm cần nhập gồm {top_restock}; nhóm cần chiến lược tồn kho gồm {top_strategy}. Nên xử lý song song: duyệt nhập cho sản phẩm có nguy cơ thiếu và giảm tồn cho sản phẩm bán chậm/dư tồn."
    return {"answer": answer, "generation_status": status, "error_message": error, "question": question, "created_at": now_text()}
