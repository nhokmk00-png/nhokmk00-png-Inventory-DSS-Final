from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal, Base, engine
from backend.app.models import DailyDemand, Forecast, Inventory, InventoryTransaction, Product
from backend.app.services.inventory_service import update_or_create_recommendation
from backend.app.services.security import ensure_admin_user

PRODUCT_NAMES = [
    ("SP001", "Áo thun nam cotton basic", "Áo thun"),
    ("SP002", "Quần jeans nữ ống rộng", "Quần jeans"),
    ("SP003", "Áo sơ mi nữ trắng công sở", "Áo sơ mi"),
    ("SP004", "Váy hoa nhí dáng xòe", "Váy"),
    ("SP005", "Áo khoác dù nam chống nắng", "Áo khoác"),
    ("SP006", "Chân váy chữ A dáng ngắn", "Chân váy"),
    ("SP007", "Quần short kaki nam", "Quần short"),
    ("SP008", "Áo thun nữ form rộng", "Áo thun"),
    ("SP009", "Áo polo nam cổ bẻ", "Áo polo"),
    ("SP010", "Đầm công sở tay lỡ", "Đầm"),
    ("SP011", "Quần tây nam slimfit", "Quần tây"),
    ("SP012", "Áo thun nam cotton basic", "Áo thun"),
    ("SP013", "Áo len nữ cổ tròn", "Áo len"),
    ("SP014", "Quần legging nữ", "Quần"),
    ("SP015", "Áo khoác bán chậm", "Áo khoác"),
    ("SP016", "Đầm maxi đi biển", "Đầm"),
    ("SP017", "Áo hoodie unisex nỉ bông", "Áo hoodie"),
    ("SP018", "Áo sơ mi nam caro", "Áo sơ mi"),
    ("SP019", "Áo khoác bomber nữ", "Áo khoác"),
    ("SP020", "Quần jogger nam", "Quần"),
    ("SP021", "Áo kiểu nữ tay phồng", "Áo kiểu"),
    ("SP022", "Áo dài cách tân nữ", "Áo dài"),
    ("SP023", "Chân váy xếp ly", "Chân váy"),
    ("SP024", "Quần baggy nữ", "Quần"),
    ("SP025", "Thắt lưng da nam", "Phụ kiện"),
]


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed():
    random.seed(20260707)
    reset_database()
    db = SessionLocal()
    try:
        ensure_admin_user(db)
        urgent = {"SP004": 3, "SP022": 14, "SP017": 15, "SP003": 22, "SP016": 38, "SP009": 45}
        over = {"SP002": 370, "SP023": 520, "SP025": 340, "SP012": 328, "SP019": 312}
        slow = {"SP001": 555, "SP005": 280, "SP015": 224}
        today = datetime.now().date()
        for idx, (pid, name, cat) in enumerate(PRODUCT_NAMES, start=1):
            if pid in urgent:
                stock = urgent[pid]
                avg = random.randint(6, 11)
            elif pid in over:
                stock = over[pid]
                avg = random.randint(32, 52)
            elif pid in slow:
                stock = slow[pid]
                avg = random.randint(3, 6)
            else:
                stock = random.randint(65, 180)
                avg = random.randint(5, 18)
            purchase = random.choice([59000, 69000, 79000, 89000, 99000, 129000, 145000])
            unit = int(purchase * random.uniform(1.35, 1.85) // 1000 * 1000)
            forecast_7 = round(avg * 7 + random.uniform(-5, 8), 1)
            product = Product(
                product_id=pid,
                product_name=name,
                category=cat,
                supplier_name=f"Nhà cung cấp {chr(64 + ((idx - 1) % 5) + 1)}",
                unit="SP",
                purchase_price=purchase,
                unit_price=unit,
                lead_time_days=random.choice([4, 5, 6, 7]),
                safety_stock=random.randint(18, 35),
                minimum_stock=random.randint(5, 14),
                reorder_point=random.randint(50, 85),
                branch_name="Cửa hàng trung tâm",
                is_active=1,
                stock_on_hand=stock,
                reserved_quantity=random.randint(0, 6),
                inbound_quantity=random.choice([0, 0, 10, 20]),
                avg_daily_demand=avg,
                forecast_7_days=forecast_7,
            )
            db.add(product)
            db.flush()
            inv = Inventory(
                product_id=pid,
                stock_on_hand=product.stock_on_hand,
                reserved_quantity=product.reserved_quantity,
                confirmed_inbound_quantity=product.inbound_quantity,
            )
            db.add(inv)
            product.inventory = inv
            forecast = Forecast(
                batch_id="BATCH_CURRENT",
                forecast_date=str(today),
                product_id=pid,
                forecast_quantity_7_days=forecast_7,
                average_daily_demand=avg,
                model_name="Moving Average",
                mae=round(random.uniform(1.0, 5.5), 2),
                wape=round(random.uniform(0.08, 0.28), 4),
            )
            db.add(forecast)
            for d in range(30):
                day = today - timedelta(days=29-d)
                demand = max(0, int(random.gauss(avg, max(1.2, avg * 0.25))))
                db.add(DailyDemand(demand_date=str(day), product_id=pid, net_demand=demand, promotion_flag=1 if d in (6, 13, 20) else 0))
            db.flush()
            rec = update_or_create_recommendation(db, product)
            rec.forecast_id = forecast.forecast_id
            for t in range(5):
                qty = random.randint(3, 20)
                direction = "IN" if t in (0, 3) else "OUT"
                tx_date = datetime.now() - timedelta(days=5-t)
                db.add(InventoryTransaction(
                    product_id=pid,
                    transaction_date=tx_date.strftime("%Y-%m-%d %H:%M:%S"),
                    voucher_type="Phiếu nhập hàng" if direction == "IN" else "Phiếu xuất bán",
                    transaction_type="RECEIPT" if direction == "IN" else "SALE_OUT",
                    movement_direction=direction,
                    quantity=qty,
                    unit_price=purchase if direction == "IN" else unit,
                    total_amount=qty * (purchase if direction == "IN" else unit),
                    stock_before=max(0, stock - qty if direction == "IN" else stock + qty),
                    stock_after=stock,
                    recorded_by="Nhân viên kho",
                    price_note="Giá thực tế theo phiếu",
                    note="Dữ liệu khởi tạo hệ thống",
                ))
        db.commit()
        print("PASS: Cơ sở dữ liệu đã khởi tạo dữ liệu.")
        print("Tài khoản quản trị: admin / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
