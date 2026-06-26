from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import settings


def main() -> None:
    connection = sqlite3.connect(settings.database_path)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        products = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        restock = connection.execute("SELECT COUNT(*) FROM recommendations WHERE recommendation_type='RESTOCK' AND business_status IN ('Nguy cấp','Cần nhập')").fetchone()[0]
        strategy = connection.execute("SELECT COUNT(*) FROM recommendations WHERE business_status IN ('Dư tồn','Bán chậm')").fetchone()[0]
        pending = connection.execute("SELECT COUNT(*) FROM recommendations WHERE internal_status='Chờ xử lý' AND business_status<>'An toàn'").fetchone()[0]
    finally:
        connection.close()
    if version != 6 or errors or products < 25 or restock < 4 or strategy < 5:
        raise SystemExit(f"FAIL: schema={version}, fk_errors={len(errors)}, products={products}, restock={restock}, strategy={strategy}")
    print("PASS: Inventory DSS V4 Pricing đã sẵn sàng.")
    print(f"Schema: v{version} | Products: {products} | Cần nhập: {restock} | Dư tồn/bán chậm: {strategy} | Chờ xử lý: {pending}")


if __name__ == "__main__":
    main()
