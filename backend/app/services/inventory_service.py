from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime

from backend.app.database import connect, transaction
from backend.app.services.recommendation_service import recalc_for_product

VOUCHER_TYPES = {
    "Phiếu nhập hàng": {"direction": "IN", "transaction_type": "RECEIPT"},
    "Phiếu xuất bán": {"direction": "OUT", "transaction_type": "SALE_OUT"},
    "Phiếu điều chỉnh kiểm kê": {"direction": "IN", "transaction_type": "ADJUSTMENT_IN"},
    "Phiếu hàng lỗi / hủy": {"direction": "OUT", "transaction_type": "DISPOSE"},
    "Phiếu điều chuyển chi nhánh": {"direction": "OUT", "transaction_type": "TRANSFER_OUT"},
}


def now_text() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _search_key(value: str) -> str:
    text = unicodedata.normalize("NFD", value.strip().lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.split())


def resolve_product_id(connection, value: str | None) -> str | None:
    if not value:
        return None
    needle = _search_key(value)
    products = connection.execute("SELECT product_id, product_name, category, supplier_name FROM products ORDER BY product_name").fetchall()
    for row in products:
        if needle in {_search_key(row["product_id"]), _search_key(row["product_name"])}:
            return row["product_id"]
    for row in products:
        if needle in _search_key(row["product_id"] + " " + row["product_name"]):
            return row["product_id"]
    for row in products:
        if needle in _search_key(row["category"] + " " + row["supplier_name"]):
            return row["product_id"]
    return None


def list_inventory(search: str | None = None) -> list[dict]:
    sql = """
        SELECT p.product_id, p.product_name, p.category, p.supplier_name, p.branch_name, p.unit,
               p.unit_price, p.purchase_price, (p.unit_price - p.purchase_price) AS gross_margin_per_unit,
               i.stock_on_hand, i.reserved_quantity, i.confirmed_inbound_quantity,
               (i.stock_on_hand - i.reserved_quantity) AS available_stock,
               (i.stock_on_hand - i.reserved_quantity + i.confirmed_inbound_quantity) AS inventory_position,
               i.updated_at,
               ROUND(i.stock_on_hand * p.unit_price, 0) AS inventory_value_selling,
               ROUND(i.stock_on_hand * p.purchase_price, 0) AS inventory_value_cost,
               r.business_status, r.recommendation_type, r.priority_rank, r.proposed_quantity, r.action_strategy, r.internal_status, r.telegram_status, r.boss_status, r.final_quantity, r.boss_final_quantity
        FROM products p
        JOIN inventory i ON i.product_id=p.product_id
        LEFT JOIN recommendations r ON r.product_id=p.product_id
        WHERE 1=1
    """
    params: list[str] = []
    if search:
        s = f"%{search.lower()}%"
        sql += " AND (LOWER(p.product_id) LIKE ? OR LOWER(p.product_name) LIKE ? OR LOWER(p.category) LIKE ? OR LOWER(p.supplier_name) LIKE ?)"
        params.extend([s, s, s, s])
    sql += " ORDER BY COALESCE(r.priority_rank, 99), p.product_name"
    with connect() as connection:
        rows = [dict(row) for row in connection.execute(sql, params).fetchall()]
    unique = {}
    for row in rows:
        unique[row["product_id"]] = row
    return list(unique.values())


def _default_unit_price(product: dict, voucher_type: str, direction: str) -> float:
    # Phiếu nhập, điều chỉnh tăng và hủy hàng dùng giá vốn/giá nhập; phiếu xuất bán dùng giá bán.
    if voucher_type == "Phiếu xuất bán":
        return float(product["unit_price"])
    return float(product["purchase_price"])


def create_inventory_voucher(
    product_id: str,
    voucher_type: str,
    quantity: int,
    reason: str,
    recorded_by: str,
    movement_direction: str | None = None,
    unit_price: float | None = None,
    price_note: str | None = None,
) -> dict:
    if quantity <= 0:
        raise ValueError("Số lượng phải lớn hơn 0.")
    if voucher_type not in VOUCHER_TYPES:
        raise ValueError("Loại phiếu không hợp lệ.")
    with transaction() as connection:
        resolved = resolve_product_id(connection, product_id)
        if not resolved:
            raise KeyError(product_id)
        inv = connection.execute("SELECT * FROM inventory WHERE product_id=?", (resolved,)).fetchone()
        product = connection.execute("SELECT * FROM products WHERE product_id=?", (resolved,)).fetchone()
        if not inv or not product:
            raise KeyError(product_id)
        direction = VOUCHER_TYPES[voucher_type]["direction"]
        tx_type = VOUCHER_TYPES[voucher_type]["transaction_type"]
        if voucher_type == "Phiếu điều chỉnh kiểm kê" and movement_direction in {"IN", "OUT"}:
            direction = movement_direction
            tx_type = "ADJUSTMENT_IN" if direction == "IN" else "ADJUSTMENT_OUT"
        actual_unit_price = float(unit_price) if unit_price not in (None, "") else _default_unit_price(dict(product), voucher_type, direction)
        if actual_unit_price < 0:
            raise ValueError("Đơn giá không được âm.")
        before = inv["stock_on_hand"]
        after = before + quantity if direction == "IN" else before - quantity
        if after < inv["reserved_quantity"]:
            raise ValueError("Tồn sau xử lý không được nhỏ hơn số lượng đang giữ cho đơn hàng.")
        connection.execute("UPDATE inventory SET stock_on_hand=?, updated_at=? WHERE product_id=?", (after, now_text(), resolved))
        transaction_id = f"TX_{uuid.uuid4().hex[:12].upper()}"
        total_amount = round(actual_unit_price * quantity, 0)
        connection.execute(
            "INSERT INTO inventory_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (transaction_id, resolved, tx_type, quantity, before, after, voucher_type, actual_unit_price, total_amount, price_note or "", reason, recorded_by, now_text()),
        )
        refreshed = recalc_for_product(connection, resolved)
    return {
        "transaction_id": transaction_id,
        "product_id": resolved,
        "product_name": product["product_name"],
        "voucher_type": voucher_type,
        "transaction_type": tx_type,
        "quantity": quantity,
        "unit_price": actual_unit_price,
        "total_amount": total_amount,
        "price_note": price_note or "",
        "stock_before": before,
        "stock_after": after,
        "recommendation_after_adjustment": refreshed,
    }


def daily_flow() -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute(
            """
            SELECT substr(transaction_date, 1, 10) AS date,
                   SUM(CASE WHEN transaction_type IN ('RECEIPT','ADJUSTMENT_IN') THEN quantity ELSE 0 END) AS inbound,
                   SUM(CASE WHEN transaction_type IN ('SALE_OUT','ADJUSTMENT_OUT','TRANSFER_OUT','DISPOSE') THEN quantity ELSE 0 END) AS outbound,
                   COUNT(*) AS transaction_count,
                   SUM(total_amount) AS total_amount
            FROM inventory_transactions
            GROUP BY substr(transaction_date, 1, 10)
            ORDER BY date
            """
        ).fetchall()]



def all_transactions() -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute(
            """
            SELECT t.*, p.product_name
            FROM inventory_transactions t JOIN products p ON p.product_id=t.product_id
            ORDER BY t.transaction_date DESC
            """
        ).fetchall()]


def day_transactions(date_text: str) -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute(
            """
            SELECT t.*, p.product_name
            FROM inventory_transactions t JOIN products p ON p.product_id=t.product_id
            WHERE substr(t.transaction_date, 1, 10)=?
            ORDER BY t.transaction_date DESC
            """,
            (date_text,),
        ).fetchall()]
