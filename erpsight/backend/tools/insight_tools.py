"""
backend/tools/insight_tools.py

Context-fetching tools called by the InsightAgent before generating
a recommendation.  Each function wraps data_service + light aggregation
to return a single LLM-readable dict — no raw Odoo records exposed.

Naming contract (matches KB scenario tables):
    fetch_sales_context      → KB1 spike detection, KB2 margin, KB3 churn
    fetch_inventory_context  → KB1 stock levels
    fetch_purchase_context   → KB1/KB2 supplier price analysis
    fetch_helpdesk_context   → KB3 VIP churn signals
    fetch_similar_incidents  → Phase 1: stub (returns [])
                               Phase 2: FAISS vector search

All functions accept an active OdooClient instance so the caller controls
connection lifecycle and can share a single auth session across tools.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.services import data_service


# ── helpers ───────────────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _parse_date(dt_str: Any) -> Optional[date]:
    """Return a date object from an Odoo datetime string, or None."""
    if not dt_str or dt_str is False:
        return None
    try:
        return datetime.fromisoformat(str(dt_str)[:10]).date()
    except ValueError:
        return None


def _product_id_by_sku(client: OdooClient, sku: str) -> Optional[int]:
    """
    Resolve a product SKU (internal reference or name fragment) to a
    product.product id.  Returns None when no match found.
    """
    # Try exact internal reference first
    results = client.search_read(
        "product.product",
        [("default_code", "=", sku), ("active", "=", True)],
        ["id", "name"],
        limit=1,
    )
    if results:
        return results[0]["id"]
    # Fall back to case-insensitive name contains
    results = client.search_read(
        "product.product",
        [("name", "ilike", sku), ("active", "=", True)],
        ["id", "name"],
        limit=1,
    )
    return results[0]["id"] if results else None


def _partner_id_by_name(client: OdooClient, name: str) -> Optional[int]:
    """
    Resolve a partner name fragment to a res.partner id.
    Returns None when no match found.
    """
    results = client.search_read(
        "res.partner",
        [("name", "ilike", name)],
        ["id", "name"],
        limit=1,
    )
    return results[0]["id"] if results else None


# ── fetch_sales_context ───────────────────────────────────────────────────────

def fetch_sales_context(
    client: OdooClient,
    product_sku: Optional[str] = None,
    partner_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    baseline_date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate sale order data into a concise context dict for the LLM.

    The optional `baseline_date_to` parameter splits the window into two
    sub-periods so the LLM can compare a *baseline* daily average against
    a *current* (spike) daily average:
        - baseline : date_from  →  baseline_date_to
        - current  : baseline_date_to+1 day  →  date_to

    Args:
        client:           active OdooClient instance
        product_sku:      internal reference or name fragment — filters to 1 product
        partner_name:     customer name fragment — filters to 1 customer
        date_from:        ISO "YYYY-MM-DD" start of analysis window
        date_to:          ISO "YYYY-MM-DD" end of analysis window; defaults to today
        baseline_date_to: ISO "YYYY-MM-DD" end of baseline sub-period (optional)

    Returns:
        {
          "product_sku":          str | None,
          "product_name":         str | None,
          "partner_name":         str | None,
          "date_from":            str,
          "date_to":              str,
          "total_qty":            float,       # sum of quantities across all matched lines
          "total_revenue":        float,       # sum of price_subtotal
          "order_count":          int,
          "avg_daily_qty":        float,       # total_qty / calendar days
          "avg_daily_baseline":   float | None,  # only when baseline_date_to given
          "avg_daily_current":    float | None,  # only when baseline_date_to given
          "daily_qty_by_date":    {date_str: float},  # per-day breakdown
          "top_partners": [       # top 5 customers by quantity (when no partner filter)
              {"partner_name": str, "qty": float, "revenue": float},
              ...
          ],
          "top_products": [       # top 5 products by quantity (when no product filter)
              {"product_name": str, "qty": float, "revenue": float},
              ...
          ],
        }
    """
    resolved_to = date_to or _today()
    resolved_from = date_from or "2000-01-01"

    partner_id: Optional[int] = None
    if partner_name:
        partner_id = _partner_id_by_name(client, partner_name)

    orders = data_service.fetch_orders(
        client,
        date_from=resolved_from,
        date_to=resolved_to,
        partner_id=partner_id,
    )

    # Determine target product_id once
    target_product_id: Optional[int] = None
    resolved_product_name: Optional[str] = None
    if product_sku:
        target_product_id = _product_id_by_sku(client, product_sku)

    # Aggregate across matching lines
    total_qty = 0.0
    total_revenue = 0.0
    daily_qty: Dict[str, float] = defaultdict(float)
    partner_agg: Dict[str, Dict[str, float]] = defaultdict(lambda: {"qty": 0.0, "revenue": 0.0})
    product_agg: Dict[str, Dict[str, float]] = defaultdict(lambda: {"qty": 0.0, "revenue": 0.0})

    baseline_qty = 0.0
    current_qty = 0.0
    baseline_days = 0
    current_days = 0

    for order in orders:
        d_str = str(order.date_order)[:10]

        for line in order.lines:
            if target_product_id is not None and line.product_id != target_product_id:
                continue
            if resolved_product_name is None and target_product_id is not None:
                resolved_product_name = line.product_name

            total_qty += line.quantity
            total_revenue += line.price_subtotal
            daily_qty[d_str] += line.quantity
            partner_agg[order.partner_name]["qty"] += line.quantity
            partner_agg[order.partner_name]["revenue"] += line.price_subtotal
            product_agg[line.product_name]["qty"] += line.quantity
            product_agg[line.product_name]["revenue"] += line.price_subtotal

    # Calendar days in full window
    try:
        d0 = date.fromisoformat(resolved_from)
        d1 = date.fromisoformat(resolved_to)
        total_days = max((d1 - d0).days + 1, 1)
    except ValueError:
        total_days = 1

    avg_daily_qty = total_qty / total_days

    # Split baseline / current when requested
    avg_daily_baseline: Optional[float] = None
    avg_daily_current: Optional[float] = None
    if baseline_date_to:
        try:
            b_end = date.fromisoformat(baseline_date_to)
            c_start = date.fromisoformat(baseline_date_to)
            c_end = date.fromisoformat(resolved_to)
            d_start = date.fromisoformat(resolved_from)

            baseline_days = max((b_end - d_start).days + 1, 1)
            current_days = max((c_end - c_start).days, 1)  # c_start exclusive

            for d_str, qty in daily_qty.items():
                d_val = date.fromisoformat(d_str)
                if d_val <= b_end:
                    baseline_qty += qty
                else:
                    current_qty += qty

            avg_daily_baseline = baseline_qty / baseline_days
            avg_daily_current = current_qty / current_days
        except ValueError:
            pass

    # Top 5 sortings
    top_partners = sorted(
        [{"partner_name": k, **v} for k, v in partner_agg.items()],
        key=lambda x: x["qty"],
        reverse=True,
    )[:5]

    top_products = sorted(
        [{"product_name": k, **v} for k, v in product_agg.items()],
        key=lambda x: x["qty"],
        reverse=True,
    )[:5]

    return {
        "product_sku": product_sku,
        "product_name": resolved_product_name,
        "partner_name": partner_name,
        "date_from": resolved_from,
        "date_to": resolved_to,
        "total_qty": round(total_qty, 2),
        "total_revenue": round(total_revenue, 2),
        "order_count": len(orders),
        "avg_daily_qty": round(avg_daily_qty, 2),
        "avg_daily_baseline": round(avg_daily_baseline, 2) if avg_daily_baseline is not None else None,
        "avg_daily_current": round(avg_daily_current, 2) if avg_daily_current is not None else None,
        "daily_qty_by_date": dict(sorted(daily_qty.items())),
        "top_partners": top_partners,
        "top_products": top_products,
    }


# ── fetch_inventory_context ───────────────────────────────────────────────────

def fetch_inventory_context(
    client: OdooClient,
    product_sku: str,
) -> Dict[str, Any]:
    """
    Return stock levels + pending PO lines for a single product SKU.

    Args:
        client:      active OdooClient instance
        product_sku: internal reference or name fragment

    Returns:
        {
          "product_sku":              str,
          "product_name":             str | None,
          "product_id":               int | None,
          "qty_on_hand":              float,
          "reserved_quantity":        float,
          "available_qty":            float,
          "location_name":            str | None,
          "avg_daily_sales":          float,   # 0.0 when not yet computed by detector
          "days_of_stock_remaining":  float | None,
          "pending_pos": [
              {
                "po_name":        str,
                "supplier_name":  str,
                "qty":            float,
                "price_unit":     float,
                "date_planned":   str,
                "state":          str,
              },
              ...
          ],
        }
    """
    product_id = _product_id_by_sku(client, product_sku)

    # Stock
    inventories = data_service.fetch_inventories(
        client,
        product_ids=[product_id] if product_id else None,
    )

    qty_on_hand = 0.0
    reserved_quantity = 0.0
    available_qty = 0.0
    product_name: Optional[str] = None
    location_name: Optional[str] = None

    for inv in inventories:
        if product_id is None or inv.product_id == product_id:
            qty_on_hand += inv.qty_on_hand
            reserved_quantity += inv.reserved_quantity
            available_qty += inv.available_qty
            if product_name is None:
                product_name = inv.product_name
            if location_name is None:
                location_name = inv.location_id

    # Pending POs for this product — exclude fully-received POs
    # (in Odoo 17, PO stays in 'purchase' state after receipt; use receipt_status
    # to distinguish pending-incoming from already-received)
    all_pos = data_service.fetch_supplier_orders(
        client,
        states=["draft", "sent", "purchase"],
        pending_only=True,
    )

    pending_pos: List[Dict[str, Any]] = []
    for po in all_pos:
        for line in po.lines:
            if product_id is not None and line.product_id != product_id:
                continue
            if product_name is None:
                product_name = line.product_name
            pending_pos.append({
                "po_name": po.name,
                "supplier_name": po.partner_name,
                "qty": line.quantity,
                "price_unit": line.price_unit,
                "date_planned": str(line.date_planned)[:10] if line.date_planned else None,
                "state": po.state,
            })

    # Sort by planned date ascending
    pending_pos.sort(key=lambda x: x["date_planned"] or "9999-99-99")

    # days_of_stock_remaining requires avg_daily_sales to be injected externally;
    # Inventory.avg_daily_sales defaults to 0.0 from the mapper, so we report
    # it as None here to avoid misleading "infinity" values.
    avg_daily = inventories[0].avg_daily_sales if inventories else 0.0
    days_remaining: Optional[float] = None
    if avg_daily > 0:
        days_remaining = round(available_qty / avg_daily, 1)

    return {
        "product_sku": product_sku,
        "product_name": product_name,
        "product_id": product_id,
        "qty_on_hand": round(qty_on_hand, 2),
        "reserved_quantity": round(reserved_quantity, 2),
        "available_qty": round(available_qty, 2),
        "location_name": location_name,
        "avg_daily_sales": round(avg_daily, 2),
        "days_of_stock_remaining": days_remaining,
        "pending_pos": pending_pos,
    }


# ── fetch_purchase_context ────────────────────────────────────────────────────

def fetch_purchase_context(
    client: OdooClient,
    product_sku: str,
    last_n_pos: int = 5,
) -> Dict[str, Any]:
    """
    Return purchase order history for a product to detect price changes
    and estimate supplier lead time.

    Args:
        client:      active OdooClient instance
        product_sku: internal reference or name fragment
        last_n_pos:  how many most-recent PO lines to include in history

    Returns:
        {
          "product_sku":          str,
          "product_name":         str | None,
          "product_id":           int | None,
          "po_history": [         # sorted newest-first, max last_n_pos items
              {
                "po_name":       str,
                "date_order":    str,
                "supplier_name": str,
                "qty":           float,
                "price_unit":    float,
                "date_planned":  str | None,
                "state":         str,
              },
              ...
          ],
          "latest_price":           float | None,
          "previous_price":         float | None,
          "price_change_pct":       float | None,  # positive = price went up
          "latest_supplier_name":   str | None,
          "estimated_lead_time_days": int | None,  # median across history entries
        }
    """
    product_id = _product_id_by_sku(client, product_sku)

    pos = data_service.fetch_supplier_orders(client)

    # Collect all matching lines with their PO metadata
    matched: List[Dict[str, Any]] = []
    product_name: Optional[str] = None

    for po in pos:
        for line in po.lines:
            if product_id is not None and line.product_id != product_id:
                continue
            if product_name is None:
                product_name = line.product_name
            matched.append({
                "po_name": po.name,
                "date_order": str(po.date_order)[:10],
                "supplier_name": po.partner_name,
                "qty": line.quantity,
                "price_unit": line.price_unit,
                "date_planned": str(line.date_planned)[:10] if line.date_planned else None,
                "state": po.state,
            })

    # Sort newest-first
    matched.sort(key=lambda x: x["date_order"], reverse=True)
    history = matched[:last_n_pos]

    # Price comparison: latest vs previous
    prices = [e["price_unit"] for e in matched if e["price_unit"] > 0]
    latest_price: Optional[float] = prices[0] if len(prices) >= 1 else None
    previous_price: Optional[float] = prices[1] if len(prices) >= 2 else None
    price_change_pct: Optional[float] = None
    if latest_price is not None and previous_price is not None and previous_price > 0:
        price_change_pct = round((latest_price - previous_price) / previous_price * 100, 1)

    # Lead time: median (date_planned - date_order) across history
    lead_times: List[int] = []
    for entry in matched:
        if entry["date_planned"] and entry["date_order"]:
            try:
                dt_order = date.fromisoformat(entry["date_order"])
                dt_planned = date.fromisoformat(entry["date_planned"])
                delta = (dt_planned - dt_order).days
                if delta > 0:
                    lead_times.append(delta)
            except ValueError:
                pass

    estimated_lead_time: Optional[int] = None
    if lead_times:
        lead_times_sorted = sorted(lead_times)
        mid = len(lead_times_sorted) // 2
        estimated_lead_time = lead_times_sorted[mid]

    latest_supplier = history[0]["supplier_name"] if history else None

    return {
        "product_sku": product_sku,
        "product_name": product_name,
        "product_id": product_id,
        "po_history": history,
        "latest_price": latest_price,
        "previous_price": previous_price,
        "price_change_pct": price_change_pct,
        "latest_supplier_name": latest_supplier,
        "estimated_lead_time_days": estimated_lead_time,
    }


# ── fetch_helpdesk_context ────────────────────────────────────────────────────

def fetch_helpdesk_context(
    client: OdooClient,
    partner_name: Optional[str] = None,
    date_from: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return open helpdesk tickets and complaint summary for a customer,
    used to detect VIP churn risk (KB3).

    Args:
        client:       active OdooClient instance
        partner_name: customer name fragment — filters to 1 customer
        date_from:    ISO "YYYY-MM-DD" — look-back window for ticket history

    Returns:
        {
          "partner_name":         str | None,
          "partner_id":           int | None,
          "date_from":            str | None,
          "open_tickets": [
              {
                "ticket_number":  str,
                "title":          str,
                "priority":       str,   # "0" normal, "1" high, "2" urgent
                "stage":          str,
                "create_date":    str,
                "days_open":      int,
              },
              ...
          ],
          "open_ticket_count":    int,
          "closed_ticket_count":  int,
          "high_priority_count":  int,   # priority in ("1", "2")
          "avg_resolution_days":  float | None,
          "complaint_summary":    str,   # formatted prose for LLM context
        }
    """
    partner_id: Optional[int] = None
    if partner_name:
        partner_id = _partner_id_by_name(client, partner_name)

    tickets = data_service.fetch_tickets(
        client,
        date_from=date_from,
        partner_id=partner_id,
    )

    today_d = date.today()

    open_tickets: List[Dict[str, Any]] = []
    closed_count = 0
    high_priority_count = 0
    resolution_days_list: List[float] = []

    for t in tickets:
        is_high = t.priority in ("1", "2")
        if is_high:
            high_priority_count += 1

        if t.closed:
            closed_count += 1
            if t.create_date and t.closed_date:
                cd = _parse_date(t.create_date)
                cl = _parse_date(t.closed_date)
                if cd and cl:
                    resolution_days_list.append((cl - cd).days)
        else:
            create_d = _parse_date(t.create_date)
            days_open = (today_d - create_d).days if create_d else 0
            open_tickets.append({
                "ticket_number": t.number or str(t.ticket_id),
                "title": t.name,
                "priority": t.priority,
                "stage": t.stage_name,
                "create_date": str(t.create_date)[:10],
                "days_open": days_open,
            })

    # Sort open tickets: highest priority first, then oldest first
    open_tickets.sort(key=lambda x: (-int(x["priority"]), -x["days_open"]))

    avg_resolution: Optional[float] = None
    if resolution_days_list:
        avg_resolution = round(sum(resolution_days_list) / len(resolution_days_list), 1)

    # Plain-english summary for LLM
    parts: List[str] = []
    if partner_name:
        parts.append(f"Customer: {partner_name}.")
    parts.append(
        f"{len(open_tickets)} open ticket(s), {closed_count} closed."
    )
    if high_priority_count:
        parts.append(f"{high_priority_count} ticket(s) marked high/urgent priority.")
    if open_tickets:
        oldest = open_tickets[-1]
        parts.append(
            f"Oldest unresolved: '{oldest['title']}' open for {oldest['days_open']} days."
        )
    if avg_resolution is not None:
        parts.append(f"Average resolution time: {avg_resolution} days.")
    complaint_summary = " ".join(parts)

    return {
        "partner_name": partner_name,
        "partner_id": partner_id,
        "date_from": date_from,
        "open_tickets": open_tickets,
        "open_ticket_count": len(open_tickets),
        "closed_ticket_count": closed_count,
        "high_priority_count": high_priority_count,
        "avg_resolution_days": avg_resolution,
        "complaint_summary": complaint_summary,
    }


# ── fetch_similar_incidents (Phase 1 stub) ────────────────────────────────────

def fetch_similar_incidents(
    event_embedding: Optional[List[float]] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Return semantically similar past incidents to support the LLM recommendation.

    Phase 1: always returns an empty list.
    Phase 2: will query a FAISS / pgvector index of historical event embeddings.

    Args:
        event_embedding: float vector for the current event (ignored in Phase 1)
        top_k:           number of similar incidents to return

    Returns:
        [] in Phase 1.
        List of {"incident_id", "summary", "action_taken", "outcome", "similarity_score"}
        in Phase 2.
    """
    _ = (event_embedding, top_k)  # Phase 2: replace with FAISS search
    return []
