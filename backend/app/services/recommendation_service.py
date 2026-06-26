from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.database import connect, transaction

STATUS_PRIORITY = {"Nguy cấp": 1, "Cần nhập": 2, "Dư tồn": 3, "Bán chậm": 4, "Theo dõi": 5, "An toàn": 6}


def now_text() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _base_query() -> str:
    return """
        SELECT p.product_id, p.product_name, p.category, p.supplier_name, p.branch_name, p.unit,
               p.unit_price, p.purchase_price, (p.unit_price - p.purchase_price) AS gross_margin_per_unit,
               i.stock_on_hand, i.reserved_quantity, i.confirmed_inbound_quantity, i.updated_at,
               f.batch_id, f.forecast_date, f.forecast_quantity_7_days, f.average_daily_demand,
               r.recommendation_id, r.recommendation_type, r.business_status, r.priority_rank,
               r.available_stock, r.inventory_position, r.reorder_point, r.target_stock,
               r.proposed_quantity, r.final_quantity, r.action_strategy, r.trigger_reason,
               r.internal_status, r.internal_reason, r.processed_by, r.processed_at,
               r.telegram_status, r.boss_status, r.boss_final_quantity, r.boss_reason, r.boss_responded_at,
               ROUND(f.forecast_quantity_7_days * p.unit_price, 0) AS forecast_revenue_7_days,
               ROUND(f.forecast_quantity_7_days * (p.unit_price - p.purchase_price), 0) AS forecast_gross_profit_7_days,
               ROUND(i.stock_on_hand * p.unit_price, 0) AS inventory_value_selling,
               ROUND(i.stock_on_hand * p.purchase_price, 0) AS inventory_value_cost,
               ai.summary AS ai_summary, ai.reason AS ai_reason, ai.suggested_action AS ai_suggested_action
        FROM recommendations r
        JOIN products p ON p.product_id=r.product_id
        JOIN inventory i ON i.product_id=p.product_id
        JOIN forecasts f ON f.forecast_id=r.forecast_id
        LEFT JOIN ai_insights ai ON ai.insight_id=(SELECT insight_id FROM ai_insights WHERE recommendation_id=r.recommendation_id ORDER BY created_at DESC LIMIT 1)
        WHERE 1=1
    """


def latest_recommendations(search: str | None = None, status: str | None = None, only_actionable: bool = False) -> list[dict]:
    query = _base_query()
    params: list[str] = []
    if search:
        s = f"%{search.lower()}%"
        query += " AND (LOWER(p.product_id) LIKE ? OR LOWER(p.product_name) LIKE ? OR LOWER(p.category) LIKE ? OR LOWER(p.supplier_name) LIKE ?)"
        params.extend([s, s, s, s])
    if status:
        query += " AND r.business_status=?"
        params.append(status)
    if only_actionable:
        query += " AND r.business_status<>'An toàn'"
    query += " ORDER BY r.priority_rank, r.proposed_quantity DESC, p.product_name"
    with connect() as connection:
        rows = [dict(row) for row in connection.execute(query, params).fetchall()]
    unique = {}
    for row in rows:
        unique[row["product_id"]] = row
    return list(unique.values())


def get_recommendation(recommendation_id: str) -> dict | None:
    with connect() as connection:
        rows = [dict(row) for row in connection.execute(_base_query() + " AND r.recommendation_id=?", (recommendation_id,)).fetchall()]
    return rows[0] if rows else None


def classify(stock: int, reserved: int, inbound: int, forecast_7d: float, lead: int, safety: int, minimum: int) -> dict:
    available = stock - reserved
    position = available + inbound
    avg = forecast_7d / 7
    reorder = avg * lead + safety
    target = avg * (lead + 7) + safety
    suggested = max(0, round(target - position))
    if stock > 300:
        status = "Dư tồn"; rec_type = "OVERSTOCK"; proposed = 0; strategy = "Điều chuyển sang chi nhánh khác, chạy khuyến mãi hoặc giảm nhập kỳ sau."; reason = f"Tồn kho {stock} vượt ngưỡng quản lý 300 sản phẩm."
    elif stock >= 180 and forecast_7d <= 40:
        status = "Bán chậm"; rec_type = "SLOW_MOVING"; proposed = 0; strategy = "Tạm dừng nhập thêm, xem xét combo, khuyến mãi hoặc điều chuyển nội bộ."; reason = f"Tồn kho {stock} cao nhưng dự báo 7 ngày chỉ {forecast_7d:.0f}."
    elif position <= minimum:
        status = "Nguy cấp"; rec_type = "RESTOCK"; proposed = suggested; strategy = "Ưu tiên duyệt nhập ngay hoặc điều chuyển nội bộ trong ngày."; reason = f"Vị thế tồn kho {position:.0f} thấp hơn tồn kho tối thiểu {minimum}."
    elif position <= reorder:
        status = "Cần nhập"; rec_type = "RESTOCK"; proposed = suggested; strategy = "Lên kế hoạch nhập bổ sung theo số lượng đề xuất."; reason = f"Vị thế tồn kho {position:.0f} thấp hơn điểm đặt hàng lại {reorder:.0f}."
    elif position <= reorder * 1.3:
        status = "Theo dõi"; rec_type = "MONITOR"; proposed = suggested; strategy = "Theo dõi thêm nhu cầu bán và chuẩn bị nhập nếu bán tăng."; reason = f"Vị thế tồn kho {position:.0f} gần ngưỡng cần đặt hàng."
    else:
        status = "An toàn"; rec_type = "NORMAL"; proposed = 0; strategy = "Tiếp tục theo dõi định kỳ."; reason = "Tồn kho đang ở mức phù hợp."
    return {"recommendation_type": rec_type, "business_status": status, "priority_rank": STATUS_PRIORITY[status], "available_stock": available, "inventory_position": position, "reorder_point": reorder, "target_stock": target, "proposed_quantity": proposed, "action_strategy": strategy, "trigger_reason": reason}


def recalc_for_product(connection, product_id: str) -> dict:
    row = connection.execute(
        """
        SELECT p.*, i.stock_on_hand, i.reserved_quantity, i.confirmed_inbound_quantity,
               f.forecast_id, f.forecast_quantity_7_days
        FROM products p JOIN inventory i ON i.product_id=p.product_id
        JOIN forecasts f ON f.product_id=p.product_id
        WHERE p.product_id=? ORDER BY f.created_at DESC LIMIT 1
        """,
        (product_id,),
    ).fetchone()
    if not row:
        raise KeyError(product_id)
    data = classify(row["stock_on_hand"], row["reserved_quantity"], row["confirmed_inbound_quantity"], row["forecast_quantity_7_days"], row["lead_time_days"], row["safety_stock"], row["minimum_stock"])
    rec = connection.execute("SELECT recommendation_id FROM recommendations WHERE forecast_id=?", (row["forecast_id"],)).fetchone()
    if rec:
        connection.execute(
            """
            UPDATE recommendations SET recommendation_type=?, business_status=?, priority_rank=?, available_stock=?, inventory_position=?,
              reorder_point=?, target_stock=?, proposed_quantity=?, final_quantity=NULL, action_strategy=?, trigger_reason=?,
              internal_status='Chờ xử lý', internal_reason=NULL, processed_by=NULL, processed_at=NULL, telegram_status='Chưa gửi',
              boss_status='Không áp dụng', boss_final_quantity=NULL, boss_reason=NULL, boss_responded_at=NULL, created_at=?
            WHERE recommendation_id=?
            """,
            (data["recommendation_type"], data["business_status"], data["priority_rank"], data["available_stock"], data["inventory_position"], data["reorder_point"], data["target_stock"], data["proposed_quantity"], data["action_strategy"], data["trigger_reason"], now_text(), rec["recommendation_id"]),
        )
        rec_id = rec["recommendation_id"]
    else:
        rec_id = f"REC_{product_id}_{uuid.uuid4().hex[:8].upper()}"
        connection.execute(
            """
            INSERT INTO recommendations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 'Chờ xử lý', NULL, NULL, NULL, 'Chưa gửi', 'Không áp dụng', NULL, NULL, NULL, ?)
            """,
            (rec_id, row["forecast_id"], product_id, data["recommendation_type"], data["business_status"], data["priority_rank"], data["available_stock"], data["inventory_position"], data["reorder_point"], data["target_stock"], data["proposed_quantity"], data["action_strategy"], data["trigger_reason"], now_text()),
        )
    data.update({"recommendation_id": rec_id, "product_id": product_id})
    return data


def process_internal_decision(recommendation_id: str, decision: str, final_quantity: int | None, reason: str, processed_by: str) -> dict:
    status_map = {"APPROVE": "Đã duyệt", "ADJUST": "Đã điều chỉnh", "REJECT": "Đã hủy"}
    if decision not in status_map:
        raise ValueError("Quyết định không hợp lệ.")
    with transaction() as connection:
        rec = connection.execute("SELECT * FROM recommendations WHERE recommendation_id=?", (recommendation_id,)).fetchone()
        if not rec:
            raise KeyError(recommendation_id)
        if decision == "REJECT":
            final = 0
            if not reason.strip():
                raise ValueError("Cần nhập lý do khi hủy đề xuất.")
        elif decision == "APPROVE":
            final = rec["proposed_quantity"]
        else:
            if final_quantity is None or final_quantity < 0:
                raise ValueError("Số lượng điều chỉnh không hợp lệ.")
            final = final_quantity
        connection.execute(
            """
            UPDATE recommendations SET internal_status=?, final_quantity=?, internal_reason=?, processed_by=?, processed_at=?, telegram_status='Chưa gửi', boss_status='Không áp dụng'
            WHERE recommendation_id=?
            """,
            (status_map[decision], final, reason, processed_by, now_text(), recommendation_id),
        )
    return get_recommendation(recommendation_id) or {}


def product_journey(product_id: str) -> dict:
    with connect() as connection:
        product = connection.execute("SELECT * FROM products WHERE product_id=?", (product_id,)).fetchone()
        if not product:
            raise KeyError(product_id)
        recommendations = latest_recommendations(search=product_id)
        transactions = [dict(row) for row in connection.execute("SELECT * FROM inventory_transactions WHERE product_id=? ORDER BY transaction_date DESC LIMIT 50", (product_id,)).fetchall()]
        demand_history = [dict(row) for row in connection.execute("SELECT demand_date, net_demand, promotion_flag FROM daily_demand WHERE product_id=? ORDER BY demand_date", (product_id,)).fetchall()]
        alerts = [dict(row) for row in connection.execute("SELECT * FROM alerts WHERE product_id=? ORDER BY created_at DESC LIMIT 20", (product_id,)).fetchall()]
        chats = [dict(row) for row in connection.execute("SELECT * FROM ai_messages WHERE product_id=? ORDER BY created_at DESC LIMIT 10", (product_id,)).fetchall()]
    return {"product": dict(product), "recommendations": recommendations, "transactions": transactions, "demand_history": demand_history, "alerts": alerts, "ai_messages": chats}
