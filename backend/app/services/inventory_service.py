from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import DailyDemand, Forecast, Inventory, InventoryTransaction, Product, Recommendation, now_text

STATUS_ORDER = ["Nguy cấp", "Cần nhập", "Dư tồn", "Bán chậm", "Theo dõi", "An toàn"]
STATUS_CLASS = {
    "Nguy cấp": "critical",
    "Cần nhập": "high",
    "Dư tồn": "over",
    "Bán chậm": "slow",
    "Theo dõi": "medium",
    "An toàn": "low",
}


def get_inventory(product: Product) -> Inventory | None:
    return product.inventory


def stock_on_hand(product: Product) -> int:
    return product.inventory.stock_on_hand if product.inventory else product.stock_on_hand


def reserved_quantity(product: Product) -> int:
    return product.inventory.reserved_quantity if product.inventory else product.reserved_quantity


def inbound_quantity(product: Product) -> int:
    return product.inventory.confirmed_inbound_quantity if product.inventory else product.inbound_quantity


def inventory_position(product: Product) -> int:
    return stock_on_hand(product) - reserved_quantity(product) + inbound_quantity(product)


def sync_product_inventory_cache(product: Product) -> None:
    if product.inventory:
        product.stock_on_hand = product.inventory.stock_on_hand
        product.reserved_quantity = product.inventory.reserved_quantity
        product.inbound_quantity = product.inventory.confirmed_inbound_quantity


def product_dict(p: Product) -> dict:
    latest = p.recommendations[-1] if p.recommendations else None
    return {
        "product_id": p.product_id,
        "product_name": p.product_name,
        "category": p.category,
        "supplier_name": p.supplier_name,
        "unit": p.unit,
        "branch_name": p.branch_name,
        "purchase_price": p.purchase_price,
        "unit_price": p.unit_price,
        "gross_margin": p.unit_price - p.purchase_price,
        "lead_time_days": p.lead_time_days,
        "safety_stock": p.safety_stock,
        "minimum_stock": p.minimum_stock,
        "reorder_point": p.reorder_point,
        "stock_on_hand": stock_on_hand(p),
        "reserved_quantity": reserved_quantity(p),
        "inbound_quantity": inbound_quantity(p),
        "inventory_position": inventory_position(p),
        "avg_daily_demand": p.avg_daily_demand,
        "forecast_7_days": p.forecast_7_days,
        "business_status": p.business_status,
        "is_active": p.is_active,
        "internal_status": latest.internal_status if latest else "Chưa có đề xuất",
        "telegram_status": latest.telegram_status if latest else "Chưa gửi",
        "updated_at": p.updated_at,
    }


def effective_action_strategy(r: Recommendation) -> str:
    """Trả về phương án thực hiện theo số lượng quản lý đã chốt.

    Số lượng gợi ý ban đầu vẫn được lưu riêng để đối chiếu, nhưng sau khi quản lý
    duyệt/điều chỉnh thì nội dung gửi đi phải phản ánh quyết định cuối cùng.
    """
    final_qty = int(r.final_quantity or 0)
    processed = r.internal_status in {"Đã duyệt", "Đã điều chỉnh"}

    if processed and r.business_status in {"Dư tồn", "Bán chậm"}:
        return (
            f"Thực hiện điều chuyển hoặc xử lý {final_qty} sản phẩm theo quyết định của quản lý; "
            "có thể kết hợp khuyến mãi và giảm nhập kỳ sau."
        )
    if processed and r.business_status in {"Nguy cấp", "Cần nhập"}:
        return f"Thực hiện nhập bổ sung {final_qty} sản phẩm theo quyết định của quản lý."
    if r.internal_status == "Đã hủy":
        return "Đề xuất đã được quản lý hủy, chưa thực hiện trong kỳ này."
    return r.action_strategy


def recommendation_dict(r: Recommendation) -> dict:
    p = r.product
    final_qty = r.final_quantity if r.final_quantity is not None else r.proposed_quantity
    return {
        "recommendation_id": r.recommendation_id,
        "product_id": r.product_id,
        "product_name": p.product_name,
        "category": p.category,
        "supplier_name": p.supplier_name,
        "unit": p.unit,
        "branch_name": p.branch_name,
        "purchase_price": p.purchase_price,
        "unit_price": p.unit_price,
        "stock_on_hand": stock_on_hand(p),
        "reserved_quantity": reserved_quantity(p),
        "inbound_quantity": inbound_quantity(p),
        "inventory_position": inventory_position(p),
        "forecast_7_days": p.forecast_7_days,
        "reorder_point": p.reorder_point,
        "business_status": r.business_status,
        "recommendation_type": r.recommendation_type,
        "trigger_reason": r.trigger_reason,
        "action_strategy": r.action_strategy,
        "effective_action_strategy": effective_action_strategy(r),
        "proposed_quantity": r.proposed_quantity,
        "transfer_quantity": r.transfer_quantity,
        "final_quantity": final_qty,
        "internal_status": r.internal_status,
        "telegram_status": r.telegram_status,
        "processed_by": r.processed_by,
        "internal_reason": r.internal_reason,
        "forecast_revenue_7_days": p.forecast_7_days * p.unit_price,
        "forecast_gross_profit_7_days": p.forecast_7_days * (p.unit_price - p.purchase_price),
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def paginate(items: list[dict], page: int = 1, page_size: int = 10) -> dict:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 10)))
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {"items": items[start:end], "page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}


def list_products(db: Session, search: str = "", status: str = "Tất cả", category: str = "Tất cả", supplier: str = "Tất cả", active: str = "Tất cả", page: int = 1, page_size: int = 10) -> dict:
    stmt = select(Product).order_by(Product.product_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.product_id.ilike(like), Product.product_name.ilike(like), Product.category.ilike(like), Product.supplier_name.ilike(like)))
    if status and status != "Tất cả":
        stmt = stmt.where(Product.business_status == status)
    if category and category != "Tất cả":
        stmt = stmt.where(Product.category == category)
    if supplier and supplier != "Tất cả":
        stmt = stmt.where(Product.supplier_name == supplier)
    if active == "Đang kinh doanh":
        stmt = stmt.where(Product.is_active == 1)
    elif active == "Ngừng kinh doanh":
        stmt = stmt.where(Product.is_active == 0)
    rows = db.scalars(stmt).all()
    items = [product_dict(p) for p in rows]
    all_products = db.scalars(select(Product)).all()
    return {**paginate(items, page, page_size), "categories": sorted({p.category for p in all_products}), "suppliers": sorted({p.supplier_name for p in all_products})}


def list_recommendations(
    db: Session,
    search: str = "",
    status: str = "Tất cả",
    internal_status: str = "Tất cả",
    page: int = 1,
    page_size: int = 8,
) -> dict:
    stmt = select(Recommendation).join(Product).where(Product.is_active == 1).order_by(Recommendation.recommendation_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Recommendation.product_id.ilike(like), Product.product_name.ilike(like), Product.category.ilike(like)))
    if status and status != "Tất cả":
        stmt = stmt.where(Recommendation.business_status == status)
    if internal_status and internal_status != "Tất cả":
        stmt = stmt.where(Recommendation.internal_status == internal_status)
    rows = db.scalars(stmt).all()
    items = [recommendation_dict(r) for r in rows]
    return paginate(items, page, page_size)


def get_product_journey(db: Session, product_id: str) -> dict | None:
    product = db.get(Product, product_id)
    if not product:
        return None
    rec = db.scalar(select(Recommendation).where(Recommendation.product_id == product_id).order_by(Recommendation.recommendation_id.desc()))
    txs = db.scalars(select(InventoryTransaction).where(InventoryTransaction.product_id == product_id).order_by(InventoryTransaction.transaction_id.desc()).limit(30)).all()
    demand_rows = db.scalars(select(DailyDemand).where(DailyDemand.product_id == product_id).order_by(DailyDemand.demand_date.desc()).limit(14)).all()
    if demand_rows:
        demand_history = [{"demand_date": d.demand_date, "net_demand": d.net_demand} for d in reversed(demand_rows)]
    else:
        demand_history = []
        for idx in range(14):
            date = (datetime.now() - timedelta(days=13 - idx)).strftime("%Y-%m-%d")
            demand_history.append({"demand_date": date, "net_demand": max(0, round(product.avg_daily_demand + ((idx % 5) - 2) * 1.5))})
    return {
        "product": product_dict(product),
        "recommendation": recommendation_dict(rec) if rec else None,
        "transactions": [transaction_dict(tx) for tx in txs],
        "demand_history": demand_history,
    }


def transaction_dict(tx: InventoryTransaction) -> dict:
    return {
        "transaction_id": tx.transaction_id,
        "product_id": tx.product_id,
        "product_name": tx.product.product_name if tx.product else tx.product_id,
        "transaction_date": tx.transaction_date,
        "voucher_type": tx.voucher_type,
        "transaction_type": tx.transaction_type,
        "movement_direction": tx.movement_direction,
        "quantity": tx.quantity,
        "unit_price": tx.unit_price,
        "total_amount": tx.total_amount,
        "stock_before": tx.stock_before,
        "stock_after": tx.stock_after,
        "recorded_by": tx.recorded_by,
        "price_note": tx.price_note,
        "note": tx.note,
    }


def recalculate_product_status(product: Product) -> str:
    pos = inventory_position(product)
    stock = stock_on_hand(product)
    if stock <= max(5, product.safety_stock // 3):
        return "Nguy cấp"
    if pos <= product.reorder_point:
        return "Cần nhập"
    if stock >= 300 and product.avg_daily_demand <= 30:
        return "Bán chậm"
    if stock >= 300:
        return "Dư tồn"
    if pos <= int(product.reorder_point * 1.25):
        return "Theo dõi"
    return "An toàn"


def update_or_create_recommendation(db: Session, product: Product) -> Recommendation:
    product.business_status = recalculate_product_status(product)
    pos = inventory_position(product)
    available = stock_on_hand(product) - reserved_quantity(product)
    target_stock = int(product.avg_daily_demand * (product.lead_time_days + 7) + product.safety_stock)
    proposed = max(0, target_stock - pos)
    transfer_qty = 0
    rec_type = "MONITOR"
    strategy = "Theo dõi định kỳ, chưa cần xử lý lớn."
    reason = f"Tồn kho {stock_on_hand(product)}, điểm đặt hàng lại {product.reorder_point}, dự báo 7 ngày {product.forecast_7_days:.1f}."
    if product.business_status == "Nguy cấp":
        rec_type = "URGENT_RESTOCK_OR_TRANSFER"
        proposed = max(proposed, int(product.reorder_point - pos + product.safety_stock))
        transfer_qty = min(max(10, proposed // 3), proposed)
        strategy = f"Ưu tiên nhập nhanh {proposed} sản phẩm hoặc điều chuyển nội bộ khoảng {transfer_qty} sản phẩm trong ngày."
    elif product.business_status == "Cần nhập":
        rec_type = "RESTOCK"
        strategy = f"Lên kế hoạch nhập bổ sung {proposed} sản phẩm theo số lượng đề xuất."
    elif product.business_status in ["Dư tồn", "Bán chậm"]:
        rec_type = "TRANSFER_OR_PROMOTION"
        proposed = 0
        transfer_qty = max(0, min(stock_on_hand(product) - 300, 80))
        strategy = f"Xem xét điều chuyển khoảng {transfer_qty} sản phẩm sang chi nhánh bán tốt, chạy khuyến mãi hoặc giảm nhập kỳ sau."
    elif product.business_status == "Theo dõi":
        rec_type = "WATCH"
        strategy = "Theo dõi thêm trong 3–7 ngày trước khi ra quyết định nhập mới."
    else:
        rec_type = "SAFE"
        strategy = "Tồn kho an toàn, tiếp tục theo dõi định kỳ."

    rec = db.scalar(select(Recommendation).where(Recommendation.product_id == product.product_id))
    if not rec:
        rec = Recommendation(product_id=product.product_id)
        db.add(rec)
    rec.business_status = product.business_status
    rec.recommendation_type = rec_type
    rec.available_stock = available
    rec.inventory_position = pos
    rec.reorder_point = product.reorder_point
    rec.target_stock = target_stock
    rec.trigger_reason = reason
    rec.action_strategy = strategy
    rec.proposed_quantity = int(proposed)
    rec.transfer_quantity = int(transfer_qty)
    rec.final_quantity = int(proposed or transfer_qty or 0)
    rec.updated_at = now_text()
    product.updated_at = now_text()
    return rec



PRODUCT_EDITABLE_FIELDS = {
    "product_name",
    "category",
    "supplier_name",
    "unit",
    "purchase_price",
    "unit_price",
    "lead_time_days",
    "safety_stock",
    "minimum_stock",
    "reorder_point",
    "branch_name",
    "is_active",
}
PRODUCT_DECISION_FIELDS = {"lead_time_days", "safety_stock", "minimum_stock", "reorder_point"}


def update_product(db: Session, product_id: str, payload: dict) -> dict:
    product = db.get(Product, product_id)
    if not product:
        raise ValueError("Không tìm thấy sản phẩm")

    values = {key: value for key, value in payload.items() if key in PRODUCT_EDITABLE_FIELDS and value is not None}
    if not values:
        return product_dict(product)

    if "product_name" in values:
        values["product_name"] = str(values["product_name"]).strip()
        if not values["product_name"]:
            raise ValueError("Tên sản phẩm không được để trống")

    old_active = int(product.is_active or 0)
    logic_changed = bool(PRODUCT_DECISION_FIELDS.intersection(values))

    for field, value in values.items():
        setattr(product, field, value)
    product.updated_at = now_text()

    rec = db.scalar(select(Recommendation).where(Recommendation.product_id == product_id))

    if int(product.is_active or 0) == 0:
        if rec:
            rec.internal_status = "Đã hủy"
            rec.final_quantity = 0
            rec.internal_reason = "Sản phẩm đã ngừng kinh doanh"
            rec.telegram_status = "Chưa gửi"
            rec.updated_at = now_text()
    elif logic_changed or old_active == 0:
        rec = update_or_create_recommendation(db, product)
        rec.internal_status = "Chờ xử lý"
        rec.processed_by = ""
        rec.internal_reason = ""
        rec.telegram_status = "Chưa gửi"
        rec.updated_at = now_text()

    db.commit()
    db.refresh(product)
    return product_dict(product)


def delete_product(db: Session, product_id: str) -> dict:
    """Xóa mềm sản phẩm để bảo toàn lịch sử giao dịch và báo cáo."""
    product = db.get(Product, product_id)
    if not product:
        raise ValueError("Không tìm thấy sản phẩm")

    if int(product.is_active or 0) == 0:
        return {
            "product_id": product_id,
            "deleted": True,
            "message": "Sản phẩm đã ở trạng thái ngừng kinh doanh.",
        }

    product.is_active = 0
    product.updated_at = now_text()
    rec = db.scalar(select(Recommendation).where(Recommendation.product_id == product_id))
    if rec:
        rec.internal_status = "Đã hủy"
        rec.final_quantity = 0
        rec.internal_reason = "Sản phẩm đã ngừng kinh doanh"
        rec.telegram_status = "Chưa gửi"
        rec.updated_at = now_text()

    db.commit()
    return {
        "product_id": product_id,
        "deleted": True,
        "message": "Đã xóa sản phẩm khỏi hoạt động kinh doanh và giữ lại lịch sử giao dịch.",
    }

def create_inventory_transaction(db: Session, payload: dict) -> dict:
    product = db.get(Product, payload["product_id"])
    if not product:
        raise ValueError("Không tìm thấy sản phẩm")
    quantity = int(payload.get("quantity") or 0)
    if quantity <= 0:
        raise ValueError("Số lượng phải lớn hơn 0")
    unit_price = float(payload.get("unit_price") or 0)
    direction = payload.get("movement_direction") or "IN"
    voucher_type = payload.get("voucher_type") or "Phiếu nhập hàng"
    inv = product.inventory or Inventory(product_id=product.product_id, stock_on_hand=product.stock_on_hand, reserved_quantity=product.reserved_quantity, confirmed_inbound_quantity=product.inbound_quantity)
    if not product.inventory:
        db.add(inv)
        product.inventory = inv
    before = inv.stock_on_hand
    if direction == "IN":
        inv.stock_on_hand += quantity
        tx_type = "RECEIPT"
    else:
        if inv.stock_on_hand < quantity:
            raise ValueError("Tồn kho không đủ để xuất/giảm")
        inv.stock_on_hand -= quantity
        if "điều chuyển" in voucher_type.lower():
            tx_type = "TRANSFER_OUT"
        elif "hủy" in voucher_type.lower() or "lỗi" in voucher_type.lower():
            tx_type = "DISPOSE"
        else:
            tx_type = "SALE_OUT"
    after = inv.stock_on_hand
    inv.updated_at = now_text()
    sync_product_inventory_cache(product)
    tx = InventoryTransaction(
        product_id=product.product_id,
        voucher_type=voucher_type,
        transaction_type=tx_type,
        movement_direction=direction,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=quantity * unit_price,
        stock_before=before,
        stock_after=after,
        recorded_by=payload.get("recorded_by") or "Nhân viên kho",
        price_note=payload.get("price_note") or "",
        note=payload.get("reason") or "",
    )
    db.add(tx)
    update_or_create_recommendation(db, product)
    db.commit()
    db.refresh(tx)
    return transaction_dict(tx)


def process_decision(db: Session, recommendation_id: int, payload: dict) -> dict:
    rec = db.get(Recommendation, recommendation_id)
    if not rec:
        raise ValueError("Không tìm thấy đề xuất")

    decision = payload.get("decision")
    requested_qty = payload.get("final_quantity")
    default_qty = rec.proposed_quantity if rec.business_status in {"Nguy cấp", "Cần nhập"} else rec.transfer_quantity
    final_qty = int(default_qty if requested_qty in (None, "") else requested_qty)
    if final_qty < 0:
        raise ValueError("Số lượng xử lý không được nhỏ hơn 0")

    if decision == "APPROVE":
        rec.internal_status = "Đã duyệt"
        rec.final_quantity = final_qty
    elif decision == "ADJUST":
        rec.internal_status = "Đã điều chỉnh"
        rec.final_quantity = final_qty
    elif decision == "REJECT":
        rec.internal_status = "Đã hủy"
        rec.final_quantity = 0
    else:
        raise ValueError("Quyết định không hợp lệ")

    rec.internal_reason = payload.get("reason") or "Đã kiểm tra tình hình thực tế"
    rec.processed_by = payload.get("processed_by") or "Quản lý kho"
    rec.updated_at = now_text()
    db.commit()
    db.refresh(rec)
    return recommendation_dict(rec)


def dashboard_summary(db: Session) -> dict:
    products = db.scalars(select(Product).where(Product.is_active == 1)).all()
    recs = db.scalars(select(Recommendation).join(Product).where(Product.is_active == 1)).all()
    status_counts = {status: 0 for status in STATUS_ORDER}
    for p in products:
        status_counts[p.business_status] = status_counts.get(p.business_status, 0) + 1
    total_purchase_value = sum(stock_on_hand(p) * p.purchase_price for p in products)
    total_sell_value = sum(stock_on_hand(p) * p.unit_price for p in products)
    need_qty = sum(r.final_quantity or r.proposed_quantity for r in recs if r.business_status in ["Nguy cấp", "Cần nhập"])
    transfer_qty = sum(r.transfer_quantity for r in recs if r.business_status in ["Dư tồn", "Bán chậm", "Nguy cấp"])
    waiting = sum(1 for r in recs if r.internal_status == "Chờ xử lý")
    sent = sum(1 for r in recs if r.telegram_status != "Chưa gửi")
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "last_updated": today,
        "total_products": len(products),
        "need_restock": status_counts.get("Nguy cấp", 0) + status_counts.get("Cần nhập", 0),
        "overstock_slow": status_counts.get("Dư tồn", 0) + status_counts.get("Bán chậm", 0),
        "waiting_internal": waiting,
        "sent_notifications": sent,
        "total_purchase_value": total_purchase_value,
        "total_sell_value": total_sell_value,
        "status_counts": status_counts,
        "quick_report": {
            "last_updated": today,
            "headline": f"Hệ thống đang theo dõi {len(products)} sản phẩm trong SQL database.",
            "risk_line": f"Cần nhập/nguy cấp: {status_counts.get('Nguy cấp', 0) + status_counts.get('Cần nhập', 0)} sản phẩm; dư tồn/bán chậm: {status_counts.get('Dư tồn', 0) + status_counts.get('Bán chậm', 0)} sản phẩm.",
            "quantity_line": f"Tổng số lượng đề xuất nhập/điều chỉnh: {need_qty}; số lượng có thể điều chuyển: {transfer_qty}.",
            "approval_line": f"Chờ xử lý nội bộ: {waiting}; đã gửi/lưu thông báo: {sent}.",
            "priority_line": "Ưu tiên xử lý nhóm Nguy cấp trước, sau đó Cần nhập và nhóm Dư tồn/Bán chậm."
        },
        "inventory_flow": flow_summary(db),
    }


def flow_summary(db: Session) -> list[dict]:
    rows = db.scalars(select(InventoryTransaction).order_by(InventoryTransaction.transaction_id.desc()).limit(100)).all()
    data: dict[str, dict] = {}
    for tx in rows:
        day = tx.transaction_date[:10]
        item = data.setdefault(day, {"date": day, "Nhập": 0, "Xuất": 0})
        if tx.movement_direction == "IN":
            item["Nhập"] += tx.quantity
        else:
            item["Xuất"] += tx.quantity
    return [data[k] for k in sorted(data.keys())][-14:]
