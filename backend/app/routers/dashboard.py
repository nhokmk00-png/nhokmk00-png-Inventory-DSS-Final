from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from backend.app.database import connect
from backend.app.services.inventory_service import all_transactions, daily_flow, day_transactions, list_inventory
from backend.app.services.recommendation_service import latest_recommendations, product_journey

router = APIRouter(prefix="/api", tags=["Tổng quan"])


def _status_counts(rows: list[dict]) -> dict:
    labels = ["Nguy cấp", "Cần nhập", "Dư tồn", "Bán chậm", "Theo dõi", "An toàn"]
    return {label: sum(1 for row in rows if row["business_status"] == label) for label in labels}


@router.get("/health")
def health() -> dict:
    with connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        fk_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        products = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    return {"status": "ok", "schema_version": version, "foreign_key_errors": fk_errors, "products": products}


@router.get("/summary")
def summary() -> dict:
    rows = latest_recommendations()
    inventory = list_inventory()
    actionable = [r for r in rows if r["business_status"] != "An toàn"]
    restock = [r for r in rows if r["recommendation_type"] == "RESTOCK" and r["business_status"] in {"Nguy cấp", "Cần nhập"}]
    strategy = [r for r in rows if r["business_status"] in {"Dư tồn", "Bán chậm"}]
    pending = [r for r in rows if r["internal_status"] == "Chờ xử lý" and r["business_status"] != "An toàn"]
    ready_to_send = [r for r in rows if r["internal_status"] in {"Đã duyệt", "Đã điều chỉnh", "Đã hủy"} and r["telegram_status"] == "Chưa gửi"]
    priority_names = [r["product_name"] for r in (restock + strategy)[:3]]
    with connect() as connection:
        alerts = [dict(row) for row in connection.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 8").fetchall()]
        imports = [dict(row) for row in connection.execute("SELECT * FROM excel_imports ORDER BY import_date DESC LIMIT 5").fetchall()]
    last_updated = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    quick_report = {
        "headline": f"Hôm nay có {len(restock)} sản phẩm cần nhập.",
        "risk_line": f"{sum(1 for r in restock if r['business_status'] == 'Nguy cấp')} sản phẩm nguy cấp và {sum(1 for r in restock if r['business_status'] == 'Cần nhập')} sản phẩm cần nhập.",
        "strategy_line": f"Có {len(strategy)} sản phẩm dư tồn hoặc bán chậm cần xem xét chiến lược.",
        "quantity_line": f"Tổng số lượng đề xuất nhập: {sum(r['proposed_quantity'] for r in restock):,.0f} sản phẩm.".replace(',', '.'),
        "approval_line": f"Có {len(pending)} đề xuất đang chờ xử lý nội bộ và {len(ready_to_send)} đề xuất sẵn sàng gửi thông báo.",
        "priority_line": "Sản phẩm ưu tiên: " + (", ".join(priority_names) if priority_names else "Chưa có sản phẩm cần xử lý."),
        "last_updated": last_updated,
    }
    return {"total_products": len(inventory), "total_stock_units": sum(i["stock_on_hand"] for i in inventory), "actionable_count": len(actionable), "restock_count": len(restock), "strategy_count": len(strategy), "pending_approval_count": len(pending), "ready_to_send_count": len(ready_to_send), "total_recommended_quantity": sum(r["proposed_quantity"] for r in restock), "total_inventory_value_cost": sum((i.get("inventory_value_cost") or 0) for i in inventory), "total_inventory_value_selling": sum((i.get("inventory_value_selling") or 0) for i in inventory), "last_updated": last_updated, "status_counts": _status_counts(rows), "critical_items": restock[:6], "strategy_items": strategy[:6], "top_actionable": actionable[:10], "latest_alerts": alerts, "latest_imports": imports, "inventory_flow": daily_flow(), "quick_report": quick_report}


@router.get("/recommendations")
def recommendations(search: str | None = Query(default=None), status: str | None = None, only_actionable: bool = False) -> dict:
    items = latest_recommendations(search, status, only_actionable)
    return {"items": items, "total": len(items)}


@router.get("/products")
def products(search: str | None = Query(default=None)) -> dict:
    items = list_inventory(search)
    return {"items": items, "total": len(items)}


@router.get("/flow/days")
def flow_days() -> dict:
    items = daily_flow()
    return {"items": items, "total": len(items)}


@router.get("/flow/transactions")
def flow_all_transactions() -> dict:
    items = all_transactions()
    return {"date": "Tất cả", "items": items, "total": len(items)}


@router.get("/flow/days/{date_text}")
def flow_day_detail(date_text: str) -> dict:
    items = day_transactions(date_text)
    return {"date": date_text, "items": items, "total": len(items)}


@router.get("/products/{product_id}/journey")
def journey(product_id: str) -> dict:
    return product_journey(product_id.upper())
