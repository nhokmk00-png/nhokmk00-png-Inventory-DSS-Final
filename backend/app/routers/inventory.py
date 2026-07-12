from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.inventory_service import create_inventory_transaction

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class VoucherPayload(BaseModel):
    product_id: str
    voucher_type: str
    movement_direction: str
    quantity: int
    unit_price: float = 0
    price_note: str = ""
    reason: str = ""
    recorded_by: str = "Nhân viên kho"


@router.post("/vouchers")
def voucher(payload: VoucherPayload, db: Session = Depends(get_db)):
    try:
        return create_inventory_transaction(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
