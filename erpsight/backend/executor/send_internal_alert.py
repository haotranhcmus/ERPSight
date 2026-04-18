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
    message = f"<b>{subject}</b><br/>{body}"

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

    if old_price > 0 and new_price > 0:
        price_line = f"Giá vốn: {old_price:,.0f}đ → {new_price:,.0f}đ ({pct:+.1f}%)<br/>"
    else:
        price_line = ""

    body = (
        f"<b>[ERPSight] Cảnh báo biên lợi nhuận – {label}</b><br/>"
        f"{price_line}"
        f"Giá bán hiện tại: {sale:,.0f}đ<br/>"
        f"Biên LN: {margin:.2f}%<br/>"
        + (f"Tổn thất ước tính/ngày: {loss:,.0f}đ" if loss > 0 else "")
    )
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

    body = (
        f"<b>[ERPSight] Cảnh báo churn – {partner_name}</b><br/>"
        f"Đơn hàng cuối: {params.get('last_order_date', 'N/A')}<br/>"
        f"Im lặng: {params.get('silent_days', 0)} ngày<br/>"
        f"Chu kỳ TB: {params.get('avg_order_cycle', 0):.0f} ngày<br/>"
        f"Hệ số quá hạn: {params.get('overdue_factor', 0):.2f}x"
    )
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
    body = (
        f"<b>[ERPSight] Cần xem xét giá – {label}</b><br/>"
        f"Giá nhập hiện tại: {cost:,.0f}đ<br/>"
        f"Giá bán hiện tại: {sale:,.0f}đ<br/>"
        f"Biên LN: {margin:.2f}%<br/>"
        + (f"Giá bán đề xuất: {suggested:,.0f}đ (đạt margin {target:.0f}%)<br/>" if suggested > 0 else "")
        + f"{params.get('note', '')}"
    )
    msg_id = client.post_chatter_message("product.template", res_id, body)
    return {"success": True, "record_id": msg_id}
