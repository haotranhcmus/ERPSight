"""
executor/send_internal_alert.py

Executor for low-risk alert actions:
  - send_internal_alert      → post chatter note
  - send_margin_alert        → post chatter note with margin table
  - send_churn_risk_alert    → post chatter note with churn context
  - flag_product_for_price_review → post internal note on product
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from erpsight.backend.adapters.odoo_client import OdooClient

logger = logging.getLogger(__name__)

_client: OdooClient | None = None


def _get_client() -> OdooClient:
    global _client
    if _client is None:
        _client = OdooClient()
    return _client


def _resolve_record_id(model: str, lookup: Dict[str, str]) -> int | None:
    """Resolve a record ID from a lookup dict like {"field": "default_code", "value": "SKU001"}."""
    client = _get_client()
    field = lookup.get("field", "name")
    value = lookup.get("value", "")
    if not value:
        return None
    records = client.search_read(model, [(field, "=", value)], ["id"], limit=1)
    if records:
        return records[0]["id"]
    return None


def _resolve_product_template_id(params: Dict[str, Any]) -> tuple[int | None, str]:
    """Resolve product.template id and SKU from params.
    Supports both SKU lookup and direct _odoo_product_id (product.product) fallback.
    Returns (template_id, sku).
    """
    client = _get_client()
    sku = params.get("product_sku", "")
    product_id = params.get("_odoo_product_id")

    if product_id:
        # product.product ID → product.template ID
        pp = client.search_read(
            "product.product", [("id", "=", product_id)],
            ["product_tmpl_id", "default_code"], limit=1,
        )
        if pp:
            tmpl_ref = pp[0].get("product_tmpl_id")
            tmpl_id = int(tmpl_ref[0]) if tmpl_ref else None
            sku = pp[0].get("default_code") or sku
            if tmpl_id:
                return tmpl_id, sku

    if sku:
        records = client.search_read(
            "product.template", [("default_code", "=", sku)], ["id"], limit=1,
        )
        if records:
            return int(records[0]["id"]), sku

    return None, sku


def _resolve_partner_id(partner_name: str) -> int | None:
    client = _get_client()
    records = client.search_read("res.partner", [("name", "ilike", partner_name)], ["id"], limit=1)
    return records[0]["id"] if records else None


# ── send_internal_alert ───────────────────────────────────────────────────────

def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Post a chatter note on an Odoo record."""
    client = _get_client()
    model = params.get("res_model", "product.template")
    lookup = params.get("res_id_lookup", {})

    # Try product-specific lookup first when model is product.template
    res_id: int | None = None
    if model == "product.template":
        res_id, _ = _resolve_product_template_id(params)
    if res_id is None:
        res_id = _resolve_record_id(model, lookup)
    if res_id is None:
        return {"success": False, "error": f"Cannot resolve record: {lookup}"}

    subject = params.get("subject", "")
    body = params.get("message_body", "")
    message = f"{subject}\n{body}"

    msg_id = client.post_chatter_message(model, res_id, message)
    return {"success": True, "record_id": msg_id}


# ── send_margin_alert ────────────────────────────────────────────────────────

def execute_margin_alert(params: Dict[str, Any]) -> Dict[str, Any]:
    """Post margin-specific alert on the product record."""
    client = _get_client()
    res_id, sku = _resolve_product_template_id(params)
    if res_id is None:
        return {"success": False, "error": f"Product not found (sku={params.get('product_sku')!r}, id={params.get('_odoo_product_id')})"}

    label = sku or f"ID:{params.get('_odoo_product_id', '?')}"
    old_price = params.get('old_purchase_price', 0)
    new_price = params.get('new_purchase_price', 0)
    pct = params.get('price_change_pct', 0)
    sale = params.get('current_sale_price', 0)
    margin = params.get('current_margin_pct', 0)
    loss = params.get('projected_daily_loss', 0)

    lines = [f"[ERPSight] Canh bao bien LN - {label}"]
    if old_price > 0 and new_price > 0:
        lines.append(f"Gia von: {old_price:,.0f}d -> {new_price:,.0f}d ({pct:+.1f}%)")
    lines.append(f"Gia ban hien tai: {sale:,.0f}d")
    lines.append(f"Bien LN: {margin:.2f}%")
    if loss > 0:
        lines.append(f"Ton that uoc tinh/ngay: {loss:,.0f}d")
    body = "\n".join(lines)
    msg_id = client.post_chatter_message("product.template", res_id, body)
    return {"success": True, "record_id": msg_id}


# ── send_churn_risk_alert ────────────────────────────────────────────────────

def execute_churn_alert(params: Dict[str, Any]) -> Dict[str, Any]:
    """Post churn alert on the partner record."""
    client = _get_client()
    partner_name = params.get("partner_name", "")
    partner_id = _resolve_partner_id(partner_name)
    if partner_id is None:
        return {"success": False, "error": f"Partner '{partner_name}' not found"}

    lines = [
        f"[ERPSight] Canh bao churn - {partner_name}",
        f"Don hang cuoi: {params.get('last_order_date', 'N/A')}",
        f"Im lang: {params.get('silent_days', 0)} ngay",
        f"Chu ky TB: {params.get('avg_order_cycle', 0):.0f} ngay",
        f"He so qua han: {params.get('overdue_factor', 0):.2f}x",
    ]
    body = "\n".join(lines)
    msg_id = client.post_chatter_message("res.partner", partner_id, body)
    return {"success": True, "record_id": msg_id}


# ── flag_product_for_price_review ────────────────────────────────────────────

def execute_flag_review(params: Dict[str, Any]) -> Dict[str, Any]:
    """Post internal note flagging product for price review."""
    client = _get_client()
    res_id, sku = _resolve_product_template_id(params)
    if res_id is None:
        return {"success": False, "error": f"Product not found (sku={params.get('product_sku')!r}, id={params.get('_odoo_product_id')})"}

    label = sku or f"ID:{params.get('_odoo_product_id', '?')}"
    cost = params.get('current_cost', 0)
    sale = params.get('current_sale_price', 0)
    margin = params.get('current_margin_pct', 0)
    suggested = params.get('suggested_new_sale_price', 0)
    target = params.get('target_margin_pct', 0)
    lines = [
        f"[ERPSight] Can xem xet gia ban - {label}",
        f"Gia nhap hien tai: {cost:,.0f}d",
        f"Gia ban hien tai: {sale:,.0f}d",
        f"Bien LN hien tai: {margin:.2f}%",
    ]
    if suggested > 0:
        lines.append(f"Gia ban de xuat: {suggested:,.0f}d (dat margin {target:.0f}%)")
    note = params.get('note', '').replace('[AI] ', '')
    if note:
        lines.append(note)
    body = "\n".join(lines)
    msg_id = client.post_chatter_message("product.template", res_id, body)
    return {"success": True, "record_id": msg_id}
