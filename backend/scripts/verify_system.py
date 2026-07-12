from __future__ import annotations

import sys
from pathlib import Path
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal, create_all
from backend.app.models import Product, Recommendation, User
from backend.app.services.security import ensure_admin_user


def main():
    create_all()
    db = SessionLocal()
    try:
        ensure_admin_user(db)
        products = len(db.scalars(select(Product)).all())
        recs = len(db.scalars(select(Recommendation)).all())
        users = len(db.scalars(select(User)).all())
        if users < 1:
            raise SystemExit("FAIL: thiếu tài khoản admin")
        print(f"PASS: Inventory DSS SQL sẵn sàng. Products: {products} | Recommendations: {recs} | Admin users: {users}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
