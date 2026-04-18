"""
executor/create_draft_po.py

Executor for purchase/pricing actions:
  - create_purchase_order  → create draft PO in Odoo (medium risk)
  - update_sale_price      → update product list_price (medium risk)
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


def _resolve_partner_id(name: str) -> int | None:
    client = _get_client()
    records = client.search_read("res.partner", [("name", "ilike", name)], ["id"], limit=1)
    return records[0]["id"] if records else None


def _resolve_product_id(sku: str) -> int | None:
    """Resolve product.product id from default_code (SKU)."""
    client = _get_client()
    records = client.search_read("product.product", [("default_code", "=", sku)], ["id"], limit=1)
    return records[0]["id"] if records else None


# ── create_purchase_order ─────────────────────────────────────────────────────

def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a draft purchase order in Odoo."""
    client = _get_client()

    supplier_name = params.get("supplier_name", "")
    partner_id = _resolve_partner_id(supplier_name)
    if partner_id is None:
        return {"success": False, "error": f"Supplier '{supplier_name}' not found"}

    sku = params.get("product_sku", "")
    product_id = _resolve_product_id(sku)
    if product_id is None:
        return {"success": False, "error": f"Product SKU '{sku}' not found"}

    order_lines = [{
        "product_id": product_id,
        "qty": float(params.get("qty", 1)),
        "price_unit": float(params.get("price_unit", 0)),
        "date_planned": params.get("date_planned", ""),
        "name": params.get("note", f"[ERPSight] Auto-PO for {sku}"),
    }]

    result = client.create_draft_purchase_order(
        partner_id=partner_id,
        order_lines=order_lines,
        notes=params.get("note", ""),
    )
    return {"success": True, **result}


# ── update_sale_price ─────────────────────────────────────────────────────────

def execute_update_price(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update the list_price of a product template."""
    client = _get_client()
    sku = params.get("product_sku", "")
    records = client.search_read("product.template", [("default_code", "=", sku)], ["id"], limit=1)
    if not records:
        return {"success": False, "error": f"Product template '{sku}' not found"}

    tmpl_id = records[0]["id"]
    new_price = float(params.get("new_sale_price", 0))
    if new_price <= 0:
        return {"success": False, "error": "new_sale_price must be > 0"}

    client._write("product.template", [tmpl_id], {"list_price": new_price})
    logger.info("Updated list_price of product.template#%d to %.2f", tmpl_id, new_price)

    # Post an audit note
    note = (
        f"<b>[ERPSight] Cập nhật giá bán</b><br/>"
        f"Giá cũ → Mới: {params.get('current_sale_price', params.get('old_sale_price', '?')):,.0f}đ → {new_price:,.0f}đ<br/>"
        f"Lý do: {params.get('reason', 'AI-suggested price update')}"
    )
    client.post_chatter_message("product.template", tmpl_id, note)

    return {"success": True, "record_id": tmpl_id, "new_price": new_price}
