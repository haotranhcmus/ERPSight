#!/usr/bin/env python3
"""
Final validation: pull ALL data through adapters + mappers, report any errors.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "erpsight"))

from backend.config.logging_config import setup_logging
setup_logging("WARNING")  # quiet

from backend.adapters.odoo_client import OdooClient
from backend.adapters.order_mapper import map_orders
from backend.adapters.inventory_mapper import map_inventories
from backend.adapters.purchase_mapper import map_supplier_orders
from backend.adapters.ticket_mapper import map_tickets
from backend.adapters.transaction_mapper import map_transactions

errors = []

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ── Connect ──
section("1. AUTHENTICATION")
client = OdooClient()
try:
    uid = client.authenticate()
    ver = client.get_server_version()
    print(f"  [OK] uid={uid}, server={ver.get('server_version')}")
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

# ── Sale Orders ──
section("2. SALE ORDERS + lines + margin")
try:
    raw_orders = client.get_sale_orders(limit=10)
    oids = [o["id"] for o in raw_orders]
    raw_lines = client.get_sale_order_lines(oids)
    cost_map = client.get_product_cost_map()
    orders = map_orders(raw_orders, raw_lines, cost_map)
    print(f"  [OK] {len(orders)} orders, {sum(len(o.lines) for o in orders)} lines")
    for o in orders[:3]:
        print(f"    {o.name} | {o.partner_name} | {o.amount_total:,.0f} VND | {len(o.lines)} lines | state={o.state}")
        for l in o.lines[:2]:
            print(f"      {l.product_name}: qty={l.quantity} price={l.price_unit:,.0f} cost={l.cost_price:,.0f} margin={l.margin_pct:.1%}")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"sale orders: {e}")

# ── Inventory ──
section("3. INVENTORY (stock.quant)")
try:
    raw_quants = client.get_stock_quants()
    inventories = map_inventories(raw_quants)
    print(f"  [OK] {len(inventories)} quants")
    for inv in inventories:
        print(f"    {inv.product_name}: on_hand={inv.qty_on_hand:.0f} reserved={inv.reserved_quantity:.0f} available={inv.available_qty:.0f} | {inv.location_name}")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"inventory: {e}")

# ── Purchase Orders ──
section("4. PURCHASE ORDERS + lines")
try:
    raw_pos = client.get_purchase_orders(limit=10)
    po_ids = [p["id"] for p in raw_pos]
    raw_po_lines = client.get_purchase_order_lines(po_ids)
    pos = map_supplier_orders(raw_pos, raw_po_lines)
    print(f"  [OK] {len(pos)} POs, {sum(len(p.lines) for p in pos)} lines")
    for p in pos[:3]:
        print(f"    {p.name} | {p.partner_name} | {p.amount_total:,.0f} VND | state={p.state}")
        for l in p.lines[:2]:
            print(f"      {l.product_name}: qty={l.quantity:.0f} price={l.price_unit:,.0f}")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"purchase orders: {e}")

# ── Helpdesk Tickets ──
section("5. HELPDESK TICKETS")
try:
    raw_tickets = client.get_helpdesk_tickets(limit=10)
    tickets = map_tickets(raw_tickets)
    print(f"  [OK] {len(tickets)} tickets")
    for t in tickets:
        print(f"    #{t.ticket_id} {t.name}")
        print(f"      stage={t.stage_name} closed={t.closed} closed_date={t.closed_date}")
        print(f"      resolution_days={t.resolution_days} last_stage_update={t.last_stage_update}")
        print(f"      partner={t.partner_name or '(none)'} priority={t.priority}")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"helpdesk: {e}")

# ── Invoices ──
section("6. INVOICES (account.move)")
try:
    raw_invoices = client.get_invoices(limit=5)
    if raw_invoices:
        inv_ids = [i["id"] for i in raw_invoices]
        raw_inv_lines = client.get_invoice_lines(inv_ids)
        transactions = map_transactions(raw_invoices, raw_inv_lines, cost_map)
        print(f"  [OK] {len(transactions)} invoices")
        for t in transactions[:2]:
            print(f"    {t.name} | {t.amount_total:,.0f} VND | type={t.move_type} | margin={t.avg_margin_pct:.1%}")
    else:
        print(f"  [OK] 0 posted invoices (expected — no invoices in system yet)")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"invoices: {e}")

# ── Products ──
section("7. PRODUCTS")
try:
    products = client.get_products()
    print(f"  [OK] {len(products)} products")
    for p in products:
        print(f"    [{p['id']}] {p['name']}: cost={p['standard_price']:,.0f} list={p['list_price']:,.0f}")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"products: {e}")

# ── Partners ──
section("8. PARTNERS (sample)")
try:
    partners = client.get_partners([1, 2, 3])
    print(f"  [OK] {len(partners)} partners")
    for p in partners:
        print(f"    [{p['id']}] {p['name']} | email={p.get('email', 'N/A')}")
except Exception as e:
    import traceback; traceback.print_exc()
    errors.append(f"partners: {e}")

# ── Whitelist.json ──
section("9. WHITELIST CONFIG")
try:
    wl_path = os.path.join(os.path.dirname(__file__), "..", "erpsight", "backend", "config", "whitelist.json")
    with open(wl_path) as f:
        wl = json.load(f)
    print(f"  [OK] {len(wl)} actions defined: {list(wl.keys())}")
except Exception as e:
    errors.append(f"whitelist: {e}")
    print(f"  [FAIL] {e}")

# ── __init__.py integrity ──
section("10. __init__.py INTEGRITY CHECK")
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
    "scripts/__init__.py",
    "scripts/seed_data/__init__.py",
]
base = os.path.join(os.path.dirname(__file__), "..")
all_ok = True
for init in init_files:
    fpath = os.path.join(base, init)
    if not os.path.exists(fpath):
        print(f"  [MISS] {init}")
        errors.append(f"missing {init}")
        all_ok = False
    else:
        size = os.path.getsize(fpath)
        if size > 10:  # Should be empty or near-empty
            with open(fpath) as f:
                content = f.read(200)
            print(f"  [BAD]  {init} — {size} bytes, content: {content[:80]!r}")
            errors.append(f"corrupted {init} ({size} bytes)")
            all_ok = False
        else:
            print(f"  [OK]   {init}")
if all_ok:
    print("  All __init__.py files are clean.")

# ── Summary ──
section("FINAL RESULT")
if errors:
    print(f"  {len(errors)} ERRORS:")
    for e in errors:
        print(f"    - {e}")
else:
    print("  ALL TESTS PASSED — Adapter layer is fully operational.")
