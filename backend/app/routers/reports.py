from __future__ import annotations

import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.services.report_service import build_recommendation_report

router = APIRouter(prefix="/api/reports", tags=["Báo cáo"])


@router.get("/recommendations.xlsx")
def recommendations_report() -> StreamingResponse:
    content = build_recommendation_report()
    return StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=bao_cao_de_xuat_xu_ly_ton_kho.xlsx"})
