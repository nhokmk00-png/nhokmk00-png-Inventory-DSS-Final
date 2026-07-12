from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.report_service import build_recommendations_workbook

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/recommendations.xlsx")
def recommendations_report(db: Session = Depends(get_db)):
    content = build_recommendations_workbook(db)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bao_cao_xu_ly_ton_kho.xlsx"},
    )
