#!/usr/bin/env python3
"""
tests/test_all.py

Bộ test toàn diện cho ERPSight adapter layer.
Bao phủ tất cả 24 hàm public trong OdooClient + 5 mapper functions.

Chạy từ thư mục root ERPSight/:
    python3 tests/test_all.py

Hoặc section cụ thể (dựa vào số section để xem output):
    python3 tests/test_all.py 2>/dev/null

Kết quả:
    [OK]   — passed
    [FAIL] — lỗi cần xem lại
    [SKIP] — bỏ qua (ví dụ: không có data để test)
    [INFO] — thông tin bổ sung, không phải lỗi
"""

import sys
import os
import json
from datetime import date, timedelta

# Path resolution: tests/ → .. → ERPSight root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from erpsight.backend.config.logging_config import setup_logging
setup_logging("WARNING")   # tắt INFO logs trong quá trình test

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.adapters.order_mapper import map_orders
from erpsight.backend.adapters.inventory_mapper import map_inventories
from erpsight.backend.adapters.purchase_mapper import map_supplier_orders
from erpsight.backend.adapters.ticket_mapper import map_tickets
from erpsight.backend.adapters.transaction_mapper import map_transactions

# ── Helpers ────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
RESET  = "\033[0m"

errors: list[str] = []

def section(num: int, title: str) -> None:
    print(f"\n{CYAN}{'═' * 62}{RESET}")
    print(f"{CYAN}  {num:02d}. {title}{RESET}")
    print(f"{CYAN}{'═' * 62}{RESET}")

def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET}   {msg}")

def fail(label: str, exc: Exception) -> None:
    import traceback
    print(f"  {RED}[FAIL]{RESET} {label}: {exc}")
    traceback.print_exc()
    errors.append(f"{label}: {exc}")

def skip(msg: str) -> None:
    print(f"  {YELLOW}[SKIP]{RESET} {msg}")

def info(msg: str) -> None:
    print(f"  {DIM}[INFO]{RESET} {msg}")

# ── Init client (shared across all tests) ─────────────────────────────────────

client = OdooClient()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 01 — authenticate() + check_connection() + get_server_version()
# ══════════════════════════════════════════════════════════════════════════════
section(1, "AUTHENTICATION + CONNECTION")
try:
    uid = client.authenticate()
    ver = client.get_server_version()
    ok(f"authenticate() → uid={uid}, server={ver.get('server_version')}")
except Exception as e:
    fail("authenticate", e)
    print(f"\n{RED}  Cannot connect to Odoo — aborting all tests.{RESET}")
    sys.exit(1)

try:
    alive = client.check_connection()
    ok(f"check_connection() → {alive}")
except Exception as e:
    fail("check_connection", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 02 — count()
# Kiểm tra đếm record không kéo data về
# ══════════════════════════════════════════════════════════════════════════════
section(2, "count() — đếm record theo domain")
try:
    n_so     = client.count("sale.order",      [("state", "in", ["sale", "done"])])
    n_po     = client.count("purchase.order",  [("state", "not in", ["cancel"])])
    n_quant  = client.count("stock.quant",     [("quantity", ">", 0)])
    n_ticket = client.count("helpdesk.ticket", [])
    n_inv    = client.count("account.move",    [("state", "=", "posted")])
    ok(f"sale.order       (confirmed): {n_so}")
    ok(f"purchase.order   (not cancel): {n_po}")
    ok(f"stock.quant      (qty > 0): {n_quant}")
    ok(f"helpdesk.ticket  (all): {n_ticket}")
    ok(f"account.move     (posted): {n_inv}")
except Exception as e:
    fail("count", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 03 — get_sale_orders() + get_sale_order_lines()
# ══════════════════════════════════════════════════════════════════════════════
section(3, "get_sale_orders() + get_sale_order_lines()")
raw_orders: list = []
raw_lines:  list = []
cost_map:   dict = {}

try:
    raw_orders = client.get_sale_orders(limit=10)
    ok(f"get_sale_orders(limit=10) → {len(raw_orders)} records")
    if raw_orders:
        sample = raw_orders[0]
        info(f"Sample keys: {list(sample.keys())}")
        info(f"Sample: {sample['name']} | partner={sample['partner_id']} | state={sample['state']}")
except Exception as e:
    fail("get_sale_orders", e)

try:
    oids = [o["id"] for o in raw_orders]
    raw_lines = client.get_sale_order_lines(oids)
    ok(f"get_sale_order_lines({len(oids)} ids) → {len(raw_lines)} lines")
    if raw_lines:
        l = raw_lines[0]
        info(f"Sample line: product={l.get('product_id')} qty={l.get('product_uom_qty')} price={l.get('price_unit')}")
except Exception as e:
    fail("get_sale_order_lines", e)

try:
    # Test empty input — should return [] without hitting Odoo
    empty_result = client.get_sale_order_lines([])
    assert empty_result == [], "Expected [] for empty input"
    ok("get_sale_order_lines([]) → [] (fast return, no RPC)")
except Exception as e:
    fail("get_sale_order_lines empty guard", e)

try:
    # Test date filter
    date_from = (date.today() - timedelta(days=365)).isoformat()
    filtered = client.get_sale_orders(date_from=date_from, limit=5)
    ok(f"get_sale_orders(date_from='{date_from}') → {len(filtered)} records")
except Exception as e:
    fail("get_sale_orders with date_from", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 04 — get_product_cost_map() + get_products()
# ══════════════════════════════════════════════════════════════════════════════
section(4, "get_products() + get_product_cost_map()")
try:
    products = client.get_products()
    ok(f"get_products() → {len(products)} products")
    for p in products[:3]:
        info(f"  [{p['id']}] {p['name']}: cost={p['standard_price']:,.0f} list={p['list_price']:,.0f}")
except Exception as e:
    fail("get_products", e)

try:
    cost_map = client.get_product_cost_map()
    ok(f"get_product_cost_map() → {len(cost_map)} entries")
    sample_items = list(cost_map.items())[:3]
    for pid, cost in sample_items:
        info(f"  product_id={pid} → standard_price={cost:,.0f}")
    assert all(isinstance(k, int) for k in cost_map), "Keys must be int"
    assert all(isinstance(v, float) for v in cost_map.values()), "Values must be float"
    ok("cost_map type check: {int: float} ✓")
except Exception as e:
    fail("get_product_cost_map", e)

try:
    # Test filtering by specific product_ids
    if products:
        ids = [p["id"] for p in products[:2]]
        filtered = client.get_products(product_ids=ids)
        assert len(filtered) <= 2
        ok(f"get_products(product_ids={ids}) → {len(filtered)} records")
        filtered_map = client.get_product_cost_map(product_ids=ids)
        ok(f"get_product_cost_map(product_ids={ids}) → {len(filtered_map)} entries")
except Exception as e:
    fail("get_products with product_ids filter", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 05 — map_orders() (order_mapper)
# ══════════════════════════════════════════════════════════════════════════════
section(5, "map_orders() — order_mapper")
orders = []
try:
    orders = map_orders(raw_orders, raw_lines, cost_map)
    ok(f"map_orders() → {len(orders)} Order objects, {sum(len(o.lines) for o in orders)} OrderLines")
    for o in orders[:3]:
        info(f"  {o.name} | {o.partner_name} | {o.amount_total:,.0f} VND | state={o.state} | {len(o.lines)} lines")
        for l in o.lines[:2]:
            info(f"    └ {l.product_name}: qty={l.quantity:.0f} margin={l.margin_pct:.1%} cost={l.cost_price:,.0f}")
    # Validate types
    if orders:
        o = orders[0]
        assert isinstance(o.order_id, int)
        assert isinstance(o.amount_total, float)
        assert isinstance(o.lines, list)
        ok("Field type assertions passed (order_id: int, amount_total: float, lines: list)")
except Exception as e:
    fail("map_orders", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 06 — get_stock_quants() + get_all_stock_quants()
# ══════════════════════════════════════════════════════════════════════════════
section(6, "get_stock_quants() + get_all_stock_quants()")
raw_quants: list = []
try:
    raw_quants = client.get_stock_quants()
    ok(f"get_stock_quants() → {len(raw_quants)} quants (qty > 0, internal only)")
    if raw_quants:
        q = raw_quants[0]
        info(f"Sample: {q.get('product_id')} qty={q.get('quantity')} reserved={q.get('reserved_quantity')}")
        assert "quantity" in q, "Field 'quantity' must exist (Odoo 17 name)"
        ok("Field name check: 'quantity' present ✓ (not qty_on_hand)")
except Exception as e:
    fail("get_stock_quants", e)

try:
    all_quants = client.get_all_stock_quants()
    ok(f"get_all_stock_quants() → {len(all_quants)} quants (includes qty=0)")
    info(f"  Difference: {len(all_quants) - len(raw_quants)} records with qty ≤ 0")
except Exception as e:
    fail("get_all_stock_quants", e)

try:
    # Test with product_ids filter
    if products:
        pids = [p["id"] for p in products[:3]]
        filtered = client.get_stock_quants(product_ids=pids)
        ok(f"get_stock_quants(product_ids={pids}) → {len(filtered)} quants")
except Exception as e:
    fail("get_stock_quants with product_ids", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 07 — map_inventories() (inventory_mapper)
# ══════════════════════════════════════════════════════════════════════════════
section(7, "map_inventories() — inventory_mapper")
inventories = []
try:
    inventories = map_inventories(raw_quants)
    ok(f"map_inventories() → {len(inventories)} Inventory objects")
    for inv in inventories:
        status = f"{RED}ZERO{RESET}" if inv.available_qty == 0 else "has stock"
        info(f"  {inv.product_name}: on_hand={inv.qty_on_hand:.0f} reserved={inv.reserved_quantity:.0f} available={inv.available_qty:.0f} [{status}]")
    if inventories:
        inv = inventories[0]
        assert inv.avg_daily_sales == 0.0, "avg_daily_sales must default to 0.0 (SentinelAgent fills this)"
        assert inv.days_of_stock_remaining is None, "days_of_stock_remaining must default to None"
        ok("Default values: avg_daily_sales=0.0, days_of_stock_remaining=None ✓")
        # Simulate SentinelAgent filling derived fields
        inv.avg_daily_sales = 3.5
        inv.days_of_stock_remaining = inv.available_qty / inv.avg_daily_sales if inv.avg_daily_sales > 0 else None
        ok(f"Derived field simulation: days_of_stock_remaining={inv.days_of_stock_remaining}")
except Exception as e:
    fail("map_inventories", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 08 — get_purchase_orders() + get_purchase_order_lines()
# ══════════════════════════════════════════════════════════════════════════════
section(8, "get_purchase_orders() + get_purchase_order_lines()")
raw_pos: list = []
raw_po_lines: list = []
try:
    raw_pos = client.get_purchase_orders(limit=10)
    ok(f"get_purchase_orders(limit=10) → {len(raw_pos)} POs")
    if raw_pos:
        p = raw_pos[0]
        info(f"Sample: {p['name']} | partner={p['partner_id']} | state={p['state']}")
except Exception as e:
    fail("get_purchase_orders", e)

try:
    po_ids = [p["id"] for p in raw_pos]
    raw_po_lines = client.get_purchase_order_lines(po_ids)
    ok(f"get_purchase_order_lines({len(po_ids)} ids) → {len(raw_po_lines)} lines")
    if raw_po_lines:
        l = raw_po_lines[0]
        info(f"Sample line: product={l.get('product_id')} qty={l.get('product_qty')} date_planned={l.get('date_planned')}")
except Exception as e:
    fail("get_purchase_order_lines", e)

try:
    empty_result = client.get_purchase_order_lines([])
    assert empty_result == []
    ok("get_purchase_order_lines([]) → [] (fast return, no RPC)")
except Exception as e:
    fail("get_purchase_order_lines empty guard", e)

try:
    # Test state filter
    confirmed = client.get_purchase_orders(states=["purchase", "done"])
    ok(f"get_purchase_orders(states=['purchase','done']) → {len(confirmed)} confirmed POs")
except Exception as e:
    fail("get_purchase_orders with states filter", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 09 — map_supplier_orders() (purchase_mapper)
# ══════════════════════════════════════════════════════════════════════════════
section(9, "map_supplier_orders() — purchase_mapper")
pos = []
try:
    pos = map_supplier_orders(raw_pos, raw_po_lines)
    ok(f"map_supplier_orders() → {len(pos)} SupplierOrder objects, {sum(len(p.lines) for p in pos)} POLines")
    for p in pos[:3]:
        info(f"  {p.name} | {p.partner_name} | {p.amount_total:,.0f} VND | state={p.state}")
        for l in p.lines[:2]:
            overdue = l.date_planned and l.date_planned.date() < date.today()
            info(f"    └ {l.product_name}: qty={l.quantity:.0f} price={l.price_unit:,.0f} planned={l.date_planned} {'⚠ OVERDUE' if overdue else ''}")
    if pos:
        assert isinstance(pos[0].po_id, int)
        assert isinstance(pos[0].lines, list)
        ok("Type assertions passed ✓")
except Exception as e:
    fail("map_supplier_orders", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — get_helpdesk_tickets()
# ══════════════════════════════════════════════════════════════════════════════
section(10, "get_helpdesk_tickets()")
raw_tickets: list = []
try:
    raw_tickets = client.get_helpdesk_tickets(limit=10)
    ok(f"get_helpdesk_tickets(limit=10) → {len(raw_tickets)} tickets")
    if raw_tickets:
        t = raw_tickets[0]
        info(f"Sample keys: {list(t.keys())}")
        info(f"Sample: #{t['id']} {t['name']} | priority={t.get('priority')} | closed={t.get('closed')}")
        assert "closed" in t, "Field 'closed' must exist (OCA helpdesk_mgmt v17)"
        assert "closed_date" in t, "Field 'closed_date' must exist"
        assert "last_stage_update" in t, "Field 'last_stage_update' must exist"
        ok("OCA field check: closed, closed_date, last_stage_update present ✓")
except Exception as e:
    fail("get_helpdesk_tickets", e)

try:
    # Test date + partner filter (should not error even if no results)
    filtered = client.get_helpdesk_tickets(date_from="2026-01-01", limit=3)
    ok(f"get_helpdesk_tickets(date_from='2026-01-01') → {len(filtered)} tickets")
except Exception as e:
    fail("get_helpdesk_tickets with date filter", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — map_tickets() (ticket_mapper) + resolution_days logic
# ══════════════════════════════════════════════════════════════════════════════
section(11, "map_tickets() — ticket_mapper + resolution_days logic")
tickets = []
try:
    tickets = map_tickets(raw_tickets)
    ok(f"map_tickets() → {len(tickets)} CustomerTicket objects")
    for t in tickets:
        info(f"  #{t.ticket_id} [{t.priority}] {t.name}")
        info(f"    stage={t.stage_name} closed={t.closed} resolution_days={t.resolution_days}")
        info(f"    closed_date={t.closed_date} last_stage_update={t.last_stage_update}")
    # Verify resolution_days logic
    for t in tickets:
        if t.closed and t.closed_date:
            # Method 1: closed_date available
            expected = (t.closed_date - t.create_date).total_seconds() / 86400
            assert abs((t.resolution_days or 0) - round(expected, 2)) < 0.01, \
                f"resolution_days mismatch for ticket #{t.ticket_id}"
        elif t.closed and not t.closed_date and t.last_stage_update:
            # Method 2: fallback to last_stage_update (OCA bug workaround)
            assert t.resolution_days is not None, \
                f"resolution_days should use last_stage_update for ticket #{t.ticket_id}"
    ok("resolution_days logic correct (closed_date → last_stage_update fallback) ✓")
    # Priority value check
    for t in tickets:
        assert t.priority in {"0", "1", "2", "3"}, f"Invalid priority: {t.priority}"
    ok("Priority values all valid ('0' | '1' | '2' | '3') ✓")
except Exception as e:
    fail("map_tickets", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — get_invoices() + get_invoice_lines()
# ══════════════════════════════════════════════════════════════════════════════
section(12, "get_invoices() + get_invoice_lines()")
raw_invoices: list = []
raw_inv_lines: list = []
try:
    raw_invoices = client.get_invoices(limit=10)
    if raw_invoices:
        ok(f"get_invoices(limit=10) → {len(raw_invoices)} posted invoices")
        inv = raw_invoices[0]
        info(f"Sample: {inv['name']} | type={inv['move_type']} | {inv['invoice_date']} | total={inv['amount_total']}")
    else:
        ok("get_invoices() → 0 posted invoices (no posted invoices in system yet)")
except Exception as e:
    fail("get_invoices", e)

try:
    raw_invoices_vendor = client.get_invoices(move_types=["in_invoice"], limit=5)
    ok(f"get_invoices(move_types=['in_invoice']) → {len(raw_invoices_vendor)} vendor bills")
except Exception as e:
    fail("get_invoices with move_types filter", e)

try:
    inv_ids = [inv["id"] for inv in raw_invoices]
    raw_inv_lines = client.get_invoice_lines(inv_ids)
    ok(f"get_invoice_lines({len(inv_ids)} ids) → {len(raw_inv_lines)} product lines (tax/section lines excluded)")
except Exception as e:
    fail("get_invoice_lines", e)

try:
    empty_result = client.get_invoice_lines([])
    assert empty_result == []
    ok("get_invoice_lines([]) → [] (fast return, no RPC)")
except Exception as e:
    fail("get_invoice_lines empty guard", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — map_transactions() (transaction_mapper)
# ══════════════════════════════════════════════════════════════════════════════
section(13, "map_transactions() — transaction_mapper")
transactions = []
try:
    transactions = map_transactions(raw_invoices, raw_inv_lines, cost_map)
    if transactions:
        ok(f"map_transactions() → {len(transactions)} Transaction objects, "
           f"{sum(len(t.lines) for t in transactions)} InvoiceLines")
        for t in transactions[:2]:
            info(f"  {t.name} | type={t.move_type} | {t.amount_total:,.0f} VND | avg_margin={t.avg_margin_pct:.1%}")
        # Check weighted avg margin
        if transactions and transactions[0].lines:
            t = transactions[0]
            total_rev = sum(l.price_subtotal for l in t.lines)
            total_cost = sum(l.cost_price * l.quantity for l in t.lines)
            expected_margin = (total_rev - total_cost) / total_rev if total_rev > 0 else 0.0
            assert abs(t.avg_margin_pct - round(expected_margin, 4)) < 0.001, "avg_margin_pct calculation wrong"
            ok("avg_margin_pct weighted average calculation correct ✓")
    else:
        ok("map_transactions() → 0 transactions (no posted invoices; NOT a bug)")
        info("avg_margin_pct = 0.0 expected when no invoices")
except Exception as e:
    fail("map_transactions", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — get_partners()
# ══════════════════════════════════════════════════════════════════════════════
section(14, "get_partners()")
try:
    partners = client.get_partners([1, 2, 3])
    ok(f"get_partners([1, 2, 3]) → {len(partners)} partners")
    for p in partners:
        info(f"  [{p['id']}] {p['name']} | email={p.get('email') or 'N/A'} | customer_rank={p.get('customer_rank', 0)}")
except Exception as e:
    fail("get_partners", e)

try:
    empty_result = client.get_partners([])
    assert empty_result == []
    ok("get_partners([]) → [] (fast return, no RPC)")
except Exception as e:
    fail("get_partners empty guard", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 15 — make_idempotency_key() (static helper)
# ══════════════════════════════════════════════════════════════════════════════
section(15, "make_idempotency_key() — idempotency helper")
try:
    key1 = OdooClient.make_idempotency_key("create_draft_po", {"partner_id": 17, "product_id": 3})
    key2 = OdooClient.make_idempotency_key("create_draft_po", {"product_id": 3, "partner_id": 17})  # different order
    key3 = OdooClient.make_idempotency_key("create_draft_po", {"partner_id": 99, "product_id": 3})  # different value
    assert key1 == key2, "Keys must be equal regardless of param order (sort_keys=True)"
    assert key1 != key3, "Keys must differ for different param values"
    assert len(key1) == 32, "Key must be 32 hex chars (sha256[:32])"
    ok(f"make_idempotency_key() correct: key1=key2={key1!r}")
    ok("Different params → different key ✓")
    ok("Key length = 32 chars ✓")
except Exception as e:
    fail("make_idempotency_key", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 16 — post_chatter_message() [WRITE — low risk]
# ══════════════════════════════════════════════════════════════════════════════
section(16, "post_chatter_message() — WRITE (low risk, internal note)")
try:
    # Cần một sale.order hoặc purchase.order để ghi note lên
    if raw_orders:
        target_so_id = raw_orders[0]["id"]
        target_so_name = raw_orders[0]["name"]
        msg_id = client.post_chatter_message(
            model="sale.order",
            res_id=target_so_id,
            message="<b>[ERPSight Test]</b> Kiểm tra post_chatter_message() — internal note, an toàn để xóa.",
            subtype_xmlid="mail.mt_note",
        )
        assert isinstance(msg_id, int) and msg_id > 0
        ok(f"post_chatter_message() → msg_id={msg_id} trên {target_so_name} (SO#{target_so_id})")
        info("Note: Message đã được ghi vào Odoo. Có thể xóa thủ công trong chatter nếu cần.")
    elif raw_pos:
        target_po_id = raw_pos[0]["id"]
        msg_id = client.post_chatter_message(
            model="purchase.order",
            res_id=target_po_id,
            message="<b>[ERPSight Test]</b> Kiểm tra post_chatter_message() — internal note.",
        )
        ok(f"post_chatter_message() → msg_id={msg_id} trên PO#{target_po_id}")
    else:
        skip("post_chatter_message — không có sale.order hoặc purchase.order để test")
except Exception as e:
    fail("post_chatter_message", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 17 — create_activity() + delete_activity() [WRITE — low risk, reversible]
# ══════════════════════════════════════════════════════════════════════════════
section(17, "create_activity() + delete_activity() — WRITE (reversible)")
activity_id: int | None = None
try:
    if raw_orders:
        target_id = raw_orders[0]["id"]
        deadline = (date.today() + timedelta(days=1)).isoformat()
        activity_id = client.create_activity(
            model="sale.order",
            res_id=target_id,
            summary="[ERPSight Test] Kiểm tra create_activity",
            note="<p>Activity này được tạo bởi test_all.py — sẽ bị xóa ngay sau đây.</p>",
            date_deadline=deadline,
        )
        assert isinstance(activity_id, int) and activity_id > 0
        ok(f"create_activity() → activity_id={activity_id} trên sale.order#{target_id} deadline={deadline}")
    elif raw_pos:
        target_id = raw_pos[0]["id"]
        activity_id = client.create_activity(
            model="purchase.order",
            res_id=target_id,
            summary="[ERPSight Test] Kiểm tra create_activity",
            note="<p>Test activity — sẽ bị xóa ngay sau đây.</p>",
        )
        ok(f"create_activity() → activity_id={activity_id} trên purchase.order#{target_id}")
    else:
        skip("create_activity — không có record để test")
except Exception as e:
    fail("create_activity", e)

try:
    if activity_id:
        success = client.delete_activity(activity_id)
        assert success is True
        ok(f"delete_activity({activity_id}) → True (activity đã bị xóa — undo thành công)")
    elif activity_id is None and raw_orders:
        skip("delete_activity — create_activity đã thất bại, bỏ qua")
    else:
        skip("delete_activity — không có activity để xóa")
except Exception as e:
    fail("delete_activity", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 18 — create_draft_purchase_order() + cancel_purchase_order() [WRITE — medium risk]
# ══════════════════════════════════════════════════════════════════════════════
section(18, "create_draft_purchase_order() + cancel_purchase_order() — WRITE (medium risk, reversible)")

# Lấy partner và product đầu tiên có sẵn
test_partner_id: int | None = None
test_product_id: int | None = None

try:
    # Tìm nhà cung cấp (vendor): customer_rank=0 thường là vendor/contact
    vendors = client.search_read("res.partner", [("active", "=", True)], ["id", "name", "customer_rank"], limit=5)
    if vendors:
        test_partner_id = vendors[0]["id"]
        info(f"Test vendor: [{test_partner_id}] {vendors[0]['name']}")
    if products:
        test_product_id = products[0]["id"]
        info(f"Test product: [{test_product_id}] {products[0]['name']}")
except Exception as e:
    info(f"Could not resolve test partner/product: {e}")

created_po_id: int | None = None
try:
    if test_partner_id and test_product_id:
        result = client.create_draft_purchase_order(
            partner_id=test_partner_id,
            order_lines=[{
                "product_id": test_product_id,
                "qty": 5.0,
                "price_unit": 100000.0,
                "name": "[ERPSight Test] Đơn test — xóa ngay",
                "date_planned": (date.today() + timedelta(days=7)).isoformat(),
            }],
            notes="Test tạo Draft PO từ test_all.py — sẽ bị hủy ngay sau đây",
        )
        assert "record_id" in result
        assert "idempotency_key" in result
        assert result["skipped"] is False
        created_po_id = result["record_id"]
        ok(f"create_draft_purchase_order() → record_id={created_po_id}, skipped={result['skipped']}")
        ok(f"idempotency_key={result['idempotency_key']!r}")

        # Test idempotency: gọi lại với cùng key → phải trả về record cũ
        result2 = client.create_draft_purchase_order(
            partner_id=test_partner_id,
            order_lines=[{
                "product_id": test_product_id,
                "qty": 5.0,
                "price_unit": 100000.0,
            }],
            idempotency_key=result["idempotency_key"],
        )
        assert result2["record_id"] == created_po_id
        assert result2["skipped"] is True
        ok(f"Idempotency test: gọi lại cùng key → skipped=True, same record_id={result2['record_id']} ✓")
    else:
        skip("create_draft_purchase_order — không tìm được partner hoặc product")
except Exception as e:
    fail("create_draft_purchase_order", e)

try:
    if created_po_id:
        success = client.cancel_purchase_order(created_po_id)
        assert success is True
        ok(f"cancel_purchase_order({created_po_id}) → True (draft PO đã bị hủy/xóa — undo thành công)")
    else:
        skip("cancel_purchase_order — không có PO test để hủy")
except Exception as e:
    fail("cancel_purchase_order", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 19 — search_read() trực tiếp (raw execute_kw wrapper)
# ══════════════════════════════════════════════════════════════════════════════
section(19, "search_read() và execute_kw() — low-level wrappers")
try:
    # search_read với limit và order
    result = client.search_read(
        "sale.order",
        [("state", "in", ["sale", "done"])],
        ["id", "name", "date_order"],
        limit=3,
        order="date_order desc",
    )
    ok(f"search_read('sale.order') → {len(result)} records")
    for r in result:
        info(f"  {r['name']} | {r['date_order']}")
except Exception as e:
    fail("search_read", e)

try:
    # execute_kw trực tiếp: lấy version
    version = client.execute_kw("res.users", "read", [[uid], ], {"fields": ["name", "login"]})
    ok(f"execute_kw('res.users', 'read', [[{uid}]]) → name={version[0]['name']}, login={version[0]['login']}")
except Exception as e:
    fail("execute_kw direct call", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 20 — whitelist.json integrity check
# ══════════════════════════════════════════════════════════════════════════════
section(20, "whitelist.json — config integrity")
try:
    wl_path = os.path.join(
        os.path.dirname(__file__), "..", "erpsight", "backend", "config", "whitelist.json"
    )
    with open(wl_path, encoding="utf-8") as f:
        wl = json.load(f)
    # whitelist.json structure: {action_name: {risk_level, reversible, ...}}
    action_types = list(wl.keys())
    expected = {"create_draft_po", "send_internal_alert", "create_activity_task"}
    assert expected == set(action_types), f"Mismatch: {expected.symmetric_difference(set(action_types))}"
    ok(f"whitelist.json loaded: {len(action_types)} actions defined")
    for action_type, details in wl.items():
        info(f"  {action_type}: risk={details['risk_level']} reversible={details['reversible']}")
    ok(f"All 3 required actions present: {sorted(action_types)}")
except Exception as e:
    fail("whitelist.json", e)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 21 — __init__.py integrity (tất cả module phải trống)
# ══════════════════════════════════════════════════════════════════════════════
section(21, "__init__.py integrity — tất cả module files phải trống (≤ 10 bytes)")
init_files = [
    "erpsight/backend/__init__.py",
    "erpsight/backend/adapters/__init__.py",
    "erpsight/backend/config/__init__.py",
    "erpsight/backend/models/__init__.py",
    "erpsight/backend/models/domain/__init__.py",
    "erpsight/backend/agents/__init__.py",
    "erpsight/backend/detectors/__init__.py",
    "erpsight/backend/executor/__init__.py",
    "erpsight/backend/memory/__init__.py",
    "erpsight/backend/services/__init__.py",
    "erpsight/backend/tools/__init__.py",
    "erpsight/backend/api/__init__.py",
    "erpsight/backend/api/routes/__init__.py",
]
base = os.path.join(os.path.dirname(__file__), "..")
all_ok = True
for init in init_files:
    fpath = os.path.join(base, init)
    if not os.path.exists(fpath):
        print(f"  {YELLOW}[MISS]{RESET}  {init}")
        errors.append(f"missing {init}")
        all_ok = False
    else:
        size = os.path.getsize(fpath)
        if size > 10:
            with open(fpath, encoding="utf-8") as f:
                content = f.read(80)
            print(f"  {RED}[BAD]{RESET}   {init} — {size} bytes: {content!r}")
            errors.append(f"corrupted {init} ({size} bytes)")
            all_ok = False
        else:
            print(f"  {GREEN}[OK]{RESET}    {init}")
if all_ok:
    ok("All __init__.py files are clean (empty) ✓")

# ══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
section(0, "FINAL SUMMARY")
if errors:
    print(f"\n  {RED}{'─' * 50}{RESET}")
    print(f"  {RED}FAILED — {len(errors)} error(s):{RESET}")
    for e in errors:
        print(f"    {RED}•{RESET} {e}")
    print(f"  {RED}{'─' * 50}{RESET}\n")
    sys.exit(1)
else:
    print(f"\n  {GREEN}{'─' * 50}{RESET}")
    print(f"  {GREEN}ALL TESTS PASSED{RESET} — Adapter layer fully operational.")
    print(f"  {GREEN}{'─' * 50}{RESET}\n")
