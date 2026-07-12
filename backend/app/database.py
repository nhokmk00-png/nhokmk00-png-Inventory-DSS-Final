from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()


def _driver(database_url: str) -> str:
    return make_url(database_url).drivername


def _is_mysql_url(database_url: str) -> bool:
    return _driver(database_url).startswith("mysql")


def _is_sqlite_url(database_url: str) -> bool:
    return _driver(database_url).startswith("sqlite")


def _ensure_mysql_database(database_url: str) -> None:
    """Tạo database MySQL nếu tài khoản có quyền tạo database."""
    url = make_url(database_url)
    if not url.database:
        raise RuntimeError("DATABASE_URL cho MySQL phải có tên database, ví dụ /inventory_dss")
    server_url = url.set(database=None)
    server_engine = create_engine(server_url, future=True, pool_pre_ping=True)
    db_name = url.database.replace("`", "")
    try:
        with server_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            conn.commit()
    finally:
        server_engine.dispose()


def _ensure_sqlite_folder(database_url: str) -> None:
    url = make_url(database_url)
    db_path = url.database
    if db_path and db_path not in (":memory:",):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


if _is_mysql_url(settings.database_url):
    try:
        _ensure_mysql_database(settings.database_url)
    except OperationalError as exc:
        raise RuntimeError(
            "Không kết nối được MySQL. Hãy kiểm tra MySQL đã chạy, user/password và DATABASE_URL trong file .env. "
            "Nếu muốn test nhanh không cần MySQL, đổi DATABASE_URL sang sqlite:///./backend/data/inventory_dss.sqlite3."
        ) from exc
elif _is_sqlite_url(settings.database_url):
    _ensure_sqlite_folder(settings.database_url)

engine = create_engine(settings.database_url, future=True, pool_pre_ping=not _is_sqlite_url(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
