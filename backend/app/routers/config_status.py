from fastapi import APIRouter
from sqlalchemy.engine import make_url
from ..config import get_settings

router = APIRouter(prefix="/api/config", tags=["config"])


def database_label(database_url: str) -> str:
    driver = make_url(database_url).drivername
    if driver.startswith("mysql"):
        return "MySQL/XAMPP"
    if driver.startswith("sqlite"):
        return "SQLite local"
    if driver.startswith("mssql"):
        return "SQL Server"
    if driver.startswith("postgresql"):
        return "PostgreSQL"
    return "SQL database"


@router.get("/status")
def status():
    s = get_settings()
    return {
        "database_mode": database_label(s.database_url),
        "database_url_configured": bool(s.database_url),
        "gemini_mode": s.gemini_mode,
        "gemini_model": s.gemini_model,
        "gemini_configured": bool(s.gemini_api_key),
        "telegram_mode": s.telegram_mode,
        "admin_username": s.admin_username,
    }
