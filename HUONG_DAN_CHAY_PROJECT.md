# Hướng dẫn chạy Inventory DSS

## 1. Chuẩn bị

Cần cài:

- Python 3.11+ hoặc 3.12+
- Node.js 20+
- MySQL trong XAMPP nếu chạy bằng MySQL

Tài khoản đăng nhập hệ thống:

```text
admin
admin123
```

## 2. Chạy bằng MySQL/XAMPP

Mở XAMPP và bật MySQL.

Mở file:

```text
backend/.env
```

Giữ cấu hình mặc định nếu MySQL XAMPP dùng user `root` không mật khẩu:

```env
DATABASE_URL=mysql+pymysql://root@127.0.0.1:3306/inventory_dss?charset=utf8mb4
```

Nếu root có mật khẩu, sửa thành:

```env
DATABASE_URL=mysql+pymysql://root:MAT_KHAU_CUA_BAN@127.0.0.1:3306/inventory_dss?charset=utf8mb4
```

Chạy backend:

```bat
cd C:\xampp\htdocs\Inventory_DSS_SQL_Clean
py -m venv .venv
.venv\Scripts\activate
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend\requirements.txt
python backend\scripts\init_sql_data.py
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3. Test nhanh bằng SQLite

Không cần XAMPP. Mở file `backend/.env`, đổi `DATABASE_URL` thành:

```env
DATABASE_URL=sqlite:///./backend/data/inventory_dss.sqlite3
```

Sau đó chạy:

```bat
py -m venv .venv
.venv\Scripts\activate
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend\requirements.txt
python backend\scripts\init_sql_data.py
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## 4. Chạy frontend

Mở terminal khác:

```bat
cd C:\xampp\htdocs\Inventory_DSS_SQL_Clean\frontend
npm config set registry https://registry.npmjs.org/
npm install
npm run dev
```

Mở trình duyệt:

```text
http://127.0.0.1:5173
```

## 5. Nhập file Excel mẫu

Các file mẫu nằm trong thư mục:

```text
import_samples/
```

Gồm:

```text
01_mau_phieu_kho_hop_le.xlsx
02_nhap_bo_sung_can_nhap.xlsx
03_dieu_chuyen_xuat_huy.xlsx
04_file_co_loi_de_test.xlsx
```

Cách nhập:

1. Vào menu `Nhập file Excel`.
2. Chọn người nhập.
3. Chọn một file `.xlsx` trong thư mục `import_samples`.
4. Bấm `Upload và xử lý`.
5. Bấm vào file trong lịch sử để xem từng dòng hợp lệ/lỗi.

## 6. Kiểm tra nhanh hệ thống

Sau khi khởi tạo dữ liệu, có thể chạy:

```bat
python backend\scripts\verify_system.py
```

Kết quả đúng sẽ báo hệ thống có sản phẩm, tồn kho, đề xuất và tài khoản quản trị.

## 7. Lưu ý cấu hình Gemini và Telegram

Mặc định hai tích hợp đang tắt để hệ thống chạy ổn định:

```env
GEMINI_MODE=disabled
TELEGRAM_MODE=disabled
```

Khi có API key/token thật, điền vào `backend/.env` rồi đổi chế độ tương ứng sang `live`. Không đưa API key hoặc Telegram token lên GitHub.


## Gửi Telegram
Để gửi Telegram thật, đặt trong `backend/.env`:

```env
TELEGRAM_MODE=live
TELEGRAM_BOT_TOKEN=token_bot_cua_ban
TELEGRAM_CHAT_ID=chat_id_cua_ban
```

Nếu hệ thống trả `SAVED`, nghĩa là thông báo chỉ được lưu nội bộ vì Telegram chưa bật hoặc thiếu token/chat id. Nếu trả `SENT`, tin đã gửi qua Telegram. Nếu trả `FAILED`, cần kiểm tra token/chat id hoặc kết nối mạng.

## Gửi báo cáo Telegram kèm Excel

Khi bấm **Gửi báo cáo tổng hợp**, hệ thống gửi theo thứ tự:

1. Tin nhắn tóm tắt tình trạng tồn kho.
2. File `bao_cao_xu_ly_ton_kho.xlsx` đính kèm ngay sau tin nhắn.

Cấu hình trong `backend/.env`:

```env
TELEGRAM_MODE=live
TELEGRAM_BOT_TOKEN=BOT_TOKEN_CUA_BAN
TELEGRAM_CHAT_ID=CHAT_ID_CUA_BAN
```

Sau khi đổi `.env`, phải dừng và chạy lại backend. Người nhận cũng cần mở bot và bấm **Start** ít nhất một lần.

- `SENT`: đã gửi cả tin nhắn và file Excel.
- `PARTIAL`: đã gửi tin nhắn nhưng file Excel chưa gửi được.
- `SAVED`: Telegram chưa bật hoặc thiếu cấu hình; thông báo chỉ được lưu trong hệ thống.
- `FAILED`: Telegram từ chối hoặc có lỗi kết nối.


## 8. Bật hỏi đáp Gemini

Mở `backend/.env` và đặt:

```env
GEMINI_MODE=live
GEMINI_API_KEY=API_KEY_GEMINI_CUA_BAN
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT_SECONDS=30
```

Sau khi thay đổi `.env`, dừng backend và chạy lại. Nếu Gemini gửi phản hồi thành công, giao diện hiển thị nguồn `Gemini`. Nếu API key sai, hết hạn mức hoặc mất kết nối, hệ thống tự dùng phản hồi dự phòng từ SQL mà không ảnh hưởng các chức năng khác.

## 9. Sửa và xóa sản phẩm

1. Vào `Danh sách sản phẩm`.
2. Chọn sản phẩm cần thao tác.
3. Bấm `Sửa` để cập nhật thông tin sản phẩm.
4. Bấm `Xóa` để chuyển sản phẩm sang trạng thái ngừng kinh doanh.

Chức năng xóa sử dụng xóa mềm để giữ nguyên lịch sử nhập/xuất, đề xuất và thông báo. Có thể chọn bộ lọc `Ngừng kinh doanh` để xem lại sản phẩm đã xóa hoặc dùng `Sửa` để kích hoạt lại.
