from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import create_all, SessionLocal
from .routers import ai, auth, config_status, dashboard, excel_imports, inventory, notifications, products, recommendations, reports
from .services.security import ensure_admin_user

settings = get_settings()
app = FastAPI(title="Inventory DSS SQL Clean", version="7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    create_all()
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(recommendations.router)
app.include_router(inventory.router)
app.include_router(excel_imports.router)
app.include_router(notifications.router)
app.include_router(ai.router)
app.include_router(reports.router)
app.include_router(config_status.router)

@app.get("/api/health")
def health():
    return {"status": "ok", "database": settings.database_url.split(":", 1)[0]}
