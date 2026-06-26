from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from backend.app.services.recommendation_service import latest_recommendations


def money(value: float | int | None) -> str:
    return f"{int(round(value or 0)):,}".replace(",", ".")


def build_recommendation_report() -> bytes:
    rows = latest_recommendations(only_actionable=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "De_Xuat_Xu_Ly_Ton_Kho"
    ws.merge_cells("A1:Q1")
    ws["A1"] = "BÁO CÁO ĐỀ XUẤT XỬ LÝ TỒN KHO"
    ws["A1"].font = Font(bold=True, size=16, color="FFFFFF")
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="17365D")
    ws["A2"] = f"Thời gian xuất báo cáo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    headers = [
        "Mã SP", "Tên sản phẩm", "Nhóm", "Tồn kho", "Dự báo 7 ngày", "Giá nhập",
        "Giá bán", "Lãi gộp/SP", "Giá trị vốn tồn", "Giá trị bán tồn", "Doanh thu dự báo",
        "Lãi gộp dự báo", "Tình trạng", "Số lượng đề xuất", "Chiến lược", "Xử lý nội bộ", "Ghi chú xử lý",
    ]
    ws.append([])
    ws.append(headers)
    for cell in ws[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="1F4E79")
    money_cols = {
        "purchase_price", "unit_price", "gross_margin_per_unit", "inventory_value_cost",
        "inventory_value_selling", "forecast_revenue_7_days", "forecast_gross_profit_7_days",
    }
    for row in rows:
        ws.append([
            row["product_id"], row["product_name"], row["category"], row["stock_on_hand"],
            row["forecast_quantity_7_days"], money(row["purchase_price"]), money(row["unit_price"]),
            money(row["gross_margin_per_unit"]), money(row["inventory_value_cost"]), money(row["inventory_value_selling"]),
            money(row["forecast_revenue_7_days"]), money(row["forecast_gross_profit_7_days"]), row["business_status"],
            row["proposed_quantity"], row["action_strategy"], row["internal_status"], row.get("internal_reason") or "",
        ])
    widths = [12, 36, 18, 12, 16, 14, 14, 14, 18, 18, 18, 18, 16, 18, 55, 18, 28]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + idx)].width = width
    ws.freeze_panes = "A5"
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
