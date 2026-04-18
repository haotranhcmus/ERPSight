"""
One-off fix: remove the ~410 duplicated SOs that have date_order > 2026-04-10
(those are the first-run SOs whose date was set to server's "today" when confirmed
and were never properly deleted).
"""

import xmlrpc.client

URL = "http://educare-connect.me"
DB  = "erpsight"
USER = "admin"
PASS = "admin"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
uid    = common.authenticate(DB, USER, PASS, {})
if not uid:
    raise SystemExit("Auth failed")
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)


def execute(model, method, *args, **kwargs):
    call_args = list(args)
    if method in ("search", "search_read", "search_count") and call_args:
        d = call_args[0]
        if isinstance(d, list) and len(d) == 1 and isinstance(d[0], list):
            call_args[0] = d[0]
    return models.execute_kw(DB, uid, PASS, model, method, call_args, kwargs)


# ── Find old duplicate SOs (date_order after 2026-04-10) ───────────────────
old_ids = execute("sale.order", "search",
                  [[("date_order", ">", "2026-04-10 23:59:59")]])
print(f"Old SOs to remove: {len(old_ids)}")
if not old_ids:
    print("Nothing to do.")
else:
    # 1. Check states
    states = execute("sale.order", "read", old_ids, fields=["id", "state", "name"])
    state_counts = {}
    for r in states:
        state_counts[r["state"]] = state_counts.get(r["state"], 0) + 1
    print(f"  States: {state_counts}")

    # 2. Cancel associated pickings
    picking_ids = execute("stock.picking", "search",
                          [[("sale_id", "in", old_ids),
                            ("state", "not in", ["done", "cancel"])]])
    if picking_ids:
        print(f"  Cancelling {len(picking_ids)} pickings...")
        for i in range(0, len(picking_ids), 50):
            batch = picking_ids[i:i + 50]
            try:
                execute("stock.picking", "action_cancel", batch)
            except Exception as e:
                for pid in batch:
                    try:
                        execute("stock.picking", "action_cancel", [pid])
                    except Exception:
                        pass
        print("  Pickings cancelled.")

    # 3. Cancel SOs
    ids_to_cancel = [r["id"] for r in states if r["state"] not in ("draft", "cancel")]
    if ids_to_cancel:
        print(f"  Cancelling {len(ids_to_cancel)} SOs...")
        for i in range(0, len(ids_to_cancel), 50):
            batch = ids_to_cancel[i:i + 50]
            try:
                execute("sale.order", "action_cancel", batch)
            except Exception:
                for so_id in batch:
                    try:
                        execute("sale.order", "action_cancel", [so_id])
                    except Exception:
                        try:
                            execute("sale.order", "write", [so_id], {"state": "cancel"})
                        except Exception:
                            pass

    # 4. Verify states after cancel
    states2 = execute("sale.order", "read", old_ids, fields=["id", "state"])
    still_active = [r["id"] for r in states2 if r["state"] not in ("draft", "cancel")]
    if still_active:
        print(f"  WARNING: {len(still_active)} SOs still not cancelled – force writing state...")
        for so_id in still_active:
            try:
                execute("sale.order", "write", [so_id], {"state": "cancel"})
            except Exception:
                pass

    # 5. Delete
    print("  Deleting old SOs...")
    deleted = 0
    failed = 0
    for i in range(0, len(old_ids), 50):
        batch = old_ids[i:i + 50]
        try:
            execute("sale.order", "unlink", batch)
            deleted += len(batch)
        except Exception:
            for so_id in batch:
                try:
                    execute("sale.order", "unlink", [so_id])
                    deleted += 1
                except Exception:
                    failed += 1
    print(f"  Deleted: {deleted}, Failed: {failed}")

# ── Final verify ────────────────────────────────────────────────────────────
total = execute("sale.order", "search_count", [[]])
print(f"\nTotal SOs in DB: {total}")

tg_pc_ids = execute("res.partner", "search", [[("name", "ilike", "Thế Giới PC")]])
if tg_pc_ids:
    tg_sos = execute("sale.order", "search_read",
                     [[("partner_id", "=", tg_pc_ids[0])]],
                     fields=["date_order"], order="date_order desc", limit=3)
    print(f"Thế Giới PC orders: {len(tg_sos)} (top 3 dates):")
    for s in tg_sos:
        print(f"  {s['date_order']}")
