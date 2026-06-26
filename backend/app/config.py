from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DATA_DIR = BACKEND_ROOT / "data"


def _load_env() -> None:
    env_path = BACKEND_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env()


@dataclass(frozen=True)
class Settings:
    database_engine: str = os.getenv("DATABASE_ENGINE", "sqlite").lower()
    database_path: Path = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "inventory_dss_v4.db"))).resolve()
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

    sqlserver_driver: str = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server")
    sqlserver_host: str = os.getenv("SQLSERVER_HOST", "localhost")
    sqlserver_database: str = os.getenv("SQLSERVER_DATABASE", "InventoryDSS")
    sqlserver_user: str = os.getenv("SQLSERVER_USER", "")
    sqlserver_password: str = os.getenv("SQLSERVER_PASSWORD", "")
    sqlserver_trust_cert: str = os.getenv("SQLSERVER_TRUST_CERT", "yes")

    telegram_mode: str = os.getenv("TELEGRAM_MODE", "disabled").lower()  # disabled | mock | live
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_timeout_seconds: float = float(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "10"))

    gemini_mode: str = os.getenv("GEMINI_MODE", "fallback").lower()  # fallback | mock | live
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_timeout_seconds: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))

    def ensure_dirs(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "templates").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
