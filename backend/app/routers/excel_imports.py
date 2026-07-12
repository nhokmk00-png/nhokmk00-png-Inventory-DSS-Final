from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ExcelImport
from ..services.excel_service import import_dict, make_template, upload_workbook

router = APIRouter(prefix="/api/excel", tags=["excel"])


@router.get("/template")
def template():
    output = make_template()
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=inventory_import_template.xlsx"},
    )


@router.get("/imports")
def imports(search: str = "", page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    stmt = select(ExcelImport).order_by(ExcelImport.import_id.desc())
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(ExcelImport.file_name.ilike(like), ExcelImport.uploaded_by.ilike(like), ExcelImport.status.ilike(like)))
    rows = db.scalars(stmt).all()
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    total = len(rows)
    start = (page - 1) * page_size
    return {"items": [import_dict(x) for x in rows[start:start + page_size]], "page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}


@router.get("/imports/{import_id}")
def import_detail(import_id: int, db: Session = Depends(get_db)):
    item = db.get(ExcelImport, import_id)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy file nhập")
    return import_dict(item, include_rows=True)


@router.post("/upload")
async def upload(excel_file: UploadFile = File(...), uploaded_by: str = Form("Nhân viên kho"), db: Session = Depends(get_db)):
    if not excel_file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .xlsx")
    content = await excel_file.read()
    return upload_workbook(db, content, excel_file.filename, uploaded_by)
