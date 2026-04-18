"""
Reset Demo: Xóa toàn bộ data → chạy lại seed → verify 3 kịch bản.
Chạy trước mỗi buổi demo hoặc khi cần test lại.
"""

import xmlrpc.client
import time
import sys
import os
import importlib
import datetime

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


def safe_unlink(model, ids):
    if ids:
        execute(model, "unlink", ids)
    return len(ids) if ids else 0


def main():
    t0 = time.time()

    # ═════════════════════════════════════════════════════════════════════════
    # BƯỚC 1: XÓA THEO THỨ TỰ (tránh FK constraint)
    # ═════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BƯỚC 1: XÓA DỮ LIỆU CŨ")
    print("=" * 60)

    # a. mail.activity
    ids = execute("mail.activity", "search", [[]])
    n = safe_unlink("mail.activity", ids)
    print(f"  a) mail.activity: xóa {n}")

    # b. helpdesk.ticket
    try:
        ids = execute("helpdesk.ticket", "search", [[]])
        n = safe_unlink("helpdesk.ticket", ids)
        print(f"  b) helpdesk.ticket: xóa {n}")
    except Exception:
        print("  b) helpdesk.ticket: module chưa cài, bỏ qua")

    # c. account.move (invoices)
    try:
        move_ids = execute("account.move", "search",
                           [[("move_type", "in", ["in_invoice", "out_invoice"])]])
        if move_ids:
            # Reset to draft trước
            for mid in move_ids:
                try:
                    move_data = execute("account.move", "read", [mid], fields=["state"])
                    if move_data and move_data[0]["state"] == "posted":
                        execute("account.move", "button_draft", [mid])
                except Exception:
                    pass
            try:
                execute("account.move", "unlink", move_ids)
            except Exception:
                # Thử xóa từng cái
                for mid in move_ids:
                    try:
                        execute("account.move", "unlink", [mid])
                    except Exception:
                        pass
        print(f"  c) account.move: xóa {len(move_ids) if move_ids else 0}")
    except Exception:
        print("  c) account.move: bỏ qua")

    # d. stock.picking (draft/cancel)
    try:
        pick_ids = execute("stock.picking", "search",
                           [[("state", "in", ["draft", "cancel"])]])
        n = safe_unlink("stock.picking", pick_ids)
        print(f"  d) stock.picking (draft/cancel): xóa {n}")
    except Exception:
        print("  d) stock.picking: bỏ qua")

    # e. sale.order
    so_ids = execute("sale.order", "search", [[]])
    if so_ids:
        # Cancel associated pickings first
        pick_ids = execute("stock.picking", "search",
                           [[("sale_id", "in", so_ids),
                             ("state", "not in", ["done", "cancel"])]])
        for i in range(0, len(pick_ids), 50):
            try:
                execute("stock.picking", "action_cancel", pick_ids[i:i + 50])
            except Exception:
                pass
        # Batch cancel SOs
        for i in range(0, len(so_ids), 50):
            batch = so_ids[i:i + 50]
            try:
                execute("sale.order", "action_cancel", batch)
            except Exception:
                for so_id in batch:
                    try:
                        execute("sale.order", "action_cancel", [so_id])
                    except Exception:
                        pass
        # Force-write remaining active
        still_active = execute("sale.order", "search",
                               [[("id", "in", so_ids),
                                 ("state", "not in", ["draft", "cancel"])]])
        for so_id in still_active:
            try:
                execute("sale.order", "write", [so_id], {"state": "cancel"})
            except Exception:
                pass
        n = safe_unlink("sale.order", so_ids)
    else:
        n = 0
    print(f"  e) sale.order: xóa {n}")

    # f. purchase.order
    po_ids = execute("purchase.order", "search", [[]])
    if po_ids:
        for i in range(0, len(po_ids), 50):
            batch = po_ids[i:i + 50]
            try:
                execute("purchase.order", "button_cancel", batch)
            except Exception:
                for po_id in batch:
                    try:
                        execute("purchase.order", "button_cancel", [po_id])
                    except Exception:
                        # POs with validated receipts can't be button_cancel'd.
                        # Force-write state so unlink can proceed.
                        try:
                            execute("purchase.order", "write", [po_id], {"state": "cancel"})
                        except Exception:
                            pass
        n = safe_unlink("purchase.order", po_ids)
    else:
        n = 0
    print(f"  f) purchase.order: xóa {n}")

    # g. stock.quant (internal)
    try:
        int_locs = execute("stock.location", "search", [[("usage", "=", "internal")]])
        if int_locs:
            quant_ids = execute("stock.quant", "search",
                                [[("location_id", "in", int_locs)]])
            n = safe_unlink("stock.quant", quant_ids)
        else:
            n = 0
        print(f"  g) stock.quant (internal): xóa {n}")
    except Exception:
        print("  g) stock.quant: bỏ qua")

    # h. res.partner
    company_ids = execute("res.company", "search", [[]])
    company_partner_ids = []
    if company_ids:
        companies = execute("res.company", "read", company_ids, fields=["partner_id"])
        company_partner_ids = [c["partner_id"][0] for c in companies if c.get("partner_id")]

    partner_ids = execute("res.partner", "search",
                          [["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0)]])
    to_del = [p for p in partner_ids if p not in company_partner_ids and p > 10]
    n = safe_unlink("res.partner", to_del)
    print(f"  h) res.partner: xóa {n}")

    # i. product.template
    tmpl_ids = execute("product.template", "search",
                       [[("type", "=", "product"), ("id", ">", 20)]])
    deleted = archived = 0
    for i in range(0, len(tmpl_ids), 50):
        batch = tmpl_ids[i:i + 50]
        try:
            execute("product.template", "unlink", batch)
            deleted += len(batch)
        except Exception:
            for tid in batch:
                try:
                    execute("product.template", "unlink", [tid])
                    deleted += 1
                except Exception:
                    try:
                        execute("product.template", "write", [tid], {
                            "active": False,
                            "default_code": f"_ARCH_{tid}",
                        })
                        archived += 1
                    except Exception:
                        pass
    print(f"  i) product.template: xóa {deleted}, lưu trữ {archived}")

    # ═════════════════════════════════════════════════════════════════════════
    # BƯỚC 2: CHẠY LẠI CÁC SCRIPT
    # ═════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BƯỚC 2: CHẠY LẠI CÁC SCRIPT SEED")
    print("=" * 60)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, script_dir)

    print("\n── Script 1: Products & Partners ──")
    import seed_odoo
    importlib.reload(seed_odoo)
    seed_odoo.main()

    print("\n── Script 2: Purchase Orders ──")
    import seed_purchase_orders
    importlib.reload(seed_purchase_orders)
    seed_purchase_orders.main()

    print("\n── Script 3: Sale Orders ──")
    import seed_sale_orders
    importlib.reload(seed_sale_orders)
    seed_sale_orders.main()

    print("\n── Script 4: Finalize – Validate ALL deliveries ──")
    # Boost tạm thời tồn kho 9999 → action_assign tất cả DOs → validate tất cả
    # → outgoing_qty = 0 cho mọi sản phẩm → Forecasted = On Hand (sạch).
    # KB1 spike được detect qua sales velocity trend (SO history), không phải pending DOs.
    import seed_finalize
    importlib.reload(seed_finalize)
    seed_finalize.main()

    print("\n── Script 5: Inventory & Tickets ──")
    import set_inventory_and_tickets
    importlib.reload(set_inventory_and_tickets)
    set_inventory_and_tickets.main()

    # ═════════════════════════════════════════════════════════════════════════
    # BƯỚC 3: VERIFY 3 KỊCH BẢN
    # ═════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BƯỚC 3: VERIFY KỊCH BẢN")
    print("=" * 60)

    results = {"pass": 0, "fail": 0, "issues": []}

    # ── KỊCH BẢN 1: CHÁY KHO ──────────────────────────────────────────────
    print("\n--- KỊCH BẢN 1: CHÁY KHO ---")

    # Tồn kho RAM DDR5 16GB Kingston
    ram_prod = execute("product.product", "search_read",
                       [[("default_code", "=", "RAM-DDR5-16-KS")]],
                       fields=["id"], limit=1)
    stock_qty = 0
    if ram_prod:
        quants = execute("stock.quant", "search_read",
                         [[("product_id", "=", ram_prod[0]["id"]),
                           ("location_id.usage", "=", "internal")]],
                         fields=["quantity"])
        stock_qty = sum(q["quantity"] for q in quants)
    print(f"Tồn kho RAM DDR5 16GB Kingston: {stock_qty:.0f} cái (cần = 90)")

    # Qty bán theo ngày
    ram_pid = ram_prod[0]["id"] if ram_prod else 0
    march_lines = execute("sale.order.line", "search_read",
                          [[("product_id", "=", ram_pid),
                            ("order_id.date_order", ">=", "2026-03-01"),
                            ("order_id.date_order", "<", "2026-03-31")]],
                          fields=["product_uom_qty"])
    march_total = sum(l["product_uom_qty"] for l in march_lines)
    march_days = 30

    april_lines = execute("sale.order.line", "search_read",
                          [[("product_id", "=", ram_pid),
                            ("order_id.date_order", ">=", "2026-03-31"),
                            ("order_id.date_order", "<=", "2026-04-10")]],
                          fields=["product_uom_qty"])
    april_total = sum(l["product_uom_qty"] for l in april_lines)
    april_days = 11

    avg_march = march_total / march_days if march_days else 0
    avg_april = april_total / april_days if april_days else 0
    ratio = avg_april / avg_march if avg_march > 0 else 0

    print(f"Qty bán TB ngày 01-30/03: {avg_march:.1f} cái/ngày")
    print(f"Qty bán TB ngày 31/03-10/04: {avg_april:.1f} cái/ngày")
    print(f"Tỷ lệ tăng: {ratio:.1f}x lần (cần > 3x)")

    if ratio > 3:
        print("→ PASS ✅")
        results["pass"] += 1
    else:
        print("→ FAIL ❌")
        results["fail"] += 1
        results["issues"].append(f"KB1: tỷ lệ tăng chỉ {ratio:.1f}x")

    # ── KỊCH BẢN 2: MARGIN ÂM ─────────────────────────────────────────────
    print("\n--- KỊCH BẢN 2: MARGIN ÂM ---")

    # Giá nhập PO cũ vs mới
    po_recs = execute("purchase.order", "search_read", [[]],
                      fields=["id", "date_order"], order="date_order asc")
    po_old_id = None
    po_new_id = None
    for po in po_recs:
        d = po["date_order"]
        if "2026-03" in d and po_old_id is None:
            po_old_id = po["id"]
        if "2026-04" in d:
            po_new_id = po["id"]

    price_old = price_new = 0
    if po_old_id:
        lines = execute("purchase.order.line", "search_read",
                         [[("order_id", "=", po_old_id),
                           ("product_id", "=", ram_pid)]],
                         fields=["price_unit"])
        if lines:
            price_old = lines[0]["price_unit"]

    if po_new_id:
        lines = execute("purchase.order.line", "search_read",
                         [[("order_id", "=", po_new_id),
                           ("product_id", "=", ram_pid)]],
                         fields=["price_unit"])
        if lines:
            price_new = lines[0]["price_unit"]

    pct_increase = ((price_new - price_old) / price_old * 100) if price_old else 0

    # Giá bán hiện tại
    ram_tmpl = execute("product.template", "search_read",
                       [[("default_code", "=", "RAM-DDR5-16-KS")]],
                       fields=["list_price"], limit=1)
    sale_price = ram_tmpl[0]["list_price"] if ram_tmpl else 0
    margin = sale_price - price_new

    print(f"Giá nhập PO cũ (tháng 3): {price_old:,.0f}đ")
    print(f"Giá nhập PO mới (tháng 4): {price_new:,.0f}đ")
    print(f"% tăng: {pct_increase:.1f}% (cần ~16%)")
    print(f"Giá bán hiện tại: {sale_price:,.0f}đ")
    print(f"Margin thô: {margin:,.0f}đ (cần < 100,000đ hoặc âm)")

    if 14 <= pct_increase <= 18 and margin < 100000:
        print("→ PASS ✅")
        results["pass"] += 1
    else:
        print("→ FAIL ❌")
        results["fail"] += 1
        results["issues"].append(f"KB2: tăng {pct_increase:.1f}%, margin {margin:,.0f}đ")

    # ── KỊCH BẢN 3: CHURN VIP ─────────────────────────────────────────────
    print("\n--- KỊCH BẢN 3: CHURN VIP ---")

    tg_partner = execute("res.partner", "search",
                         [[("name", "ilike", "Thế Giới PC")]], limit=1)
    tg_partner_id = tg_partner[0] if tg_partner else 0

    tg_orders = execute("sale.order", "search_read",
                        [[("partner_id", "=", tg_partner_id)]],
                        fields=["date_order"], order="date_order desc")
    n_orders = len(tg_orders)
    last_date_str = tg_orders[0]["date_order"] if tg_orders else "N/A"
    last_date = None
    if tg_orders:
        last_date = datetime.datetime.strptime(
            tg_orders[0]["date_order"][:10], "%Y-%m-%d").date()
    silent_days = (datetime.date(2026, 4, 10) - last_date).days if last_date else 0

    # Ticket phàn nàn
    try:
        tg_tickets = execute("helpdesk.ticket", "search_count",
                             [[("partner_id", "=", tg_partner_id)]])
    except Exception:
        tg_tickets = 0

    # Activity quá hạn
    has_overdue_activity = False
    try:
        tg_acts = execute("mail.activity", "search_count",
                          [[("date_deadline", "<", "2026-04-10")]])
        has_overdue_activity = tg_acts > 0
    except Exception:
        pass

    print(f"Đơn hàng Thế Giới PC: {n_orders} đơn")
    print(f"Ngày đơn cuối: {last_date_str[:10] if last_date_str != 'N/A' else 'N/A'} (cần = 25/03/2026)")
    print(f"Ngày im lặng: {silent_days} ngày (cần > 14)")
    print(f"Ticket phàn nàn: {'CÓ' if tg_tickets > 0 else 'KHÔNG'}")
    print(f"Activity follow-up quá hạn: {'CÓ' if has_overdue_activity else 'KHÔNG'}")

    last_ok = last_date == datetime.date(2026, 3, 25) if last_date else False
    if last_ok and silent_days > 14:
        print("→ PASS ✅")
        results["pass"] += 1
    else:
        print("→ FAIL ❌")
        results["fail"] += 1
        results["issues"].append(f"KB3: last={last_date}, silent={silent_days}d")

    # ── KẾT QUẢ ────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print("KẾT QUẢ")
    print("=" * 60)

    if results["fail"] == 0:
        print("SẴN SÀNG DEMO ✅")
    else:
        print(f"CẦN FIX ❌: {', '.join(results['issues'])}")

    print(f"Pass: {results['pass']}/3, Fail: {results['fail']}/3")
    print(f"Thời gian chạy reset: {elapsed:.0f} giây")


if __name__ == "__main__":
    main()
