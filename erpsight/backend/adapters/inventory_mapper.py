"""
backend/adapters/inventory_mapper.py

Maps raw Odoo stock.quant dicts → Inventory domain model.

avg_daily_sales and days_of_stock_remaining are left at defaults (0.0 / None)
and populated later by SentinelAgent.compute_derived_metrics().

Usage:
    from backend.adapters.inventory_mapper import map_inventories
    inventories = map_inventories(raw_quants)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.models.domain.inventory import Inventory


def _m2o_id(value: Any) -> Optional[int]:
    if isinstance(value, (list, tuple)) and len(value) >= 1 and value[0]:
        return int(value[0])
    return None


def _m2o_name(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    return ""


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or value is False:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def map_inventory(raw: Dict[str, Any]) -> Inventory:
    qty = float(raw.get("quantity") or 0)       # Odoo 17: field is 'quantity'
    reserved = float(raw.get("reserved_quantity") or 0)
    return Inventory(
        quant_id=int(raw["id"]),
        product_id=_m2o_id(raw.get("product_id")) or 0,
        product_name=_m2o_name(raw.get("product_id")),
        qty_on_hand=qty,
        reserved_quantity=reserved,
        available_qty=max(qty - reserved, 0.0),
        location_id=_m2o_id(raw.get("location_id")) or 0,
        location_name=_m2o_name(raw.get("location_id")),
        last_movement=_parse_dt(raw.get("in_date")),
    )


def map_inventories(raw_list: List[Dict[str, Any]]) -> List[Inventory]:
    """
    Map a batch of stock.quant records to Inventory domain models.

    Args:
        raw_list: list of dicts from OdooClient.get_stock_quants()
    """
    return [map_inventory(raw) for raw in raw_list]
