# Hướng dẫn xác minh dữ liệu đã seed trong Odoo 17

## Thông tin truy cập

| Thông tin | Giá trị                     |
| --------- | --------------------------- |
| URL       | `http://educare-connect.me` |
| Database  | `erpsight`                  |
| Tài khoản | `admin` / `admin`           |

---

## Chạy lại dữ liệu demo

```bash
cd /home/haotranhcmus/MashineLearning/ERPSight/erpsight/backend/script
python3 reset_demo.py
```

Script này tự động:

1. Xóa toàn bộ dữ liệu cũ (FK-safe order)
2. Chạy lại 4 scripts seed theo thứ tự:
   - `seed_odoo.py` – users, sản phẩm, đối tác
   - `seed_purchase_orders.py` – 8 Purchase Orders
   - `seed_sale_orders.py` – 410 Sale Orders
   - `set_inventory_and_tickets.py` – tồn kho 19 SKU + 8 helpdesk tickets + activities

---

## 1. Xác minh Users (4 nhân viên)

**Đường dẫn:** Settings → Users & Companies → Users

| Login          | Họ tên           | Vai trò          |
| -------------- | ---------------- | ---------------- |
| `khoa.sale`    | Nguyễn Minh Khoa | Salesperson      |
| `hang.sale`    | Trần Thị Hằng    | Salesperson      |
| `duc.purchase` | Lê Văn Đức       | Purchase Manager |
| `lan.support`  | Phạm Thị Lan     | Support Agent    |

**Cách kiểm tra:**

1. Vào **Settings** → menu trái chọn **Users & Companies** → **Users**
2. Tìm lần lượt các login ở trên ở ô search góc phải

---

## 2. Xác minh Products (19 SKU)

**Đường dẫn:** Inventory → Products → Products

**Cách kiểm tra:**

1. Vào **Inventory** → menu trái chọn **Products** → **Products**
2. Xóa filter mặc định "Can be Sold" nếu có
3. Search theo `default_code` hoặc tên

| Nhóm     | Số lượng | Ví dụ SKU                                                      |
| -------- | -------- | -------------------------------------------------------------- |
| RAM      | 4        | RAM-DDR5-16-KS, RAM-DDR5-32-KS, RAM-DDR5-16-SS, RAM-DDR5-32-CO |
| SSD      | 4        | SSD-1TB-SS-870, SSD-2TB-SS-870, SSD-512-WD-BL, SSD-1TB-WD-BL   |
| HDD      | 3        | HDD-2TB-SG-BC, HDD-4TB-SG-BC, HDD-2TB-WD-BL                    |
| Monitor  | 3        | MON-27-LG-GP850, MON-24-DL-P2422, MON-27-SS-LS27               |
| CPU      | 3        | CPU-I5-14400, CPU-I7-14700K, CPU-I9-14900K                     |
| Phụ kiện | 2        | ACC-THERMAL-MX4, ACC-FAN-NF-A12                                |

**Kiểm tra tồn kho:**

- Click vào sản phẩm → tab **General Information** → xem **On Hand**
- Hoặc click nút **"X On Hand"** trên card sản phẩm

---

## 3. Xác minh Partners (17 đối tác)

**Đường dẫn:** Contacts → (search)

| Loại         | Tên đối tác                                                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| Khách hàng   | Thế Giới PC, IT Solutions ABC, Hoàng Long Computer, Minh Khoa Tech, Hùng Laptop Cần Thơ, Công Nghệ Phúc Anh, ABC Computer Bình Dương |
| Cá nhân      | Nguyễn Văn Bình, Trần Thị Mai, Lê Minh Tuấn, Phạm Văn Long, Minh Phát Technology                                                     |
| Nhà cung cấp | Samsung Electronics Vietnam, Western Digital Vietnam, Seagate Technology Vietnam, Intel Vietnam, Phụ Kiện Máy Tính Thành Đạt         |

---

## 4. Xác minh Purchase Orders (8 POs)

**Đường dẫn:** Purchase → Orders → Purchase Orders

**Cách kiểm tra:**

1. Vào **Purchase** → **Orders** → **Purchase Orders**
2. Tổng số PO = **8**, trạng thái `Purchase Order` (confirmed)
3. Lọc theo ngày: tháng 1–4 năm 2026

**Danh sách PO:**

| PO   | Ngày       | Nhà cung cấp                        | Ghi chú                                 |
| ---- | ---------- | ----------------------------------- | --------------------------------------- |
| PO 1 | 15/01/2026 | Samsung / Western Digital / Seagate | Nhập hàng tháng 1                       |
| PO 2 | 28/01/2026 | Intel / Phụ Kiện Thành Đạt          | Nhập CPU                                |
| PO 3 | 05/02/2026 | Samsung                             |                                         |
| PO 4 | 20/02/2026 | Western Digital                     |                                         |
| PO 5 | 10/03/2026 | Seagate                             |                                         |
| PO 6 | 07/03/2026 | Samsung                             | **RAM-DDR5-16-KS: 1,850,000đ**          |
| PO 7 | 20/03/2026 | Intel                               |                                         |
| PO 8 | 05/04/2026 | Samsung                             | **RAM-DDR5-16-KS: 2,150,000đ** (+16.2%) |

> **KB2 check:** Mở PO 6 (07/03) và PO 8 (05/04) → so sánh giá RAM-DDR5-16-KS

---

## 5. Xác minh Sale Orders (410 SOs)

**Đường dẫn:** Sales → Orders → Orders

**Cách kiểm tra:**

1. Vào **Sales** → **Orders** → **Orders**
2. Tổng số đơn hàng = **410**, trạng thái `Sales Order` hoặc `Done`
3. Filter theo ngày: **01/01/2026 – 10/04/2026**

**Phân bố theo ngày:**

| Ngày tạo   | Số đơn tích lũy |
| ---------- | --------------- |
| 10/01/2026 | 42              |
| 20/01/2026 | 81              |
| 30/01/2026 | 101             |
| 09/02/2026 | 124             |
| 19/02/2026 | 187             |
| 01/03/2026 | 224             |
| 11/03/2026 | 271             |
| 21/03/2026 | 313             |
| 31/03/2026 | 353             |
| 10/04/2026 | 410 (tổng)      |

---

## 6. Xác minh Tồn kho (Stock Levels)

**Đường dẫn:** Inventory → Products → Products → click sản phẩm

**Cách xem on-hand nhanh:**

1. Vào **Inventory** → **Products** → **Products**
2. Số nhỏ màu xanh/xám trên mỗi card = số lượng tồn kho
3. Hoặc vào **Inventory → Reporting → Inventory** để xem dạng bảng

**Tồn kho mục tiêu:**

| SKU             | Tên                       | On Hand |
| --------------- | ------------------------- | ------- |
| RAM-DDR5-16-KS  | RAM DDR5 16GB Kingston    | 90      |
| RAM-DDR5-32-KS  | RAM DDR5 32GB Kingston    | 45      |
| RAM-DDR5-16-SS  | RAM DDR5 16GB Samsung     | 60      |
| RAM-DDR5-32-CO  | RAM DDR5 32GB Corsair     | 30      |
| SSD-1TB-SS-870  | SSD 1TB Samsung 870 EVO   | 55      |
| SSD-2TB-SS-870  | SSD 2TB Samsung 870 EVO   | 25      |
| SSD-512-WD-BL   | SSD 512GB WD Blue         | 70      |
| SSD-1TB-WD-BL   | SSD 1TB WD Blue           | 40      |
| HDD-2TB-SG-BC   | HDD 2TB Seagate Barracuda | 35      |
| HDD-4TB-SG-BC   | HDD 4TB Seagate Barracuda | 20      |
| HDD-2TB-WD-BL   | HDD 2TB WD Blue           | 30      |
| MON-27-LG-GP850 | Màn hình 27" LG 27GP850   | 15      |
| MON-24-DL-P2422 | Màn hình 24" Dell P2422H  | 20      |
| MON-27-SS-LS27  | Màn hình 27" Samsung LS27 | 18      |
| CPU-I5-14400    | CPU Intel Core i5-14400   | 25      |
| CPU-I7-14700K   | CPU Intel Core i7-14700K  | 15      |
| CPU-I9-14900K   | CPU Intel Core i9-14900K  | 8       |
| ACC-THERMAL-MX4 | Keo tản nhiệt Arctic MX-4 | 100     |
| ACC-FAN-NF-A12  | Fan case Noctua NF-A12    | 50      |

---

## 7. Kiểm tra 3 Kịch bản KB (Knowledge Base)

### KB1 – RAM DDR5 16GB Kingston: Đột biến tồn kho tháng 3–4

**Mô tả:** Tồn kho RAM-DDR5-16-KS tăng bất thường (z-score ≈ 2.8) trong giai đoạn 31/03–10/04/2026

**Đường dẫn xác minh:**

**Cách 1 – Báo cáo Inventory:**

1. **Inventory** → **Reporting** → **Inventory** (hoặc **Forecast**)
2. Group by: **Product** + **Date**
3. Filter: sản phẩm = `RAM DDR5 16GB Kingston`

**Cách 2 – Báo cáo Sales:**

1. **Sales** → **Reporting** → **Sales**
2. Measures: **Qty Ordered**
3. Group by: **Product** (row) + **Order Date: Month** (column)
4. Filter: Product = `RAM DDR5 16GB Kingston`
5. So sánh: tháng 3 và tháng 4 tăng đột biến so với tháng 1–2

---

### KB2 – Giá nhập RAM DDR5 16GB Kingston tăng 16.2%

**Mô tả:** Nhà cung cấp (Samsung) tăng giá từ **1,850,000đ** (07/03) lên **2,150,000đ** (05/04)

**Đường dẫn xác minh:**

1. **Purchase** → **Orders** → **Purchase Orders**
2. Tìm PO ngày **07/03/2026** → mở → tab **Order Lines** → tìm RAM-DDR5-16-KS → xem **Unit Price**
3. Tìm PO ngày **05/04/2026** → mở → tab **Order Lines** → so sánh giá

| PO    | Ngày           | Giá RAM-DDR5-16-KS |
| ----- | -------------- | ------------------ |
| PO 06 | 07/03/2026     | **1,850,000 VND**  |
| PO 08 | 05/04/2026     | **2,150,000 VND**  |
|       | **Chênh lệch** | **+16.2%**         |

**Cách xem nhanh qua sản phẩm:**

1. **Purchase** → **Products** → click **RAM DDR5 16GB Kingston**
2. Tab **Purchase** → xem bảng **Vendor Pricelist**

---

### KB3 – Thế Giới PC: Lần mua cuối cùng ngày 25/03/2026

**Mô tả:** Khách hàng lớn nhất ngừng mua sau 25/03/2026 – dấu hiệu churn

**Đường dẫn xác minh:**

1. **Sales** → **Orders** → **Orders**
2. Filter **Customer** = `Thế Giới PC`
3. Sort by **Order Date** giảm dần
4. Đơn hàng đầu tiên (mới nhất) phải có ngày = **25/03/2026**

**Hoặc xem qua Contact:**

1. **Contacts** → tìm `Thế Giới PC` → mở
2. Nút **"X Sales"** (góc phải trên) → click → xem danh sách đơn hàng
3. Sort by date → đơn cuối cùng = 25/03/2026

---

## 8. Xác minh Helpdesk Tickets (8 tickets)

**Đường dẫn:** Helpdesk → Helpdesk Ticket (menu trái) hoặc Dashboard → Helpdesk

**Module:** `helpdesk_mgmt` (OCA) — models: `helpdesk.ticket`, `helpdesk.ticket.team`, `helpdesk.ticket.stage`

**Cách kiểm tra:**

1. Vào **Helpdesk** → **Dashboard / Helpdesk Ticket**
2. Tổng số ticket = **8**, phân bổ theo stage

**Danh sách Stages:**

| Stage       | Loại                  | Tickets |
| ----------- | --------------------- | ------- |
| New         | Mở                    | 0       |
| In Progress | Đang xử lý            | 2       |
| Done        | Đã đóng (closed=True) | 5       |
| (pending)   | Mở                    | 1       |

**Danh sách 8 tickets:**

| Tiêu đề                                    | Khách hàng              | Stage       | Priority | Ngày tạo   |
| ------------------------------------------ | ----------------------- | ----------- | -------- | ---------- |
| Giao hàng thiếu - Đơn hàng ngày 25/03/2026 | Thế Giới PC             | Done        | Medium   | 26/03/2026 |
| Hàng nhận được bị lỗi - SSD Samsung 1TB    | Hoàng Long Computer     | Done        | Medium   | 15/02/2026 |
| Tư vấn nâng cấp RAM cho PC gaming          | Nguyễn Văn Bình         | Done        | Low      | 20/01/2026 |
| Thiếu hóa đơn VAT đơn hàng tháng 1         | Minh Khoa Tech          | Done        | Low      | 05/02/2026 |
| Báo giá RAM DDR5 số lượng lớn tháng 3      | IT Solutions ABC        | Done        | Low      | 07/03/2026 |
| Giá RAM DDR5 tăng cao bất thường           | Hùng Laptop Cần Thơ     | New         | Medium   | 06/04/2026 |
| Hỏi khi nào có hàng RAM DDR5 16GB          | ABC Computer Bình Dương | In Progress | Low      | 08/04/2026 |
| Đổi trả quạt case Noctua bị lỗi bearing    | Phạm Văn Long           | In Progress | Low      | 20/03/2026 |

**KB3 liên quan — Ticket Thế Giới PC:**

- Filter **Partner** = `Thế Giới PC` → thấy ticket "Giao hàng thiếu" ngày **26/03/2026**
- Ticket này liên quan trực tiếp đến đơn hàng cuối cùng ngày 25/03/2026 (churn signal)

**Activities quá hạn:**

- **Helpdesk** → **Helpdesk Ticket** → mở ticket Thế Giới PC → tab **Activities** → activity "Xác nhận khách đã nhận đủ hàng" deadline **28/03/2026** (quá hạn)
- **Inventory** → **Products** → **RAM DDR5 16GB Kingston** → tab **Activities** → activity "Cập nhật pricelist tháng 4" deadline **06/04/2026** (quá hạn)

---

## 9. Checklist tổng hợp

| Hạng mục                  | Kỳ vọng                                           | Trạng thái |
| ------------------------- | ------------------------------------------------- | ---------- |
| Users                     | 4 nhân viên active                                | ☐          |
| Products                  | 19 SKU (storable type)                            | ☐          |
| Partners                  | 17 đối tác                                        | ☐          |
| Purchase Orders           | 8 POs confirmed                                   | ☐          |
| Sale Orders               | 410 SOs                                           | ☐          |
| Tồn kho RAM-DDR5-16-KS    | On Hand = 90                                      | ☐          |
| KB1 – RAM spike tháng 3-4 | Số lượng bán tăng rõ                              | ☐          |
| KB2 – Giá nhập +16.2%     | PO6: 1,850,000đ vs PO8: 2,150,000đ                | ☐          |
| KB3 – Thế Giới PC churn   | Đơn cuối = 25/03/2026                             | ☐          |
| Helpdesk Tickets          | 8 tickets (5 Done, 2 In Progress, 1 New)          | ☐          |
| Activity quá hạn          | 1 activity trên ticket TG PC + 1 trên RAM product | ☐          |

---

_Tạo tự động bởi ERPSight seeding pipeline — Odoo 17 Community_
