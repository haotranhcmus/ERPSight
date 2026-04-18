"""
Script 4: Set tồn kho + Tạo helpdesk tickets + Activities quá hạn.
"""

import xmlrpc.client

URL = "http://educare-connect.me"
DB = "erpsight"
USER = "admin"
PASS = "admin"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(DB, USER, PASS, {})
if not uid:
    raise SystemExit("Xác thực thất bại.")
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)


def execute(model, method, *args, **kwargs):
    call_args = list(args)
    if method in ("search", "search_read", "search_count") and call_args:
        d = call_args[0]
        if isinstance(d, list) and len(d) == 1 and isinstance(d[0], list):
            call_args[0] = d[0]
    return models.execute_kw(DB, uid, PASS, model, method, call_args, kwargs)


def find_product_id(ref):
    recs = execute("product.product", "search_read",
                   [[("default_code", "=", ref)]], fields=["id"], limit=1)
    return recs[0]["id"] if recs else None


def find_partner(name):
    recs = execute("res.partner", "search_read",
                   [[("name", "ilike", name)]], fields=["id"], limit=1)
    return recs[0]["id"] if recs else None


def find_user(login):
    recs = execute("res.users", "search_read",
                   [[("login", "=", login)]], fields=["id"], limit=1)
    return recs[0]["id"] if recs else uid


def main():
    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN A: SET TỒN KHO
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN A: SET TỒN KHO ===")

    # Tìm location WH/Stock
    loc_ids = execute("stock.location", "search",
                      [[("usage", "=", "internal"), ("name", "ilike", "Stock")]])
    if not loc_ids:
        raise SystemExit("Không tìm thấy location WH/Stock")
    location_id = loc_ids[0]
    print(f"  Location WH/Stock id = {location_id}")

    inventory_data = {
        "RAM-DDR5-16-KS":  90,
        "RAM-DDR5-32-KS":  45,
        "RAM-DDR5-32-CO":  30,
        "RAM-DDR5-16-SS":  80,
        "SSD-1TB-SS-870":  35,
        "SSD-2TB-SS-870":  12,
        "SSD-512-WD-BL":   60,
        "SSD-1TB-WD-BL":   45,
        "HDD-2TB-SG-BC":   120,
        "HDD-4TB-SG-BC":   40,
        "HDD-2TB-WD-BL":   85,
        "MON-27-LG-GP850": 8,
        "MON-24-DL-P2422": 18,
        "MON-27-SS-LS27":  14,
        "CPU-I5-14400":    30,
        "CPU-I7-14700K":   12,
        "CPU-I9-14900K":   3,
        "ACC-THERMAL-MX4": 95,
        "ACC-FAN-NF-A12":  22,
    }

    for ref, qty in inventory_data.items():
        prod_id = find_product_id(ref)
        if not prod_id:
            print(f"  [skip] {ref} – sản phẩm không tồn tại")
            continue

        # Search existing quant
        quant_ids = execute("stock.quant", "search",
                            [[("product_id", "=", prod_id),
                              ("location_id", "=", location_id)]])
        if quant_ids:
            execute("stock.quant", "write", quant_ids,
                    {"inventory_quantity": qty})
            quant_id = quant_ids[0]
        else:
            quant_id = execute("stock.quant", "create", {
                "product_id": prod_id,
                "location_id": location_id,
                "inventory_quantity": qty,
            })

        # Apply inventory
        try:
            execute("stock.quant", "action_apply_inventory", [quant_id])
        except Exception:
            pass  # Odoo 17 may return None which triggers xmlrpc fault
        print(f"  ✅ {ref}: {qty} cái")

    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN A2: CẬP NHẬT STANDARD_PRICE (KB2 – Margin Erosion)
    # Costing method = Standard Price → không tự cập nhật khi nhận PO.
    # Cập nhật thủ công để phản ánh giá nhập mới từ P00138 (05/04).
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN A2: CẬP NHẬT STANDARD_PRICE ===")
    cost_updates = [
        ("RAM-DDR5-16-KS", 2_150_000),  # was 1,850,000 → +16.2% (P00138)
        ("RAM-DDR5-32-KS", 4_060_000),  # was 3,500,000 → +16%   (P00138)
        ("RAM-DDR5-16-SS", 2_262_000),  # was 1,950,000 → +16%   (P00138)
    ]
    for sku, new_cost in cost_updates:
        tmpl = execute("product.template", "search_read",
                       [[("default_code", "=", sku)]],
                       fields=["id", "name", "standard_price", "list_price"])
        if not tmpl:
            print(f"  ⚠️  {sku}: not found, skip")
            continue
        t = tmpl[0]
        execute("product.template", "write", [[t["id"]], {"standard_price": new_cost}])
        margin = (t["list_price"] - new_cost) / t["list_price"] * 100
        print(f"  ✅ {sku}: standard_price {t['standard_price']:,.0f} → {new_cost:,.0f}  (margin now {margin:.2f}%)")

    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN B: TẠO HELPDESK TICKETS
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN B: TẠO HELPDESK TICKETS ===")

    # Kiểm tra module helpdesk (cần cả helpdesk.ticket.team và helpdesk.ticket)
    try:
        execute("helpdesk.ticket.team", "search", [[]], limit=1)
    except Exception:
        print("  [WARN] Module helpdesk_mgmt chưa được cài đặt / thiếu helpdesk.ticket.team. Bỏ qua phần B & C.")
        return

    # Tìm helpdesk team
    team_ids = execute("helpdesk.ticket.team", "search", [[]], limit=1)
    team_id = team_ids[0] if team_ids else False

    # Tìm stages
    stages = execute("helpdesk.ticket.stage", "search_read", [[]], fields=["id", "name"])
    print(f"  Stages tìm thấy: {[s['name'] for s in stages]}")

    stage_done = None
    stage_new = None
    stage_progress = None
    for s in stages:
        name_lower = s["name"].lower()
        if any(kw in name_lower for kw in ["done", "resolved", "closed", "solved"]):
            stage_done = s["id"]
        if any(kw in name_lower for kw in ["new", "open"]):
            stage_new = s["id"]
        if any(kw in name_lower for kw in ["progress", "in progress"]):
            stage_progress = s["id"]

    if not stage_done and stages:
        stage_done = stages[-1]["id"]
        print(f"  [info] Dùng stage cuối '{stages[-1]['name']}' cho Done")
    if not stage_new and stages:
        stage_new = stages[0]["id"]
    if not stage_progress and stages:
        stage_progress = stages[1]["id"] if len(stages) > 1 else stages[0]["id"]

    # Tìm partners
    tg_pc = find_partner("Thế Giới PC")
    hoang_long = find_partner("Hoàng Long Computer")
    binh = find_partner("Nguyễn Văn Bình")
    minh_khoa = find_partner("Minh Khoa Tech")
    it_sol = find_partner("IT Solutions ABC")
    hung_laptop = find_partner("Hùng Laptop Cần Thơ")
    abc_bd = find_partner("ABC Computer Bình Dương")
    long_pv = find_partner("Phạm Văn Long")

    lan_uid = find_user("lan.support")

    # Xóa tickets cũ
    old_tickets = execute("helpdesk.ticket", "search", [[]])
    if old_tickets:
        execute("helpdesk.ticket", "unlink", old_tickets)
        print(f"  Đã xóa {len(old_tickets)} tickets cũ")

    tickets = [
        {
            "name": "Giao hàng thiếu - Đơn hàng ngày 25/03/2026",
            "partner_id": tg_pc,
            "team_id": team_id,
            "description": (
                "Khách hàng phản ánh qua điện thoại lúc 9h15 sáng ngày 26/03/2026: "
                "đơn hàng ngày 25/03 giao thiếu 10 cái RAM DDR5 16GB Kingston. "
                "Tổng giá trị hàng thiếu: 22,000,000đ.\n"
                "Đã liên hệ kho xác nhận và hẹn bổ sung trong ngày 27/03.\n"
                "NOTE: Chưa có xác nhận lại từ khách hàng sau khi giao bổ sung."
            ),
            "priority": "1",
            "stage_id": stage_done,
            "_create_date": "2026-03-26 09:15:00",
        },
        {
            "name": "Hàng nhận được bị lỗi - SSD Samsung 1TB",
            "partner_id": hoang_long,
            "team_id": team_id,
            "description": (
                "2 cái SSD 1TB Samsung 870 EVO trong đơn ngày 15/02/2026 bị lỗi, "
                "không nhận diện được khi cắm vào máy. Khách yêu cầu đổi hàng. "
                "Đã xử lý đổi 2 cái mới ngày 17/02."
            ),
            "priority": "1",
            "stage_id": stage_done,
            "_create_date": "2026-02-15 10:00:00",
        },
        {
            "name": "Tư vấn nâng cấp RAM cho PC gaming",
            "partner_id": binh,
            "team_id": team_id,
            "description": (
                "Khách hỏi tư vấn nâng cấp RAM 32GB cho build gaming. "
                "Đã tư vấn chọn RAM DDR5 32GB Kingston, khách đã mua."
            ),
            "priority": "0",
            "stage_id": stage_done,
            "_create_date": "2026-01-20 14:30:00",
        },
        {
            "name": "Thiếu hóa đơn VAT đơn hàng tháng 1",
            "partner_id": minh_khoa,
            "team_id": team_id,
            "description": (
                "Kế toán công ty phản ánh chưa nhận được hóa đơn VAT "
                "cho 3 đơn hàng trong tháng 1/2026. Đã xuất lại và gửi qua email."
            ),
            "priority": "0",
            "stage_id": stage_done,
            "_create_date": "2026-02-05 08:30:00",
        },
        {
            "name": "Báo giá RAM DDR5 số lượng lớn tháng 3",
            "partner_id": it_sol,
            "team_id": team_id,
            "description": (
                "Khách cần báo giá 500 cái RAM DDR5 16GB Kingston "
                "cho dự án nâng cấp server. Đã gửi báo giá ngày 08/03."
            ),
            "priority": "0",
            "stage_id": stage_done,
            "_create_date": "2026-03-07 11:00:00",
        },
        {
            "name": "Giá RAM DDR5 tăng cao bất thường so với báo giá cũ",
            "partner_id": hung_laptop,
            "team_id": team_id,
            "description": (
                "Khách phản ánh giá RAM DDR5 16GB trong đơn hàng ngày 06/04/2026 "
                "cao hơn 15% so với đơn tháng 3. Yêu cầu giải thích lý do tăng giá. "
                "Chưa xử lý."
            ),
            "priority": "1",
            "stage_id": stage_new,
            "_create_date": "2026-04-06 09:00:00",
        },
        {
            "name": "Hỏi khi nào có hàng RAM DDR5 16GB Kingston",
            "partner_id": abc_bd,
            "team_id": team_id,
            "description": (
                "Nhiều khách hỏi về tình trạng tồn kho RAM DDR5. "
                "Cửa hàng thông báo đặt hàng 50 cái nhưng lo ngại thiếu hàng "
                "do thị trường đang khan hiếm. Cần xác nhận ETA."
            ),
            "priority": "0",
            "stage_id": stage_progress,
            "_create_date": "2026-04-08 10:30:00",
        },
        {
            "name": "Đổi trả quạt case Noctua bị lỗi bearing",
            "partner_id": long_pv,
            "team_id": team_id,
            "description": (
                "Quạt case Noctua NF-A12 mua ngày 15/01 bị tiếng ồn lạ sau 2 tháng dùng. "
                "Đã kiểm tra, xác nhận lỗi bearing. Đang chờ hàng đổi từ nhà cung cấp."
            ),
            "priority": "0",
            "stage_id": stage_progress,
            "_create_date": "2026-03-20 15:00:00",
        },
    ]

    ticket_ids = {}
    for t in tickets:
        create_date = t.pop("_create_date")
        tid = execute("helpdesk.ticket", "create", t)
        # Set create_date (superuser can write)
        try:
            execute("helpdesk.ticket", "write", [tid], {"create_date": create_date})
        except Exception:
            pass
        ticket_ids[t["name"][:30]] = tid
        print(f"  [ok] {t['name'][:60]}")

    print(f"→ Đã tạo {len(tickets)} tickets")

    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN C: TẠO ACTIVITIES QUÁ HẠN
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN C: TẠO ACTIVITIES QUÁ HẠN ===")

    # Tìm activity types
    phone_call_type = execute("mail.activity.type", "search_read",
                              [[("name", "ilike", "phone")]],
                              fields=["id", "name"], limit=1)
    todo_type = execute("mail.activity.type", "search_read",
                        [[("name", "ilike", "to-do")]],
                        fields=["id", "name"], limit=1)
    if not todo_type:
        todo_type = execute("mail.activity.type", "search_read",
                            [[("name", "ilike", "todo")]],
                            fields=["id", "name"], limit=1)

    phone_type_id = phone_call_type[0]["id"] if phone_call_type else None
    todo_type_id = todo_type[0]["id"] if todo_type else None

    if not phone_type_id:
        print("  [warn] Không tìm thấy activity type Phone Call")
    if not todo_type_id:
        print("  [warn] Không tìm thấy activity type To-Do")

    # Ticket Thế Giới PC (ticket đầu tiên)
    tg_ticket_ids = execute("helpdesk.ticket", "search",
                            [[("partner_id", "=", tg_pc)]], limit=1)
    tg_ticket_id = tg_ticket_ids[0] if tg_ticket_ids else None

    # Product template RAM DDR5 16GB Kingston
    ram_tmpl = execute("product.template", "search_read",
                       [[("default_code", "=", "RAM-DDR5-16-KS")]],
                       fields=["id"], limit=1)
    ram_tmpl_id = ram_tmpl[0]["id"] if ram_tmpl else None

    khoa_uid = find_user("khoa.sale")
    lan_uid_val = find_user("lan.support")

    # Xóa activities cũ
    old_acts = execute("mail.activity", "search", [[]])
    if old_acts:
        execute("mail.activity", "unlink", old_acts)
        print(f"  Đã xóa {len(old_acts)} activities cũ")

    created_acts = 0

    # Activity 1: Follow-up ticket Thế Giới PC
    if phone_type_id and tg_ticket_id:
        execute("mail.activity", "create", {
            "res_model_id": execute("ir.model", "search",
                                    [[("model", "=", "helpdesk.ticket")]], limit=1)[0],
            "res_id": tg_ticket_id,
            "activity_type_id": phone_type_id,
            "summary": "Xác nhận khách đã nhận đủ hàng bổ sung chưa",
            "note": ("Gọi hỏi thăm sự hài lòng sau sự cố giao thiếu. "
                     "Đề cập ưu đãi đơn hàng tiếp theo nếu khách còn bực."),
            "date_deadline": "2026-03-28",
            "user_id": lan_uid_val,
        })
        created_acts += 1
        print("  [ok] Activity: Follow-up ticket Thế Giới PC (quá hạn 13 ngày)")

    # Activity 2: Review giá bán RAM DDR5
    if todo_type_id and ram_tmpl_id:
        execute("mail.activity", "create", {
            "res_model_id": execute("ir.model", "search",
                                    [[("model", "=", "product.template")]], limit=1)[0],
            "res_id": ram_tmpl_id,
            "activity_type_id": todo_type_id,
            "summary": "Cập nhật pricelist tháng 4 - giá nhập đã tăng",
            "note": ("PO00008 ngày 05/04 giá nhập tăng 16%. Cần review "
                     "và update sales price trước khi tiếp tục bán."),
            "date_deadline": "2026-04-06",
            "user_id": khoa_uid,
        })
        created_acts += 1
        print("  [ok] Activity: Review giá bán RAM DDR5 (quá hạn 4 ngày)")

    print(f"→ Đã tạo {created_acts} activities")


if __name__ == "__main__":
    main()
