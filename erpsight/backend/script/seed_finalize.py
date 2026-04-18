"""
Script 4 (finalize): Validate ALL pending sale-order delivery transfers +
re-apply inventory target quantities.

Run order (via reset_demo.py):
    seed_odoo          → products & partners
    seed_purchase_orders → PO receipts validated (2400 RAM + other products)
    seed_sale_orders   → 403 SOs confirmed (Jan 10 – Apr 10)
    seed_finalize      ← THIS script
    set_inventory_and_tickets → helpdesk tickets + final inventory reset

What it does:
  PRE. Temporarily boost ALL product inventories to 9999 so that action_assign
       can reserve stock for every DO regardless of PO qty vs SO demand gaps.
  A.  Collect every pending outgoing delivery (all dates).
  B.  Fix scheduled_date on each DO to match parent SO's date_order.
  C.  action_assign ALL pickings (now possible because stock = 9999).
  D.  Validate every assigned picking → all DOs become 'done'.
  E.  Re-apply real inventory targets (overrides the 9999 temp values).

After running, ALL products show:
  On Hand = target   Forecasted = target   In: 0   Out: 0
KB1 spike scenario is detected via SO sales velocity trend, not pending DOs.
"""

import xmlrpc.client
from datetime import datetime

URL = "http://educare-connect.me"
DB  = "erpsight"
USER = "admin"
PASS = "admin"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
uid    = common.authenticate(DB, USER, PASS, {})
if not uid:
    raise SystemExit("Xác thực thất bại.")
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)


def execute(model, method, args, kw=None):
    return models.execute_kw(DB, uid, PASS, model, method, args, kw or {})


# ── target inventory levels (same as set_inventory_and_tickets.py) ────────────
INVENTORY_TARGETS = {
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


def find_product_id(ref):
    recs = execute("product.product", "search_read",
                   [[("default_code", "=", ref)]], {"fields": ["id"], "limit": 1})
    return recs[0]["id"] if recs else None


def find_internal_location():
    locs = execute("stock.location", "search",
                   [[("usage", "=", "internal"), ("name", "ilike", "Stock")]])
    if not locs:
        raise SystemExit("Không tìm thấy WH/Stock location")
    return locs[0]


def validate_picking(pick_id, pick_name):
    """In Odoo 17, button_validate may return:
    - True (direct done) → picking is done ✅
    - confirm.stock.sms → SMS confirm wizard; call action_confirm to skip SMS
    - stock.backorder.confirmation → call process_cancel_backorder to no-backorder
    - stock.immediate.transfer → call process() (qty_done auto-set before this)
    Pass skip_sms=True in context to avoid the SMS wizard where possible."""
    try:
        result = execute("stock.picking", "button_validate", [[pick_id]],
                         {"context": {"skip_sms": True}})
        if isinstance(result, dict) and result.get("res_model"):
            wiz_model = result["res_model"]
            if wiz_model == "confirm.stock.sms":
                # SMS confirm wizard – proceed without SMS
                wiz_id = execute(wiz_model, "create",
                                 [{"picking_ids": [[6, 0, [pick_id]]]}])
                execute(wiz_model, "action_confirm", [[wiz_id]])
            elif wiz_model == "stock.backorder.confirmation":
                wiz_id = execute(wiz_model, "create",
                                 [{"pick_ids": [[6, 0, [pick_id]]]}])
                execute(wiz_model, "process_cancel_backorder", [[wiz_id]])
            elif wiz_model == "stock.immediate.transfer":
                wiz_id = execute(wiz_model, "create",
                                 [{"pick_ids": [[6, 0, [pick_id]]]}])
                execute(wiz_model, "process", [[wiz_id]])
        return True
    except Exception as exc:
        print(f"    ⚠️  {pick_name}: {exc}")
        return False


def apply_inventory_qty(prod_id, location_id, target_qty):
    """Set a product's on-hand in WH/Stock to target_qty via inventory adjustment."""
    quant_ids = execute("stock.quant", "search",
                        [[("product_id", "=", prod_id),
                          ("location_id", "=", location_id)]])
    if quant_ids:
        execute("stock.quant", "write", [quant_ids, {"inventory_quantity": target_qty}])
        quant_id = quant_ids[0]
    else:
        quant_id = execute("stock.quant", "create", [{
            "product_id": prod_id,
            "location_id": location_id,
            "inventory_quantity": target_qty,
        }])
    try:
        execute("stock.quant", "action_apply_inventory", [[quant_id]])
    except Exception:
        pass  # Odoo 17 returns None for void methods – xmlrpc raises Fault


def main():
    location_id = find_internal_location()

    # ─────────────────────────────────────────────────────────────────────────
    # PRE. Temporarily boost ALL product inventories to 9999 units.
    #      This lets action_assign reserve stock for EVERY pending DO
    #      even when PO qty < total SO demand (e.g. SSD-512: 400 PO vs 520 SOs).
    #      Real targets are restored in step E.
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== PRE. BOOST INVENTORY (temp 9999 để assign all DOs) ===")
    TEMP_QTY = 9999
    for ref in INVENTORY_TARGETS:
        prod_id = find_product_id(ref)
        if prod_id:
            apply_inventory_qty(prod_id, location_id, TEMP_QTY)
    print(f"  Boosted {len(INVENTORY_TARGETS)} products to {TEMP_QTY} units (tạm thời)")

    # ─────────────────────────────────────────────────────────────────────────
    # A. Collect ALL pending outgoing DOs (no date filter needed).
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== A. COLLECT ALL PENDING DELIVERIES ===")
    all_pending_picks = execute(
        "stock.picking", "search_read",
        [[("picking_type_code", "=", "outgoing"),
          ("state", "not in", ["done", "cancel"])]],
        {"fields": ["id", "name", "origin", "sale_id", "scheduled_date"]},
    )
    print(f"  Found {len(all_pending_picks)} pending delivery pickings")

    # ─────────────────────────────────────────────────────────────────────────
    # B. Fix scheduled_date on every DO to match the parent SO's date_order.
    #    (action_confirm resets scheduled_date to now; restore for cleanliness.)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== B. FIX DELIVERY SCHEDULED DATES ===")
    fixed = 0
    for pick in all_pending_picks:
        sale_id_val = pick.get("sale_id")
        if not sale_id_val or sale_id_val is False:
            continue
        sale_id = sale_id_val[0] if isinstance(sale_id_val, (list, tuple)) else sale_id_val
        so = execute("sale.order", "read", [[sale_id]], {"fields": ["date_order"]})
        if not so:
            continue
        date_order_str = str(so[0]["date_order"])[:16]  # "YYYY-MM-DD HH:MM"
        execute("stock.picking", "write", [[pick["id"]], {"scheduled_date": date_order_str + ":00"}])
        fixed += 1
    print(f"  Fixed scheduled_date for {fixed} pickings")

    # ─────────────────────────────────────────────────────────────────────────
    # C. Reserve stock for ALL pickings (action_assign in batches).
    #    All should fully assign because inventory was boosted to 9999.
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== C. RESERVE STOCK (action_assign) ===")
    pick_ids_all = [p["id"] for p in all_pending_picks]
    BATCH = 50
    for i in range(0, len(pick_ids_all), BATCH):
        batch = pick_ids_all[i:i + BATCH]
        try:
            execute("stock.picking", "action_assign", [batch])
        except Exception as exc:
            print(f"  ⚠️  batch {i//BATCH + 1} assign error: {exc}")
    print(f"  action_assign done on {len(pick_ids_all)} pickings")

    assigned_picks = execute(
        "stock.picking", "search_read",
        [["&", ("id", "in", pick_ids_all), ("state", "=", "assigned")]],
        {"fields": ["id", "name"]},
    )
    still_pending = len(pick_ids_all) - len(assigned_picks)
    print(f"  {len(assigned_picks)} assigned  |  {still_pending} still not assigned")

    # ─────────────────────────────────────────────────────────────────────────
    # D. Validate ALL assigned deliveries → all DOs become 'done'.
    #    After this: outgoing_qty = 0 for every product.
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== D. VALIDATE ALL DELIVERIES ===")
    ok = 0
    skip = 0
    for pick in assigned_picks:
        success = validate_picking(pick["id"], pick["name"])
        if success:
            ok += 1
        else:
            skip += 1
        if (ok + skip) % 50 == 0:
            print(f"  ... {ok + skip}/{len(assigned_picks)} processed")
    print(f"  Validated: {ok}   Skipped/failed: {skip}")

    # ─────────────────────────────────────────────────────────────────────────
    # E. Re-apply REAL inventory targets (replaces the 9999 temp values).
    #    After this: on_hand = target, In: 0, Out: 0, Forecasted = target.
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== E. RE-APPLY INVENTORY TARGETS ===")
    for ref, target_qty in INVENTORY_TARGETS.items():
        prod_id = find_product_id(ref)
        if not prod_id:
            print(f"  [skip] {ref}")
            continue
        apply_inventory_qty(prod_id, location_id, target_qty)
        print(f"  ✅ {ref}: {target_qty}")

    # ─────────────────────────────────────────────────────────────────────────
    # F. Final verification for RAM-DDR5-16-KS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n=== F. VERIFICATION: RAM-DDR5-16-KS ===")
    ram_id = find_product_id("RAM-DDR5-16-KS")
    if ram_id:
        prod = execute("product.product", "read", [[ram_id]],
                       {"fields": ["qty_available", "virtual_available",
                                   "incoming_qty", "outgoing_qty"]})[0]
        print(f"  On Hand (qty_available)  = {prod['qty_available']}")
        print(f"  Forecasted (virtual)     = {prod['virtual_available']}")
        print(f"  Incoming (unvalidated In)= {prod['incoming_qty']}")
        print(f"  Outgoing (pending Out)   = {prod['outgoing_qty']}")
        if prod["incoming_qty"] == 0 and prod["outgoing_qty"] == 0:
            print("  ✅ In: 0 / Out: 0 – KB1 scenario ready")
        else:
            print("  ⚠️  Some moves still pending – check manually")

    # PO states
    po_lines = execute("purchase.order.line", "search_read",
                       [[("product_id", "=", ram_id)]],
                       {"fields": ["order_id", "product_qty", "price_unit"]})
    for l in po_lines:
        po = execute("purchase.order", "read", [[l["order_id"][0]]],
                     {"fields": ["name", "state", "date_order"]})[0]
        print(f"  PO {po['name']}  state={po['state']}  date={str(po['date_order'])[:10]}"
              f"  qty={l['product_qty']}  price={l['price_unit']:.0f}")


if __name__ == "__main__":
    main()
