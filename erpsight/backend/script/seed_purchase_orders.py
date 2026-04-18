"""
Script 2: Tạo Purchase Orders vào Odoo 17 qua XML-RPC.
8 POs lịch sử nhập hàng linh kiện, bao gồm kịch bản giá tăng 16%.
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


def find_product(ref):
    recs = execute("product.product", "search_read",
                   [[("default_code", "=", ref)]], fields=["id"], limit=1)
    if not recs:
        raise ValueError(f"Không tìm thấy product ref={ref}")
    return recs[0]["id"]


def find_partner(name):
    recs = execute("res.partner", "search_read",
                   [[("name", "ilike", name)]], fields=["id"], limit=1)
    if not recs:
        raise ValueError(f"Không tìm thấy partner name={name}")
    return recs[0]["id"]


def main():
    # ═════════════════════════════════════════════════════════════════════════
    # XÓA PURCHASE ORDERS CŨ
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== XÓA PURCHASE ORDERS CŨ ===")
    po_ids = execute("purchase.order", "search", [[]])
    if po_ids:
        # Step 1: cancel non-draft POs via business method
        cancelable = []
        for po_id in po_ids:
            po_data = execute("purchase.order", "read", [po_id], fields=["state"])
            if po_data and po_data[0]["state"] not in ("draft", "cancel"):
                cancelable.append(po_id)
        for po_id in cancelable:
            try:
                execute("purchase.order", "button_cancel", [po_id])
            except Exception:
                # Falls here when receipt is validated (receipt_status=full).
                # Force-write state to cancel so unlink can proceed.
                try:
                    execute("purchase.order", "write", [po_id], {"state": "cancel"})
                except Exception:
                    pass
        execute("purchase.order", "unlink", po_ids)
        print(f"  Đã xóa {len(po_ids)} PO cũ")

    # ═════════════════════════════════════════════════════════════════════════
    # TÌM IDs
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== TÌM PRODUCT & PARTNER IDs ===")
    minh_phat = find_partner("Minh Phát Technology")
    samsung   = find_partner("Samsung Electronics Vietnam")
    wd        = find_partner("Western Digital Vietnam")
    seagate   = find_partner("Seagate Technology Vietnam")
    intel     = find_partner("Intel Vietnam")

    p = {
        "RAM-DDR5-16-KS": find_product("RAM-DDR5-16-KS"),
        "RAM-DDR5-32-KS": find_product("RAM-DDR5-32-KS"),
        "RAM-DDR5-16-SS": find_product("RAM-DDR5-16-SS"),
        "RAM-DDR5-32-CO": find_product("RAM-DDR5-32-CO"),
        "SSD-1TB-SS-870": find_product("SSD-1TB-SS-870"),
        "SSD-512-WD-BL":  find_product("SSD-512-WD-BL"),
        "SSD-1TB-WD-BL":  find_product("SSD-1TB-WD-BL"),
        "HDD-2TB-SG-BC":  find_product("HDD-2TB-SG-BC"),
        "HDD-4TB-SG-BC":  find_product("HDD-4TB-SG-BC"),
        "HDD-2TB-WD-BL":  find_product("HDD-2TB-WD-BL"),
        "MON-27-LG-GP850": find_product("MON-27-LG-GP850"),
        "MON-24-DL-P2422": find_product("MON-24-DL-P2422"),
        "CPU-I5-14400":    find_product("CPU-I5-14400"),
        "CPU-I7-14700K":   find_product("CPU-I7-14700K"),
        "CPU-I9-14900K":   find_product("CPU-I9-14900K"),
        "ACC-THERMAL-MX4": find_product("ACC-THERMAL-MX4"),
    }
    print("  IDs found OK")

    # ═════════════════════════════════════════════════════════════════════════
    # ĐỊNH NGHĨA 8 POs
    # ═════════════════════════════════════════════════════════════════════════
    po_defs = [
        {
            "date": "2026-01-03 08:00:00",
            "partner_id": minh_phat,
            "lines": [
                (p["RAM-DDR5-16-KS"], 600, 1850000),
                (p["RAM-DDR5-32-KS"], 150, 3500000),
                (p["RAM-DDR5-16-SS"], 200, 1950000),
            ],
        },
        {
            "date": "2026-01-08 08:00:00",
            "partner_id": samsung,
            "lines": [
                (p["RAM-DDR5-16-SS"],  200, 1950000),
                (p["MON-27-LG-GP850"], 30,  6800000),
                (p["MON-24-DL-P2422"], 50,  3200000),
            ],
        },
        {
            "date": "2026-01-10 08:00:00",
            "partner_id": wd,
            "lines": [
                (p["SSD-1TB-WD-BL"], 300, 1300000),
                (p["SSD-512-WD-BL"], 400, 720000),
                (p["HDD-2TB-WD-BL"], 200, 920000),
            ],
        },
        {
            "date": "2026-02-12 08:00:00",
            "partner_id": minh_phat,
            "notes": "Sau Tết Âm lịch, nhập nhiều bù hàng",
            "lines": [
                (p["RAM-DDR5-16-KS"], 700, 1850000),
                (p["RAM-DDR5-32-KS"], 200, 3500000),
                (p["RAM-DDR5-32-CO"], 100, 3600000),
            ],
        },
        {
            "date": "2026-02-15 08:00:00",
            "partner_id": seagate,
            "lines": [
                (p["HDD-2TB-SG-BC"], 400, 890000),
                (p["HDD-4TB-SG-BC"], 150, 1600000),
            ],
        },
        {
            "date": "2026-03-07 08:00:00",
            "partner_id": minh_phat,
            "lines": [
                (p["RAM-DDR5-16-KS"], 500, 1850000),
                (p["RAM-DDR5-16-SS"], 150, 1950000),
                (p["SSD-1TB-SS-870"], 100, 1450000),
            ],
        },
        {
            "date": "2026-03-15 08:00:00",
            "partner_id": intel,
            "lines": [
                (p["CPU-I5-14400"],    50,  5200000),
                (p["CPU-I7-14700K"],   30,  10200000),
                (p["CPU-I9-14900K"],   10,  18500000),
                (p["ACC-THERMAL-MX4"], 200, 85000),
            ],
        },
        {
            "date": "2026-04-05 08:00:00",
            "partner_id": minh_phat,
            "notes": "Giá điều chỉnh do khan hiếm DRAM toàn cầu - "
                     "thiếu hụt từ nhu cầu AI server tháng 4/2026",
            "lines": [
                (p["RAM-DDR5-16-KS"], 600, 2150000),   # +16.2%
                (p["RAM-DDR5-32-KS"], 200, 4060000),   # tăng tương ứng
                (p["RAM-DDR5-16-SS"], 200, 2262000),   # +16%
            ],
        },
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # TẠO POs
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== TẠO PURCHASE ORDERS ===")
    po_ids_created = []
    for i, po_def in enumerate(po_defs, 1):
        order_lines = []
        for prod_id, qty, price in po_def["lines"]:
            order_lines.append((0, 0, {
                "product_id": prod_id,
                "product_qty": qty,
                "price_unit": price,
            }))
        vals = {
            "partner_id": po_def["partner_id"],
            "order_line": order_lines,
        }
        if po_def.get("notes"):
            vals["notes"] = po_def["notes"]
        po_id = execute("purchase.order", "create", vals)
        po_ids_created.append((po_id, po_def["date"]))
        print(f"  [ok] PO {i}/8 – id={po_id}")

    # Receipt dates used in both date_planned fix (step 3) and receipt validation (step 5)
    # Each = date_order + 4 days lead time
    receipt_dates = [
        "2026-01-07 08:00:00",   # PO1: Jan 3 + 4 days (Minh Phát)
        "2026-01-12 08:00:00",   # PO2: Jan 8 + 4 days (Samsung)
        "2026-01-14 08:00:00",   # PO3: Jan 10 + 4 days (Western Digital)
        "2026-02-16 08:00:00",   # PO4: Feb 12 + 4 days (Minh Phát)
        "2026-02-19 08:00:00",   # PO5: Feb 15 + 4 days (Seagate)
        "2026-03-11 08:00:00",   # PO6: Mar 7 + 4 days (Minh Phát)
        "2026-03-19 08:00:00",   # PO7: Mar 15 + 4 days (Intel)
        "2026-04-09 08:00:00",   # PO8: Apr 5 + 4 days ← KEY for KB1
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # 1) CONFIRM tất cả PO
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== CONFIRM POs ===")
    all_po_ids = [x[0] for x in po_ids_created]
    for po_id in all_po_ids:
        execute("purchase.order", "button_confirm", [po_id])
    print(f"  Confirmed {len(all_po_ids)} POs")

    # ═════════════════════════════════════════════════════════════════════════
    # 2) FIX date_order
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== FIX DATE_ORDER ===")
    for po_id, date_str in po_ids_created:
        execute("purchase.order", "write", [po_id], {"date_order": date_str})
    print("  Dates updated")

    # ═════════════════════════════════════════════════════════════════════════
    # 3) FIX date_planned on PO lines (= date_order + lead_time)
    # ═════════════════════════════════════════════════════════════════════════
    # This mirrors the receipt_dates list so the PO line date matches the
    # actual receipt scheduled date shown in fetch_purchase_context.
    print("\n=== FIX DATE_PLANNED ON PO LINES ===")
    for (po_id, _), sched_date in zip(po_ids_created, receipt_dates):
        line_ids = execute("purchase.order.line", "search",
                           [[("order_id", "=", po_id)]])
        if line_ids:
            execute("purchase.order.line", "write", line_ids,
                    {"date_planned": sched_date})
    print("  date_planned updated for all PO lines")

    # ═════════════════════════════════════════════════════════════════════════
    # 4) SET Delivery Lead Time (product.supplierinfo)
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== SET VENDOR LEAD TIME ===")
    # Tìm product_tmpl_id cho RAM DDR5 16GB Kingston
    tmpl_recs = execute("product.template", "search_read",
                        [[("default_code", "=", "RAM-DDR5-16-KS")]],
                        fields=["id"], limit=1)
    if tmpl_recs:
        tmpl_id = tmpl_recs[0]["id"]
        # Search existing supplierinfo
        si_ids = execute("product.supplierinfo", "search",
                         [[("product_tmpl_id", "=", tmpl_id),
                           ("partner_id", "=", minh_phat)]])
        if si_ids:
            execute("product.supplierinfo", "write", si_ids, {"delay": 4})
            print(f"  Updated delay=4 cho supplierinfo ids={si_ids}")
        else:
            si_id = execute("product.supplierinfo", "create", {
                "product_tmpl_id": tmpl_id,
                "partner_id": minh_phat,
                "delay": 4,
                "price": 1850000,
            })
            print(f"  Created supplierinfo id={si_id} delay=4")

    # ═════════════════════════════════════════════════════════════════════════
    # 5) VALIDATE PO RECEIPTS – backdate scheduled_date + mark goods received
    # ═════════════════════════════════════════════════════════════════════════
    # PO08 (Apr 5 + 4) → Apr 9: goods received before KB1 detection date Apr 10
    # → confirms "no pending POs" signal in KB1.
    print("\n=== VALIDATE PO RECEIPTS ===")
    for (po_id, _), sched_date in zip(po_ids_created, receipt_dates):
        picks = execute(
            "stock.picking", "search_read",
            [[("purchase_id", "=", po_id), ("state", "not in", ["done", "cancel"])]],
            fields=["id", "name"],
        )
        if not picks:
            print(f"  [skip] No pending receipt for PO id={po_id}")
            continue

        for pick in picks:
            pick_id = pick["id"]
            # Backdate the scheduled receipt date
            execute("stock.picking", "write", [pick_id],
                    {"scheduled_date": sched_date})

            # In Odoo 17 (state=assigned), stock.move.line.quantity already
            # holds the reserved qty. button_validate can be called directly.
            try:
                result = execute("stock.picking", "button_validate", [pick_id])
                if isinstance(result, dict) and result.get("res_model"):
                    wiz_model = result["res_model"]
                    wiz_ctx   = result.get("context", {})
                    if wiz_model == "stock.backorder.confirmation":
                        wiz_id = execute(wiz_model, "create",
                                         {"pick_ids": [[4, pick_id]]}, wiz_ctx)
                        execute(wiz_model, "process_cancel_backorder", [[wiz_id]])
                    elif wiz_model == "stock.immediate.transfer":
                        wiz_id = execute(wiz_model, "create",
                                         {"pick_ids": [[6, 0, [pick_id]]]}, wiz_ctx)
                        execute(wiz_model, "process", [[wiz_id]])
                print(f"  ✅ {pick['name']} validated (scheduled: {sched_date[:10]})")
            except Exception as exc:
                print(f"  ⚠️  {pick['name']} validate error: {exc}")

    # ═════════════════════════════════════════════════════════════════════════
    # 5) VERIFY giá PO00006 vs PO00008
    # ═════════════════════════════════════════════════════════════════════════
    print("\n=== VERIFY GIÁ NHẬP ===")
    # PO thứ 6 (index 5) và PO thứ 8 (index 7)
    po6_id = po_ids_created[5][0]
    po8_id = po_ids_created[7][0]

    ram16ks_id = p["RAM-DDR5-16-KS"]

    lines_po6 = execute("purchase.order.line", "search_read",
                        [[("order_id", "=", po6_id),
                          ("product_id", "=", ram16ks_id)]],
                        fields=["price_unit"])
    lines_po8 = execute("purchase.order.line", "search_read",
                        [[("order_id", "=", po8_id),
                          ("product_id", "=", ram16ks_id)]],
                        fields=["price_unit"])

    price_old = lines_po6[0]["price_unit"] if lines_po6 else 0
    price_new = lines_po8[0]["price_unit"] if lines_po8 else 0
    pct = ((price_new - price_old) / price_old * 100) if price_old else 0

    print(f"  RAM-DDR5-16-KS PO cũ (07/03): {price_old:,.0f}đ")
    print(f"  RAM-DDR5-16-KS PO mới (05/04): {price_new:,.0f}đ")
    print(f"  % tăng: {pct:.1f}%")

    total = execute("purchase.order", "search_count", [[]])
    print(f"\n→ Tổng PO trong hệ thống: {total}")


if __name__ == "__main__":
    main()
