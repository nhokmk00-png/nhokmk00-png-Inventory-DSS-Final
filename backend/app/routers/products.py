from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.inventory_service import (
    delete_product,
    get_product_journey,
    list_products,
    update_product,
)

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductUpdatePayload(BaseModel):
    product_name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    supplier_name: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=30)
    purchase_price: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    safety_stock: int | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)
    reorder_point: int | None = Field(default=None, ge=0)
    branch_name: str | None = Field(default=None, max_length=255)
    is_active: int | None = Field(default=None, ge=0, le=1)


@router.get("")
def products(
    search: str = "",
    status: str = "Tất cả",
    category: str = "Tất cả",
    supplier: str = "Tất cả",
    active: str = "Tất cả",
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    return list_products(
        db,
        search=search,
        status=status,
        category=category,
        supplier=supplier,
        active=active,
        page=page,
        page_size=page_size,
    )


@router.get("/{product_id}")
def product_detail(product_id: str, db: Session = Depends(get_db)):
    data = get_product_journey(db, product_id)
    if not data:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return data


@router.put("/{product_id}")
def product_update(product_id: str, payload: ProductUpdatePayload, db: Session = Depends(get_db)):
    try:
        return update_product(db, product_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{product_id}")
def product_delete(product_id: str, db: Session = Depends(get_db)):
    try:
        return delete_product(db, product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
