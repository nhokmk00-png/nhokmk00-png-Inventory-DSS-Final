from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.security import authenticate

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    token = authenticate(db, payload.username, payload.password)
    if not token:
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")
    return {"access_token": token, "token_type": "bearer", "username": payload.username, "role": "admin"}
