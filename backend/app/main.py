from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.routers import ai, dashboard, excel_imports, inventory, notifications, recommendations, reports

app = FastAPI(
    title="Inventory DSS API",
    version="4.0.0",
    description="Hệ thống hỗ trợ quản lý tồn kho, xử lý đề xuất, cảnh báo dư tồn/bán chậm và phê duyệt nhiều cấp.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(inventory.router)
app.include_router(recommendations.router)
app.include_router(ai.router)
app.include_router(notifications.router)
app.include_router(excel_imports.router)
app.include_router(reports.router)
