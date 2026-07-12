# Inventory DSS

Inventory DSS là hệ thống hỗ trợ quản lý tồn kho bán lẻ theo hướng HTTTQL/DSS. Hệ thống thu thập dữ liệu sản phẩm, tồn kho, giao dịch nhập/xuất, nhu cầu bán, kết quả dự báo và đề xuất xử lý để hỗ trợ quản lý ra quyết định.

## Chức năng chính

- Đăng nhập quản trị: `admin / admin123`.
- Dashboard quản lý: KPI, trạng thái tồn kho, báo cáo nhanh, nhóm sản phẩm cần xử lý.
- Biểu đồ nhập/xuất hàng theo ngày.
- KPI giá trị vốn tồn kho và giá trị bán tồn kho.
- Xử lý đề xuất: duyệt, điều chỉnh, hủy, gửi thông báo.
- Nhập hàng / xuất hàng / điều chỉnh / hàng lỗi-hủy / điều chuyển chi nhánh.
- Danh sách sản phẩm có tìm kiếm, lọc, phân trang, sửa thông tin và xóa mềm để giữ lịch sử giao dịch.
- Chi tiết sản phẩm có lịch sử nhập/xuất và nhu cầu gần đây.
- Nhập file Excel theo mẫu, kiểm tra dòng hợp lệ/lỗi và lưu lịch sử nhập file.
- Hỏi đáp Gemini bằng dữ liệu tồn kho thực tế; tự động dùng phản hồi dự phòng khi Gemini chưa được cấu hình hoặc gặp lỗi.
- Gửi Telegram và xuất báo cáo Excel.
- Hỗ trợ MySQL/XAMPP và SQLite để test nhanh.

## Cấu trúc dữ liệu chính

Thiết kế dữ liệu bám theo mô hình trong tài liệu: `products`, `inventory`, `inventory_transactions`, `daily_demand`, `forecasts`, `recommendations`, `ai_insights`, `ai_messages`, `alerts`, `excel_imports`, `excel_import_rows`, `users`.

`products` là bảng trung tâm. Các bảng tồn kho, giao dịch, nhu cầu, dự báo và đề xuất đều gắn với sản phẩm để phục vụ phân tích, báo cáo và hỗ trợ quyết định.

## File hướng dẫn chạy

Xem chi tiết tại:

```text
HUONG_DAN_CHAY_PROJECT.md
```


## Gửi Telegram
Để gửi Telegram thật, đặt trong `backend/.env`:

```env
TELEGRAM_MODE=live
TELEGRAM_BOT_TOKEN=token_bot_cua_ban
TELEGRAM_CHAT_ID=chat_id_cua_ban
```

Nếu hệ thống trả `SAVED`, nghĩa là thông báo chỉ được lưu nội bộ vì Telegram chưa bật hoặc thiếu token/chat id. Nếu trả `SENT`, tin đã gửi qua Telegram. Nếu trả `FAILED`, cần kiểm tra token/chat id hoặc kết nối mạng.


## Bật hỏi đáp Gemini thật

Mở `backend/.env` và cấu hình:

```env
GEMINI_MODE=live
GEMINI_API_KEY=api_key_cua_ban
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT_SECONDS=30
```

Gemini chỉ diễn giải dữ liệu do Python và MySQL cung cấp. Khi Gemini lỗi hoặc chưa được bật, hệ thống giữ nguyên luồng cũ và trả phản hồi dự phòng từ dữ liệu SQL.
