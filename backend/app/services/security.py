from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import User

TOKEN_STORE: dict[str, tuple[str, datetime]] = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_admin_user(db: Session) -> None:
    settings = get_settings()
    user = db.scalar(select(User).where(User.username == settings.admin_username))
    password_hash = hash_password(settings.admin_password)
    if user:
        if user.password_hash != password_hash:
            user.password_hash = password_hash
        user.role = "admin"
    else:
        db.add(User(username=settings.admin_username, password_hash=password_hash, role="admin"))
    db.commit()


def authenticate(db: Session, username: str, password: str) -> str | None:
    ensure_admin_user(db)
    user = db.scalar(select(User).where(User.username == username))
    if not user or not hmac.compare_digest(user.password_hash, hash_password(password)):
        return None
    token = secrets.token_urlsafe(32)
    TOKEN_STORE[token] = (username, datetime.now() + timedelta(hours=12))
    return token


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    item = TOKEN_STORE.get(token)
    if not item:
        return False
    _, expires_at = item
    if expires_at < datetime.now():
        TOKEN_STORE.pop(token, None)
        return False
    return True
