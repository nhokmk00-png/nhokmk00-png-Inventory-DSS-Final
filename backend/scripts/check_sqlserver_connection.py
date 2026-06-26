from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import settings


def main() -> None:
    try:
        import pyodbc
    except ImportError as exc:
        raise SystemExit("Chưa cài pyodbc. Chạy: python -m pip install -r backend/requirements.txt") from exc
    auth = f"UID={settings.sqlserver_user};PWD={settings.sqlserver_password};" if settings.sqlserver_user else "Trusted_Connection=yes;"
    conn_str = f"DRIVER={{{settings.sqlserver_driver}}};SERVER={settings.sqlserver_host};DATABASE={settings.sqlserver_database};{auth}TrustServerCertificate={settings.sqlserver_trust_cert};"
    with pyodbc.connect(conn_str, timeout=5) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]
    print(f"PASS: Kết nối SQL Server thành công, SELECT 1 = {result}")


if __name__ == "__main__":
    main()
