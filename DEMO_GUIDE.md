# Demo Guide – Inventory DSS

## 1. Trang chủ

Mở Dashboard và giới thiệu hệ thống hỗ trợ quản lý tồn kho theo hai hướng:

- thiếu hàng cần nhập;
- dư tồn hoặc bán chậm cần xử lý chiến lược.

Chỉ vào các KPI:

```text
Sản phẩm cần nhập
Dư tồn / bán chậm
Chờ xử lý nội bộ
Sẵn sàng gửi thông báo
```

## 2. Hỏi Gemini

Thử các câu hỏi khác nhau để thấy Gemini không còn trả một nội dung cố định:

```text
Sản phẩm nào đang giữ vốn nhiều?
Sản phẩm nào nên ưu tiên nhập để tăng lợi nhuận?
SP001 và SP004 khác nhau như thế nào?
Nếu khách hàng lớn muốn giá ưu đãi thì sản phẩm nào phù hợp?
```

## 3. Lập phiếu xuất bán có giá ưu đãi

Vào tab **Nhập hàng / Xuất hàng**.

Ví dụ:

```text
Loại phiếu: Phiếu xuất bán
Sản phẩm: SP001 - Áo thun nam cotton basic
Số lượng: 50
Đơn giá thực tế: 115000
Ghi chú về giá: Giá ưu đãi khách hàng lớn
Lý do: Xuất bán cho khách hàng sỉ
```

Sau khi lưu, hệ thống cập nhật:

- tồn kho;
- đơn giá giao dịch;
- thành tiền;
- lịch sử giao dịch;
- báo cáo và đề xuất liên quan.

## 4. Lập phiếu nhập hàng có giá nhập mới

Ví dụ:

```text
Loại phiếu: Phiếu nhập hàng
Sản phẩm: SP003 - Áo sơ mi nữ trắng công sở
Số lượng: 20
Đơn giá thực tế: 151000
Ghi chú về giá: Giá nhập mới từ nhà cung cấp
```

Điểm cần nói: giá nhập tại mỗi thời điểm có thể thay đổi nên hệ thống lưu đơn giá theo từng giao dịch, không chỉ lấy giá cố định trong danh mục.

## 5. Nhập file Excel

Vào tab **Nhập file Excel**, tải mẫu hoặc dùng file:

```text
import_samples/Phieu_Nhap_Xuat_Mau.xlsx
```

File đã có thêm cột:

```text
Đơn giá thực tế
```

Upload file để kiểm tra lịch sử nhập file và các dòng hợp lệ.

## 6. Gửi báo cáo tổng hợp Telegram

Ở Trang chủ bấm **Gửi báo cáo tổng hợp**.

Hệ thống gửi nội dung ngắn và đính kèm file báo cáo Excel nếu đã cấu hình Telegram. Nếu chưa cấu hình, hệ thống vẫn lưu lịch sử thông báo.

## 7. Tải báo cáo Excel

Bấm **Tải báo cáo xử lý tồn kho**.

Kiểm tra trong file Excel:

- giá nhập;
- giá bán;
- lãi gộp/SP;
- giá trị vốn tồn;
- doanh thu dự báo;
- lãi gộp dự báo.

Các cột tiền hiển thị dạng:

```text
xxx.xxx.xxx
```

## 8. Kết luận demo

Hệ thống không chỉ báo thiếu hàng mà còn hỗ trợ quản lý xem vốn tồn, giá giao dịch, lãi gộp, tồn kho bán chậm và báo cáo tổng hợp cho cấp trên.
