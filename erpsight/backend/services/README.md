# `data_service` — API Reference

> **File:** `erpsight/backend/services/data_service.py`  
> **Vai trò:** Tầng service mỏng — bọc `OdooClient` + mapper thành các hàm single-call.  
> Đây là **entry point duy nhất** cho agent, detector và pipeline khi cần dữ liệu từ Odoo.  
> Agent **không được** gọi trực tiếp `OdooClient` hay mapper — luôn đi qua `data_service`.

---

## Import

```python
from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.services import data_service

client = OdooClient()
```

---

## Hàm 1 — `fetch_orders()`

### Chữ ký

```python
def fetch_orders(
    client: OdooClient,
    date_from:  Optional[str]        = None,
    date_to:    Optional[str]        = None,
    partner_id: Optional[int]        = None,
    states:     Optional[List[str]]  = None,
    limit:      int                  = 500,
    cost_map:   Optional[Dict[int, float]] = None,
) -> List[Order]
```

### Mô tả

Lấy danh sách đơn bán hàng (`sale.order`) kèm toàn bộ dòng sản phẩm (`sale.order.line`)
từ Odoo, tính margin cho từng dòng, và trả về danh sách `Order` đã map sẵn.

Hàm thực hiện **2 lần gọi Odoo API** internally:

1. `GET sale.order` — lọc theo điều kiện đầu vào
2. `GET sale.order.line` — lấy tất cả dòng của các đơn vừa lấy

### Tham số đầu vào

| Tham số      | Kiểu                       | Bắt buộc | Mặc định           | Mô tả                                                                   |
| ------------ | -------------------------- | -------- | ------------------ | ----------------------------------------------------------------------- |
| `client`     | `OdooClient`               | ✅       | —                  | Instance OdooClient đã khởi tạo                                         |
| `date_from`  | `str \| None`              | ❌       | `None`             | Lọc đơn hàng từ ngày này (inclusive). Định dạng: `"YYYY-MM-DD"`.        |
| `date_to`    | `str \| None`              | ❌       | `None`             | Lọc đơn hàng đến ngày này (inclusive). Định dạng: `"YYYY-MM-DD"`.       |
| `partner_id` | `int \| None`              | ❌       | `None`             | Chỉ lấy đơn của 1 khách hàng cụ thể. `res.partner.id` trong Odoo.       |
| `states`     | `List[str] \| None`        | ❌       | `["sale", "done"]` | Lọc theo trạng thái đơn. Truyền `None` để dùng default.                 |
| `limit`      | `int`                      | ❌       | `500`              | Số bản ghi tối đa. Truyền `0` để lấy tất cả (cẩn thận với dataset lớn). |
| `cost_map`   | `Dict[int, float] \| None` | ❌       | `None`             | Dict `{product_id: standard_price}` — xem note bên dưới.                |

> **Ghi chú `cost_map`:**  
> Nếu truyền `None`, hàm tự gọi `client.get_product_cost_map()` bên trong — thêm 1 lần API call.  
> Khi gọi nhiều hàm fetch trong cùng 1 session, nên fetch `cost_map` 1 lần rồi truyền vào tất cả để tránh gọi API thừa:
>
> ```python
> cost_map = client.get_product_cost_map()
> orders = data_service.fetch_orders(client, cost_map=cost_map)
> ```

> **Ghi chú `states`:**
>
> ```
> "draft"  — Nháp, chưa xác nhận
> "sale"   — Đã xác nhận, đang xử lý  ← default
> "done"   — Hoàn thành               ← default
> "cancel" — Đã hủy
> ```

### Đầu ra — `List[Order]`

Danh sách rỗng `[]` nếu không có đơn hàng nào khớp điều kiện.

#### Model `Order`

| Field          | Kiểu              | Bắt buộc | Mô tả                                                           | Ghi chú                                                                   |
| -------------- | ----------------- | -------- | --------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `order_id`     | `int`             | ✅       | ID đơn hàng trong Odoo (`sale.order.id`)                        | Dùng làm khóa join, không hiển thị cho user                               |
| `name`         | `str`             | ✅       | Số đơn hàng, ví dụ `"S00080"`                                   | Hiển thị trực tiếp                                                        |
| `partner_id`   | `int`             | ✅       | ID khách hàng (`res.partner.id`)                                | Dùng để filter, join với tickets                                          |
| `partner_name` | `str`             | ✅       | Tên khách hàng                                                  | Hiển thị, không cần query thêm                                            |
| `date_order`   | `datetime`        | ✅       | Ngày giờ xác nhận đơn hàng                                      | Trục thời gian — dùng để tính sales velocity (UC-01), order cycle (UC-12) |
| `amount_total` | `float`           | ✅       | Tổng tiền đơn hàng (bao gồm thuế, đơn vị VNĐ)                   | Dùng để tính AOV trend (UC-13)                                            |
| `state`        | `str`             | ✅       | Trạng thái đơn: `"draft"` \| `"sale"` \| `"done"` \| `"cancel"` | Dùng để lọc đơn đang active                                               |
| `lines`        | `List[OrderLine]` | ✅       | Danh sách dòng sản phẩm trong đơn                               | Luôn được điền — không bao giờ rỗng với đơn hợp lệ                        |

#### Model `OrderLine` (phần tử của `Order.lines`)

| Field            | Kiểu    | Mặc định | Mô tả                                                      | Ghi chú                                                                                                         |
| ---------------- | ------- | -------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `line_id`        | `int`   | —        | ID dòng trong Odoo (`sale.order.line.id`)                  | Khóa chính, dùng để tránh đếm trùng                                                                             |
| `order_id`       | `int`   | —        | ID đơn hàng cha                                            | Dùng để group dòng theo đơn                                                                                     |
| `product_id`     | `int`   | —        | ID sản phẩm (`product.product.id`)                         | **Quan trọng** — join với `Inventory.product_id` để tính `avg_daily_sales`                                      |
| `product_name`   | `str`   | —        | Tên sản phẩm                                               | Hiển thị trực tiếp                                                                                              |
| `quantity`       | `float` | —        | Số lượng bán                                               | Dùng tính `qty_sold` → `avg_daily_sales` (UC-01/02)                                                             |
| `price_unit`     | `float` | —        | Đơn giá bán (sau chiết khấu, chưa thuế)                    | So sánh với `cost_price` để tính margin (UC-07/08)                                                              |
| `price_subtotal` | `float` | —        | Doanh thu dòng = `quantity × price_unit`                   | Dùng tính weighted margin deviation (UC-08)                                                                     |
| `discount`       | `float` | `0.0`    | Chiết khấu %                                               | `0.0` nếu không có chiết khấu                                                                                   |
| `cost_price`     | `float` | `0.0`    | Giá vốn từ `cost_map[product_id]`                          | `0.0` nếu không truyền `cost_map` hoặc sản phẩm chưa có cost                                                    |
| `margin_pct`     | `float` | `0.0`    | Tỉ lệ lợi nhuận = `(price_unit - cost_price) / price_unit` | Âm = đang bán dưới giá vốn (UC-08). `0.0` nếu `price_unit = 0` hoặc không có cost. Làm tròn 4 chữ số thập phân. |

### Ví dụ sử dụng

```python
# UC-01: Lấy đơn 30 ngày để tính sales velocity
from datetime import date, timedelta

orders = data_service.fetch_orders(
    client,
    date_from=(date.today() - timedelta(days=30)).isoformat(),
    states=["sale", "done"],
)

# Tính tổng qty bán theo sản phẩm
from collections import defaultdict
qty_sold: dict[int, float] = defaultdict(float)
for order in orders:
    for line in order.lines:
        qty_sold[line.product_id] += line.quantity

# UC-08: Lấy đơn kèm margin để phát hiện bán lỗ
cost_map = client.get_product_cost_map()
orders = data_service.fetch_orders(client, cost_map=cost_map)

for order in orders:
    for line in order.lines:
        if line.margin_pct < 0:
            print(f"Bán lỗ: {order.name} | {line.product_name} | margin={line.margin_pct:.1%}")
```

---

## Hàm 2 — `fetch_inventories()`

### Chữ ký

```python
def fetch_inventories(
    client:        OdooClient,
    product_ids:   Optional[List[int]] = None,
    internal_only: bool                = True,
) -> List[Inventory]
```

### Mô tả

Lấy danh sách bản ghi tồn kho (`stock.quant`) từ Odoo.

Mỗi `Inventory` đại diện cho **tồn kho của 1 sản phẩm tại 1 vị trí kho cụ thể**.
Nếu cùng 1 sản phẩm đặt ở 2 ngăn kho khác nhau → 2 bản ghi `Inventory` riêng biệt.

Hàm thực hiện **1 lần gọi Odoo API** internally.

⚠️ Hai trường `avg_daily_sales` và `days_of_stock_remaining` **không được tự điền** — agent/detector phải tính và inject sau khi gọi hàm này.

### Tham số đầu vào

| Tham số         | Kiểu                | Bắt buộc | Mặc định | Mô tả                                                                                                                          |
| --------------- | ------------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `client`        | `OdooClient`        | ✅       | —        | Instance OdooClient đã khởi tạo                                                                                                |
| `product_ids`   | `List[int] \| None` | ❌       | `None`   | Chỉ lấy tồn kho của các sản phẩm trong danh sách. `None` = lấy tất cả sản phẩm.                                                |
| `internal_only` | `bool`              | ❌       | `True`   | `True` = chỉ kho nội bộ (`usage = "internal"`), bỏ qua kho ảo, kho khách hàng, kho nhà cung cấp. Hầu hết trường hợp để `True`. |

### Đầu ra — `List[Inventory]`

#### Model `Inventory`

| Field                     | Kiểu            | Mặc định | Mô tả                                                                                    | Ghi chú                                                                                 |
| ------------------------- | --------------- | -------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `quant_id`                | `int`           | —        | ID bản ghi tồn kho (`stock.quant.id`)                                                    | Khóa chính định danh 1 lô tại 1 vị trí                                                  |
| `product_id`              | `int`           | —        | ID sản phẩm                                                                              | **Join key** — dùng để map với `OrderLine.product_id`                                   |
| `product_name`            | `str`           | —        | Tên sản phẩm                                                                             | Hiển thị trực tiếp                                                                      |
| `qty_on_hand`             | `float`         | —        | Tổng số lượng vật lý đang có trong kho                                                   | Bao gồm cả hàng đã đặt chỗ                                                              |
| `reserved_quantity`       | `float`         | `0.0`    | Số lượng đã được giữ chỗ cho đơn bán đã xác nhận nhưng chưa xuất kho                     | Không được dùng để bán thêm                                                             |
| `available_qty`           | `float`         | `0.0`    | Số lượng có thể bán ngay = `qty_on_hand - reserved_quantity`                             | **Số quan trọng nhất** — dùng tính `days_of_stock_remaining` (UC-02)                    |
| `location_id`             | `int`           | —        | ID vị trí kho (`stock.location.id`)                                                      | Dùng để filter/group theo warehouse                                                     |
| `location_name`           | `str`           | —        | Tên vị trí kho, ví dụ `"WH/Stock"`, `"WH/Shelf-A"`                                       | Hiển thị, gộp tồn theo kho                                                              |
| `avg_daily_sales`         | `float`         | `0.0`    | ⚠️ **Không tự điền.** Tốc độ bán trung bình mỗi ngày (30 ngày gần nhất)                  | Phải tính và inject sau khi gọi `fetch_inventories()` — xem mục "Inject derived fields" |
| `days_of_stock_remaining` | `float \| None` | `None`   | ⚠️ **Không tự điền.** Số ngày tồn kho còn có thể bán = `available_qty / avg_daily_sales` | `None` = chưa tính. Agent phải kiểm tra `is not None` trước khi dùng.                   |

### Inject derived fields (bắt buộc cho UC-02/03)

```python
from collections import defaultdict
from datetime import date, timedelta

# Bước 1: Lấy tồn kho
inventories = data_service.fetch_inventories(client)

# Bước 2: Lấy đơn bán 30 ngày để tính velocity
past_orders = data_service.fetch_orders(
    client,
    date_from=(date.today() - timedelta(days=30)).isoformat(),
)

# Bước 3: Tính tổng qty bán theo product_id
qty_sold: dict[int, float] = defaultdict(float)
for order in past_orders:
    for line in order.lines:
        qty_sold[line.product_id] += line.quantity

# Bước 4: Inject vào từng Inventory object
for inv in inventories:
    inv.avg_daily_sales = qty_sold.get(inv.product_id, 0.0) / 30
    if inv.avg_daily_sales > 0:
        inv.days_of_stock_remaining = round(inv.available_qty / inv.avg_daily_sales, 1)
    # Nếu avg_daily_sales = 0 → days_of_stock_remaining giữ None (không bán được → không tính)

# Bước 5: So sánh với lead time (UC-03)
for inv in inventories:
    if inv.days_of_stock_remaining is not None and inv.days_of_stock_remaining < 7:
        print(f"CẢNH BÁO: {inv.product_name} còn {inv.days_of_stock_remaining} ngày hàng")
```

---

## Hàm 3 — `fetch_supplier_orders()`

### Chữ ký

```python
def fetch_supplier_orders(
    client:     OdooClient,
    date_from:  Optional[str]       = None,
    date_to:    Optional[str]       = None,
    partner_id: Optional[int]       = None,
    states:     Optional[List[str]] = None,
    limit:      int                 = 500,
) -> List[SupplierOrder]
```

### Mô tả

Lấy danh sách đơn mua hàng (`purchase.order`) kèm dòng chi tiết (`purchase.order.line`)
từ module Purchase của Odoo.

Hàm thực hiện **2 lần gọi Odoo API** internally:

1. `GET purchase.order` — lọc theo điều kiện
2. `GET purchase.order.line` — lấy tất cả dòng của các PO vừa lấy

### Tham số đầu vào

| Tham số      | Kiểu                | Bắt buộc | Mặc định                                                     | Mô tả                                                                                             |
| ------------ | ------------------- | -------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `client`     | `OdooClient`        | ✅       | —                                                            | Instance OdooClient đã khởi tạo                                                                   |
| `date_from`  | `str \| None`       | ❌       | `None`                                                       | Lọc PO từ ngày này theo `date_order`. Định dạng: `"YYYY-MM-DD"`.                                  |
| `date_to`    | `str \| None`       | ❌       | `None`                                                       | Lọc PO đến ngày này.                                                                              |
| `partner_id` | `int \| None`       | ❌       | `None`                                                       | Chỉ lấy đơn của 1 nhà cung cấp cụ thể (`res.partner.id`).                                         |
| `states`     | `List[str] \| None` | ❌       | Tất cả trừ `"cancel"` — `["draft","sent","purchase","done"]` | Lọc theo trạng thái. Truyền `["purchase"]` để chỉ lấy đơn đã xác nhận đang chờ nhận hàng (UC-03). |
| `limit`      | `int`               | ❌       | `500`                                                        | Số bản ghi tối đa. `0` = tất cả.                                                                  |

> **Ghi chú `states`:**
>
> ```
> "draft"    — Nháp
> "sent"     — Đã gửi nhà cung cấp, chưa xác nhận
> "purchase" — Đã xác nhận, đang chờ nhận hàng  ← quan trọng nhất cho UC-03/06
> "done"     — Đã nhận hàng đủ
> "cancel"   — Đã hủy  ← bị loại khỏi default
> ```

### Đầu ra — `List[SupplierOrder]`

Danh sách rỗng `[]` nếu không có PO nào khớp điều kiện.

#### Model `SupplierOrder`

| Field          | Kiểu           | Mặc định | Mô tả                                                                       | Ghi chú                                                         |
| -------------- | -------------- | -------- | --------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `po_id`        | `int`          | —        | ID đơn mua (`purchase.order.id`)                                            | Khóa chính                                                      |
| `name`         | `str`          | —        | Số đơn mua, ví dụ `"PO00007"`                                               | Hiển thị trong cảnh báo, log                                    |
| `partner_id`   | `int`          | —        | ID nhà cung cấp (`res.partner.id`)                                          | UC-06: nhận diện vendor nào tăng giá                            |
| `partner_name` | `str`          | —        | Tên nhà cung cấp                                                            | Hiển thị trực tiếp                                              |
| `date_order`   | `datetime`     | —        | Ngày đặt mua                                                                | UC-06: cơ sở tính baseline giá 30 ngày                          |
| `state`        | `str`          | —        | Trạng thái: `"draft"` \| `"sent"` \| `"purchase"` \| `"done"` \| `"cancel"` | Filter qua tham số `states` (không cần filter lại sau khi nhận) |
| `lines`        | `List[POLine]` | `[]`     | Danh sách dòng hàng trong đơn                                               | Luôn được điền với PO hợp lệ                                    |

#### Model `POLine` (phần tử của `SupplierOrder.lines`)

| Field          | Kiểu               | Mặc định | Mô tả                              | Ghi chú                                                                                                                          |
| -------------- | ------------------ | -------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `line_id`      | `int`              | —        | ID dòng (`purchase.order.line.id`) | Khóa chính                                                                                                                       |
| `po_id`        | `int`              | —        | ID đơn mua cha                     | Group dòng theo PO                                                                                                               |
| `product_id`   | `int`              | —        | ID sản phẩm                        | UC-06: join để tính baseline giá theo từng product                                                                               |
| `product_name` | `str`              | —        | Tên sản phẩm                       | Hiển thị trong cảnh báo                                                                                                          |
| `quantity`     | `float`            | —        | Số lượng đặt mua                   | UC-05: tính số lượng RFQ = `lead_time × velocity + buffer`                                                                       |
| `price_unit`   | `float`            | —        | Đơn giá mua                        | **Trường trọng tâm của UC-06** — so với baseline 30 ngày để phát hiện tăng giá                                                   |
| `date_planned` | `datetime \| None` | `None`   | Ngày dự kiến nhận hàng             | **Trường trọng tâm của UC-03** — `None` nếu nhà cung cấp chưa xác nhận ngày giao. Luôn kiểm tra `is not None` trước khi so sánh. |

### Ví dụ sử dụng

```python
# UC-03: Phát hiện đơn đang chờ nhận hàng bị quá hạn
from datetime import datetime

pos = data_service.fetch_supplier_orders(
    client,
    states=["purchase"],  # chỉ lấy đơn đã xác nhận
)
now = datetime.now()

for po in pos:
    for line in po.lines:
        if line.date_planned and line.date_planned < now:
            overdue_days = (now - line.date_planned).days
            print(f"QUÁ HẠN {overdue_days} ngày: {po.name} | {po.partner_name} | {line.product_name}")

# UC-06: Lấy baseline giá 30 ngày cho 1 sản phẩm
from datetime import date, timedelta

recent_pos = data_service.fetch_supplier_orders(
    client,
    date_from=(date.today() - timedelta(days=30)).isoformat(),
    states=["purchase", "done"],
)

# Tập hợp giá nhập theo product_id
from collections import defaultdict
price_history: dict[int, list[float]] = defaultdict(list)
for po in recent_pos:
    for line in po.lines:
        price_history[line.product_id].append(line.price_unit)
```

---

## Hàm 4 — `fetch_tickets()`

### Chữ ký

```python
def fetch_tickets(
    client:     OdooClient,
    date_from:  Optional[str] = None,
    date_to:    Optional[str] = None,
    partner_id: Optional[int] = None,
    limit:      int           = 500,
) -> List[CustomerTicket]
```

### Mô tả

Lấy danh sách ticket hỗ trợ (`helpdesk.ticket`) từ module Helpdesk (OCA `helpdesk_mgmt` v17).

Hàm thực hiện **1 lần gọi Odoo API** internally.

### Tham số đầu vào

| Tham số      | Kiểu          | Bắt buộc | Mặc định | Mô tả                                                                                                 |
| ------------ | ------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `client`     | `OdooClient`  | ✅       | —        | Instance OdooClient đã khởi tạo                                                                       |
| `date_from`  | `str \| None` | ❌       | `None`   | Lọc ticket từ ngày tạo (`create_date`). Định dạng: `"YYYY-MM-DD"`.                                    |
| `date_to`    | `str \| None` | ❌       | `None`   | Lọc ticket đến ngày tạo.                                                                              |
| `partner_id` | `int \| None` | ❌       | `None`   | Chỉ lấy ticket của 1 khách hàng cụ thể. Dùng khi đang phân tích churn của 1 khách VIP cụ thể (UC-14). |
| `limit`      | `int`         | ❌       | `500`    | Số bản ghi tối đa. `0` = tất cả.                                                                      |

### Đầu ra — `List[CustomerTicket]`

#### Model `CustomerTicket`

| Field               | Kiểu               | Mặc định | Mô tả                                                                        | Ghi chú                                                                                                                                                                             |
| ------------------- | ------------------ | -------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ticket_id`         | `int`              | —        | ID ticket (`helpdesk.ticket.id`)                                             | Khóa chính                                                                                                                                                                          |
| `number`            | `str`              | `""`     | Mã số ticket, ví dụ `"HT00001"` (`_rec_name` trong OCA)                      | Hiển thị truyền thông tin, log cảnh báo. `"/"` nếu Odoo chưa cấp số.                                                                                                                |
| `name`              | `str`              | —        | Tiêu đề yêu cầu                                                              | Hiển thị trong insight churn (UC-15)                                                                                                                                                |
| `description`       | `str`              | `""`     | Mô tả chi tiết — thường là HTML từ Odoo                                      | UC-14: phân tích nội dung khiếu nại. `""` nếu trống.                                                                                                                                |
| `partner_id`        | `int \| None`      | `None`   | ID khách hàng (`res.partner.id`)                                             | `None` nếu ticket ẩn danh. **Join key** — dùng để lọc ticket của khách VIP đang phân tích.                                                                                          |
| `partner_name`      | `str`              | `""`     | Tên khách hàng                                                               | `""` nếu ticket ẩn danh                                                                                                                                                             |
| `stage_name`        | `str`              | `""`     | Tên giai đoạn hiện tại, ví dụ `"New"`, `"In Progress"`, `"Done"`             | Hiển thị. Dùng để xác định ticket đang mở hay đóng (nếu không có field `closed`).                                                                                                   |
| `priority`          | `str`              | `"0"`    | Mức độ ưu tiên: `"0"` Thấp \| `"1"` Trung bình \| `"2"` Cao \| `"3"` Rất cao | Mặc định Odoo = `"1"` (Medium). UC-14: trọng số trong Causal Proximity Score — P2/P3 ảnh hưởng mạnh hơn P0/P1                                                                       |
| `user_id`           | `int \| None`      | `None`   | ID nhân viên phụ trách (`res.users.id`)                                      | `None` nếu chưa gán. UC-16: xác định Account Manager để tạo task.                                                                                                                   |
| `user_name`         | `str`              | `""`     | Tên nhân viên phụ trách                                                      | Hiển thị trong task chăm sóc khách (UC-16). `""` nếu chưa gán.                                                                                                                      |
| `create_date`       | `datetime`         | —        | Thời điểm tạo ticket                                                         | UC-14: **tính temporal proximity** — bao nhiêu ngày trước đơn hàng cuối cùng của khách                                                                                              |
| `closed_date`       | `datetime \| None` | `None`   | Thời điểm đóng ticket                                                        | `None` nếu ticket chưa đóng. Field luôn có trong `helpdesk_mgmt` — tự điền khi ticket chuyển sang stage `closed=True`. **Không dùng để check trạng thái** — dùng `closed` thay thế. |
| `closed`            | `bool`             | `False`  | `True` nếu ticket đã đóng                                                    | **Related field** từ `stage_id.closed` — tự cập nhật khi ticket chuyển sang stage có `closed=True`. **Trường chính** để check open/closed.                                          |
| `last_stage_update` | `datetime \| None` | `None`   | Thời gian ticket được chuyển giai đoạn lần cuối                              | UC-14: phát hiện ticket "stale" — đóng nhưng không có follow-up gần đây → tín hiệu rủi ro. `None` nếu Odoo không log field này.                                                     |

### Ví dụ sử dụng

```python
# UC-14: Lấy ticket của 1 khách VIP trong 60 ngày gần nhất
from datetime import date, timedelta

tickets = data_service.fetch_tickets(
    client,
    date_from=(date.today() - timedelta(days=60)).isoformat(),
    partner_id=vip_customer_id,
)

# Tìm ticket tiêu cực đang mở trước thời điểm đơn hàng cuối
last_order_date = ...  # datetime của đơn hàng cuối cùng của khách

negative_tickets = [
    t for t in tickets
    if not t.closed                          # đang mở
    and t.create_date < last_order_date      # xảy ra trước đơn cuối
    and t.priority in ("1", "2", "3")        # mức độ ưu tiên cao
]

# Tính Causal Proximity Score (đơn giản)
priority_weight = {"0": 1, "1": 2, "2": 4, "3": 8}
causal_score = sum(priority_weight.get(t.priority, 1) for t in negative_tickets)
```

---
