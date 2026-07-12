from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Hệ thống hỗ trợ cả MySQL/XAMPP và SQLite để test nhanh.
    # Mặc định phù hợp XAMPP/MySQL root không mật khẩu.
    # Test nhanh SQLite: đổi thành sqlite:///./backend/data/inventory_dss.sqlite3
    database_url: str = "mysql+pymysql://root@127.0.0.1:3306/inventory_dss?charset=utf8mb4"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    gemini_mode: str = "disabled"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 30
    telegram_mode: str = "disabled"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
