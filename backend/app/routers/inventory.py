from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.inventory_service import VOUCHER_TYPES, create_inventory_voucher, list_inventory

router = APIRouter(prefix="/api/inventory", tags=["Nhập xuất kho"])


class VoucherRequest(BaseModel):
    product_id: str = Field(min_length=1)
    voucher_type: str = Field(min_length=3)
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=3)
    recorded_by: str = "Nhân viên kho"
    movement_direction: str | None = Field(default=None, pattern="^(IN|OUT)$")
    unit_price: float | None = Field(default=None, ge=0)
    price_note: str | None = None


@router.get("")
def inventory(search: str | None = Query(default=None)) -> dict:
    items = list_inventory(search)
    return {"items": items, "total": len(items)}


@router.get("/voucher-types")
def voucher_types() -> dict:
    return {"items": list(VOUCHER_TYPES.keys())}


@router.post("/vouchers", status_code=201)
def voucher(payload: VoucherRequest) -> dict:
    try:
        return create_inventory_voucher(payload.product_id, payload.voucher_type, payload.quantity, payload.reason, payload.recorded_by, payload.movement_direction, payload.unit_price, payload.price_note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy sản phẩm {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
