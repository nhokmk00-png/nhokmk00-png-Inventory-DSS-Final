from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.services.excel_import_service import TEMPLATE_PATH, import_history, process_upload

router = APIRouter(prefix="/api/imports", tags=["Nhập file Excel"])


@router.get("")
def list_imports() -> dict:
    items = import_history()
    return {"items": items, "total": len(items)}


@router.get("/template")
def template() -> FileResponse:
    return FileResponse(TEMPLATE_PATH, filename="Mau_Nhap_Xuat_Kho.xlsx")


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...), uploaded_by: str = Form("Nhân viên kho")) -> dict:
    try:
        return await process_upload(file, uploaded_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
