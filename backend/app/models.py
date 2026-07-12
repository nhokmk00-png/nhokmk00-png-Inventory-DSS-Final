from __future__ import annotations

from datetime import date, datetime, time
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_text() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class DateTimeText(TypeDecorator):
    """Lưu DATETIME trong MySQL nhưng giữ chuỗi ở tầng ứng dụng.

    Các service hiện tại đang gán và đọc thời gian theo định dạng
    ``YYYY-MM-DD HH:MM:SS``. TypeDecorator này chuyển đổi ở ranh giới ORM,
    nhờ đó không phải thay đổi luồng API, Excel, Telegram hoặc giao diện.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return None
            normalized = text_value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
                return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
            except ValueError:
                for fmt in ("%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        return datetime.strptime(text_value, fmt)
                    except ValueError:
                        continue
        raise ValueError(f"Giá trị DATETIME không hợp lệ: {value!r}")

    def process_result_value(self, value, dialect):
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return value.strftime("%Y-%m-%d %H:%M:%S")


class DateText(TypeDecorator):
    """Lưu DATE trong MySQL nhưng giữ chuỗi ``YYYY-MM-DD`` ở ứng dụng."""

    impl = Date
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return None
            # OpenPyXL có thể trả ngày dưới dạng "YYYY-MM-DD 00:00:00".
            normalized = text_value[:10] if len(text_value) >= 10 and text_value[4:5] == "-" else text_value
            try:
                return date.fromisoformat(normalized)
            except ValueError:
                for fmt in ("%Y/%m/%d", "%d/%m/%Y"):
                    try:
                        return datetime.strptime(text_value, fmt).date()
                    except ValueError:
                        continue
        raise ValueError(f"Giá trị DATE không hợp lệ: {value!r}")

    def process_result_value(self, value, dialect):
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return value.isoformat()


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), default="Khác", index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), default="Nhà cung cấp", index=True)
    unit: Mapped[str] = mapped_column(String(30), default="SP")
    purchase_price: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    safety_stock: Mapped[int] = mapped_column(Integer, default=20)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=10)
    reorder_point: Mapped[int] = mapped_column(Integer, default=50)
    branch_name: Mapped[str] = mapped_column(String(255), default="Cửa hàng trung tâm")
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)

    # Cột cache để giữ tương thích API cũ; bảng Inventory là nơi phản ánh tồn kho hiện tại.
    stock_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    inbound_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_daily_demand: Mapped[float] = mapped_column(Float, default=0)
    forecast_7_days: Mapped[float] = mapped_column(Float, default=0)
    business_status: Mapped[str] = mapped_column(String(50), default="An toàn", index=True)
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)
    updated_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)

    inventory: Mapped["Inventory"] = relationship(back_populates="product", uselist=False, cascade="all, delete-orphan")
    transactions: Mapped[list["InventoryTransaction"]] = relationship(back_populates="product")
    daily_demands: Mapped[list["DailyDemand"]] = relationship(back_populates="product")
    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="product")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="product")
    ai_messages: Mapped[list["AiLog"]] = relationship(back_populates="product")


class Inventory(Base):
    __tablename__ = "inventory"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    stock_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_inbound_quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)

    product: Mapped[Product] = relationship(back_populates="inventory")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    transaction_date: Mapped[str] = mapped_column(DateTimeText(), default=now_text, index=True)
    voucher_type: Mapped[str] = mapped_column(String(100), default="Phiếu nhập hàng")
    transaction_type: Mapped[str] = mapped_column(String(50), default="RECEIPT")
    movement_direction: Mapped[str] = mapped_column(String(10), default="IN")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), default=0)
    stock_before: Mapped[int] = mapped_column(Integer, default=0)
    stock_after: Mapped[int] = mapped_column(Integer, default=0)
    recorded_by: Mapped[str] = mapped_column(String(120), default="Nhân viên kho")
    price_note: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")

    product: Mapped[Product] = relationship(back_populates="transactions")


class DailyDemand(Base):
    __tablename__ = "daily_demand"
    __table_args__ = (UniqueConstraint("demand_date", "product_id", name="uq_daily_demand_date_product"),)

    demand_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    demand_date: Mapped[str] = mapped_column(DateText(), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    net_demand: Mapped[int] = mapped_column(Integer, default=0)
    promotion_flag: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="daily_demands")


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (UniqueConstraint("batch_id", "product_id", name="uq_forecast_batch_product"),)

    forecast_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), default="BATCH_CURRENT")
    forecast_date: Mapped[str] = mapped_column(DateText(), default=today_text)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    forecast_quantity_7_days: Mapped[float] = mapped_column(Float, default=0)
    average_daily_demand: Mapped[float] = mapped_column(Float, default=0)
    model_name: Mapped[str] = mapped_column(String(100), default="Moving Average")
    mae: Mapped[float] = mapped_column(Float, nullable=True)
    wape: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)

    product: Mapped[Product] = relationship(back_populates="forecasts")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="forecast")


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[int | None] = mapped_column(ForeignKey("forecasts.forecast_id"), nullable=True, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    business_status: Mapped[str] = mapped_column(String(50), index=True)
    recommendation_type: Mapped[str] = mapped_column(String(50), default="MONITOR")
    priority_rank: Mapped[int] = mapped_column(Integer, default=0)
    available_stock: Mapped[float] = mapped_column(Float, default=0)
    inventory_position: Mapped[float] = mapped_column(Float, default=0)
    reorder_point: Mapped[float] = mapped_column(Float, default=0)
    target_stock: Mapped[float] = mapped_column(Float, default=0)
    trigger_reason: Mapped[str] = mapped_column(Text, default="")
    action_strategy: Mapped[str] = mapped_column(Text, default="")
    proposed_quantity: Mapped[int] = mapped_column(Integer, default=0)
    transfer_quantity: Mapped[int] = mapped_column(Integer, default=0)
    final_quantity: Mapped[int] = mapped_column(Integer, default=0)
    internal_status: Mapped[str] = mapped_column(String(50), default="Chờ xử lý", index=True)
    telegram_status: Mapped[str] = mapped_column(String(50), default="Chưa gửi", index=True)
    processed_by: Mapped[str] = mapped_column(String(120), default="")
    internal_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)
    updated_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)

    product: Mapped[Product] = relationship(back_populates="recommendations")
    forecast: Mapped[Forecast | None] = relationship(back_populates="recommendations")
    ai_insights: Mapped[list["AiInsight"]] = relationship(back_populates="recommendation", cascade="all, delete-orphan")


class AiInsight(Base):
    __tablename__ = "ai_insights"

    insight_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.recommendation_id"), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    suggested_action: Mapped[str] = mapped_column(Text, default="")
    management_note: Mapped[str] = mapped_column(Text, default="")
    generation_status: Mapped[str] = mapped_column(String(30), default="FALLBACK")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)

    recommendation: Mapped[Recommendation] = relationship(back_populates="ai_insights")


class AiLog(Base):
    __tablename__ = "ai_messages"

    ai_log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.product_id"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer_json: Mapped[str] = mapped_column(Text, default="")
    generation_status: Mapped[str] = mapped_column(String(30), default="FALLBACK")
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)

    product: Mapped[Product | None] = relationship(back_populates="ai_messages")


class ExcelImport(Base):
    __tablename__ = "excel_imports"

    import_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_date: Mapped[str] = mapped_column(DateTimeText(), default=now_text, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(120), default="Nhân viên kho")
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="Đã nhập")
    note: Mapped[str] = mapped_column(Text, default="")

    rows: Mapped[list["ExcelImportRow"]] = relationship(back_populates="import_file", cascade="all, delete-orphan")


class ExcelImportRow(Base):
    __tablename__ = "excel_import_rows"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("excel_imports.import_id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer, default=0)
    document_date: Mapped[str | None] = mapped_column(DateText(), nullable=True, default=None)
    voucher_type: Mapped[str] = mapped_column(String(100), default="")
    product_id: Mapped[str] = mapped_column(String(20), default="")
    product_name: Mapped[str] = mapped_column(String(255), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False), default=0)
    uploaded_by: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    row_status: Mapped[str] = mapped_column(String(50), default="Hợp lệ")
    error_message: Mapped[str] = mapped_column(Text, default="")

    import_file: Mapped[ExcelImport] = relationship(back_populates="rows")


class Notification(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(20), default="", index=True)
    recommendation_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    notification_type: Mapped[str] = mapped_column(String(50), default="DETAIL")
    product_name_snapshot: Mapped[str] = mapped_column(String(255), default="")
    business_status_snapshot: Mapped[str] = mapped_column(String(50), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    send_status: Mapped[str] = mapped_column(String(50), default="SAVED")
    sent_at: Mapped[str | None] = mapped_column(DateTimeText(), nullable=True, default=None)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="admin")
    created_at: Mapped[str] = mapped_column(DateTimeText(), default=now_text)
