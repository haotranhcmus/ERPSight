"""
Script 1: Tạo Users, Products, Partners vào Odoo 17 qua XML-RPC.
Công ty: Công ty TNHH Phân Phối Linh Kiện Số
"""

import xmlrpc.client

URL = "http://educare-connect.me"
DB = "erpsight"
USER = "admin"
PASS = "admin"


def _connect():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
    _uid = common.authenticate(DB, USER, PASS, {})
    if not _uid:
        raise SystemExit("Xác thực thất bại.")
    _models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)
    return _uid, _models


def execute(model, method, *args, **kwargs):
    call_args = list(args)
    # Callers pass [[domain_conds]] but execute_kw expects [domain_conds] as args[0]
    if method in ("search", "search_read", "search_count") and call_args:
        d = call_args[0]
        if isinstance(d, list) and len(d) == 1 and isinstance(d[0], list):
            call_args[0] = d[0]  # unwrap [[...]] → [...]
    return models.execute_kw(DB, uid, PASS, model, method, call_args, kwargs)


uid, models = _connect()


def main():
    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN 1: NHÂN VIÊN (res.users)
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN 1: TẠO NHÂN VIÊN ===")

    ref = execute("ir.model.data", "search_read",
                  [[("module", "=", "base"), ("name", "=", "group_user")]],
                  fields=["res_id"], limit=1)
    group_user_ids = [ref[0]["res_id"]] if ref else []

    employees = [
        {"name": "Nguyễn Minh Khoa", "login": "khoa.sale", "password": "Admin@123"},
        {"name": "Trần Thu Hằng",    "login": "hang.sale", "password": "Admin@123"},
        {"name": "Lê Văn Đức",       "login": "duc.purchase", "password": "Admin@123"},
        {"name": "Phạm Thị Lan",     "login": "lan.support", "password": "Admin@123"},
    ]

    created_users = 0
    for emp in employees:
        existing = execute("res.users", "search", [[("login", "=", emp["login"])]])
        if existing:
            print(f"  [skip] {emp['login']} đã tồn tại")
            continue
        vals = {
            "name": emp["name"],
            "login": emp["login"],
            "password": emp["password"],
            "share": False,
        }
        if group_user_ids:
            vals["groups_id"] = [(6, 0, group_user_ids)]
        execute("res.users", "create", vals)
        created_users += 1
        print(f"  [ok] Tạo user: {emp['login']} ({emp['name']})")
    print(f"→ Đã tạo {created_users} user mới")

    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN 2: SẢN PHẨM (product.template)
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN 2: XÓA & TẠO SẢN PHẨM ===")

    # Xóa SO/PO trước để tránh FK constraint khi xóa products
    print("  Dọn dẹp SO/PO cũ trước khi xóa sản phẩm...")
    so_ids = execute("sale.order", "search", [[]])
    if so_ids:
        # Batch cancel confirmed SOs
        to_cancel = [s for s in execute("sale.order", "read", so_ids, fields=["id", "state"])
                     if s["state"] not in ("draft", "cancel")]
        to_cancel_ids = [s["id"] for s in to_cancel]
        if to_cancel_ids:
            try:
                execute("sale.order", "action_cancel", to_cancel_ids)
            except Exception:
                # force-write state as fallback
                execute("sale.order", "write", to_cancel_ids, {"state": "cancel"})
        execute("sale.order", "unlink", so_ids)
        print(f"    Đã xóa {len(so_ids)} sale order")

    po_ids = execute("purchase.order", "search", [[]])
    if po_ids:
        for po_id in po_ids:
            d = execute("purchase.order", "read", [po_id], fields=["state"])
            if d and d[0]["state"] not in ("draft", "cancel"):
                try:
                    execute("purchase.order", "button_cancel", [po_id])
                except Exception:
                    pass
        execute("purchase.order", "unlink", po_ids)
        print(f"    Đã xóa {len(po_ids)} purchase order")

    storable_ids = execute("product.template", "search",
                           [[("type", "in", ["product", "consu"])]])
    if storable_ids:
        # Thử xóa; nếu bị block bởi done stock.moves → archive + đổi tên ref tránh trùng
        try:
            execute("product.template", "unlink", storable_ids)
            print(f"  Đã xóa {len(storable_ids)} product.template cũ")
        except Exception:
            for tmpl_id in storable_ids:
                try:
                    t = execute("product.template", "read", [tmpl_id], fields=["default_code"])
                    old_ref = (t[0].get("default_code") or "") if t else ""
                    execute("product.template", "write", [tmpl_id], {
                        "active": False,
                        "default_code": f"_ARCH_{tmpl_id}",
                        "name": f"[ARCH] {old_ref}",
                    })
                except Exception:
                    pass
            print(f"  [info] Archive {len(storable_ids)} products cũ (stock moves đã done không thể xóa)")

    uom_records = execute("uom.uom", "search_read",
                          [[("name", "in", ["Units", "Unit(s)", "Cái", "Chiếc"])]],
                          fields=["id", "name"], limit=5)
    uom_id = uom_records[0]["id"] if uom_records else False
    if uom_id:
        print(f"  UoM id = {uom_id} ({uom_records[0]['name']})")

    products = [
        {"name": "RAM DDR5 16GB Kingston",        "default_code": "RAM-DDR5-16-KS",   "standard_price": 1850000,  "list_price": 2200000},
        {"name": "RAM DDR5 32GB Kingston",        "default_code": "RAM-DDR5-32-KS",   "standard_price": 3500000,  "list_price": 4350000},
        {"name": "RAM DDR5 16GB Samsung",         "default_code": "RAM-DDR5-16-SS",   "standard_price": 1950000,  "list_price": 2350000},
        {"name": "RAM DDR5 32GB Corsair",         "default_code": "RAM-DDR5-32-CO",   "standard_price": 3600000,  "list_price": 4300000},
        {"name": "SSD 1TB Samsung 870 EVO",       "default_code": "SSD-1TB-SS-870",   "standard_price": 1450000,  "list_price": 1750000},
        {"name": "SSD 2TB Samsung 870 EVO",       "default_code": "SSD-2TB-SS-870",   "standard_price": 2700000,  "list_price": 3200000},
        {"name": "SSD 512GB WD Blue",             "default_code": "SSD-512-WD-BL",    "standard_price": 720000,   "list_price": 890000},
        {"name": "SSD 1TB WD Blue",               "default_code": "SSD-1TB-WD-BL",    "standard_price": 1300000,  "list_price": 1580000},
        {"name": "HDD 2TB Seagate Barracuda",     "default_code": "HDD-2TB-SG-BC",    "standard_price": 890000,   "list_price": 1100000},
        {"name": "HDD 4TB Seagate Barracuda",     "default_code": "HDD-4TB-SG-BC",    "standard_price": 1600000,  "list_price": 1950000},
        {"name": "HDD 2TB WD Blue",               "default_code": "HDD-2TB-WD-BL",    "standard_price": 920000,   "list_price": 1150000},
        {"name": "Màn hình 27 inch LG 27GP850",   "default_code": "MON-27-LG-GP850",  "standard_price": 6800000,  "list_price": 8200000},
        {"name": "Màn hình 24 inch Dell P2422H",  "default_code": "MON-24-DL-P2422",  "standard_price": 3200000,  "list_price": 3900000},
        {"name": "Màn hình 27 inch Samsung LS27", "default_code": "MON-27-SS-LS27",   "standard_price": 4500000,  "list_price": 5500000},
        {"name": "CPU Intel Core i5-14400",       "default_code": "CPU-I5-14400",      "standard_price": 5200000,  "list_price": 6300000},
        {"name": "CPU Intel Core i7-14700K",      "default_code": "CPU-I7-14700K",     "standard_price": 10200000, "list_price": 12500000},
        {"name": "CPU Intel Core i9-14900K",      "default_code": "CPU-I9-14900K",     "standard_price": 18500000, "list_price": 22000000},
        {"name": "Keo tản nhiệt Arctic MX-4",     "default_code": "ACC-THERMAL-MX4",  "standard_price": 85000,    "list_price": 120000},
        {"name": "Fan case Noctua NF-A12",        "default_code": "ACC-FAN-NF-A12",   "standard_price": 320000,   "list_price": 420000},
    ]

    created_products = 0
    for p in products:
        vals = {
            "name": p["name"],
            "default_code": p["default_code"],
            "type": "product",
            "list_price": p["list_price"],
            "standard_price": p["standard_price"],
            "sale_ok": True,
            "purchase_ok": True,
        }
        if uom_id:
            vals["uom_id"] = uom_id
            vals["uom_po_id"] = uom_id
        execute("product.template", "create", vals)
        created_products += 1
        print(f"  [ok] {p['default_code']} – {p['name']}")
    print(f"→ Đã tạo {created_products} sản phẩm")

    # ═════════════════════════════════════════════════════════════════════════
    # PHẦN 3: ĐỐI TÁC (res.partner)
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== PHẦN 3: XÓA & TẠO ĐỐI TÁC ===")

    company_ids = execute("res.company", "search", [[]])
    company_partner_ids = []
    if company_ids:
        companies = execute("res.company", "read", company_ids, fields=["partner_id"])
        company_partner_ids = [c["partner_id"][0] for c in companies if c.get("partner_id")]

    old_ids = execute("res.partner", "search",
                      [["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0)]])
    to_delete = [pid for pid in old_ids if pid not in company_partner_ids]
    if to_delete:
        execute("res.partner", "unlink", to_delete)
        print(f"  Đã xóa {len(to_delete)} partner cũ")

    partners = [
        # ── KHÁCH HÀNG VIP ────────────────────────────────────────────────
        {"name": "Công ty TNHH Thế Giới PC",       "is_company": True,  "customer_rank": 5, "supplier_rank": 0,
         "street": "245 Nguyễn Đình Chiểu, Quận 3, TP.HCM",     "phone": "0901234567", "email": "order@thegioipc.vn"},
        {"name": "Công ty TNHH IT Solutions ABC",   "is_company": True,  "customer_rank": 5, "supplier_rank": 0,
         "street": "78 Cộng Hòa, Tân Bình, TP.HCM",             "phone": "0912345678", "email": "purchase@itsolutions.vn"},
        # ── KHÁCH HÀNG B2B VỪA ────────────────────────────────────────────
        {"name": "Cửa hàng Hoàng Long Computer",    "is_company": True,  "customer_rank": 3, "supplier_rank": 0,
         "street": "45 Lê Văn Việt, Quận 9, TP.HCM",            "phone": "0923456789", "email": "hoanglong.pc@gmail.com"},
        {"name": "Công ty TNHH Minh Khoa Tech",     "is_company": True,  "customer_rank": 3, "supplier_rank": 0,
         "street": "112 Đinh Tiên Hoàng, Bình Thạnh, TP.HCM",   "phone": "0934567890", "email": "info@minhkhoa.vn"},
        {"name": "Cửa hàng Hùng Laptop Cần Thơ",   "is_company": True,  "customer_rank": 3, "supplier_rank": 0,
         "street": "23 Trần Phú, Ninh Kiều, Cần Thơ",           "phone": "0710234567", "email": "hunglaptop.ct@gmail.com"},
        {"name": "Công ty CP Công Nghệ Phúc Anh",   "is_company": True,  "customer_rank": 3, "supplier_rank": 0,
         "street": "56 Lý Thường Kiệt, Hoàn Kiếm, Hà Nội",     "phone": "0243456789", "email": "info@phucanhtech.vn"},
        {"name": "Cửa hàng ABC Computer Bình Dương","is_company": True,  "customer_rank": 3, "supplier_rank": 0,
         "street": "89 Đại lộ Bình Dương, Thủ Dầu Một, Bình Dương", "phone": "0274345678", "email": "abccomputer.bd@gmail.com"},
        # ── KHÁCH HÀNG LẺ ─────────────────────────────────────────────────
        {"name": "Nguyễn Văn Bình",  "is_company": False, "customer_rank": 1, "supplier_rank": 0,
         "phone": "0956789012", "email": "binh.nv@gmail.com"},
        {"name": "Trần Thị Mai",     "is_company": False, "customer_rank": 1, "supplier_rank": 0,
         "phone": "0967890123", "email": "mai.tt@gmail.com"},
        {"name": "Lê Minh Tuấn",     "is_company": False, "customer_rank": 1, "supplier_rank": 0,
         "phone": "0978901234", "email": "tuan.lm@gmail.com"},
        {"name": "Phạm Văn Long",    "is_company": False, "customer_rank": 1, "supplier_rank": 0,
         "phone": "0989012345", "email": "long.pv@gmail.com"},
        # ── NHÀ CUNG CẤP ──────────────────────────────────────────────────
        {"name": "Minh Phát Technology",          "is_company": True, "customer_rank": 0, "supplier_rank": 5,
         "street": "15 Khu CN Tân Bình, Tân Bình, TP.HCM",       "phone": "0281234567", "email": "sales@minhphat.vn"},
        {"name": "Samsung Electronics Vietnam",   "is_company": True, "customer_rank": 0, "supplier_rank": 4,
         "street": "Khu CN Yên Phong, Yên Phong, Bắc Ninh",       "phone": "02223456789", "email": "b2b@samsung.vn"},
        {"name": "Western Digital Vietnam",       "is_company": True, "customer_rank": 0, "supplier_rank": 3,
         "street": "Tầng 18 Bitexco, Quận 1, TP.HCM",             "phone": "02837890123", "email": "vn.sales@wdc.com"},
        {"name": "Seagate Technology Vietnam",    "is_company": True, "customer_rank": 0, "supplier_rank": 3,
         "street": "Lầu 12 Saigon Trade Center, Quận 1, TP.HCM",  "phone": "02838901234", "email": "vnsales@seagate.com"},
        {"name": "Intel Vietnam",                 "is_company": True, "customer_rank": 0, "supplier_rank": 3,
         "street": "Tầng 10 Vincom Center, Quận 1, TP.HCM",       "phone": "02839012345", "email": "vietnam@intel.com"},
        {"name": "Phụ Kiện Máy Tính Thành Đạt",  "is_company": True, "customer_rank": 0, "supplier_rank": 2,
         "street": "67 Huỳnh Tấn Phát, Quận 7, TP.HCM",           "phone": "0907654321", "email": "sale@thanhdatpc.vn"},
    ]

    created_partners = 0
    for p in partners:
        execute("res.partner", "create", p)
        created_partners += 1
        print(f"  [ok] {p['name']}")
    print(f"→ Đã tạo {created_partners} đối tác")

    # ═════════════════════════════════════════════════════════════════════════
    # TỔNG KẾT
    # ═════════════════════════════════════════════════════════════════════════
    total_products = execute("product.template", "search_count", [[("type", "=", "product")]])
    total_partners = execute("res.partner", "search_count",
                             [["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0)]])
    print("\n══════════════════════════════════════")
    print(f"  Tổng sản phẩm storable : {total_products}")
    print(f"  Tổng đối tác (KH + NCC): {total_partners}")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    main()
