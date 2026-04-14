"""
backend/adapters/inventory_mapper.py

Maps raw Odoo stock.quant dicts → Inventory domain model.

avg_daily_sales and days_of_stock_remaining are left at defaults (0.0 / None)
and populated later by SentinelAgent.compute_derived_metrics().

Usage:
    from erpsight.backend.adapters.inventory_mapper import map_inventories
    inventories = map_inventories(raw_quants)
"""

from __future__ import annotations

from typing import Any, Dict, List

from erpsight.backend.adapters.mapper_utils import m2o_id as _m2o_id
from erpsight.backend.adapters.mapper_utils import m2o_name as _m2o_name
from erpsight.backend.models.domain.inventory import Inventory


def map_inventory(raw: Dict[str, Any]) -> Inventory:
    qty = float(raw.get("quantity") or 0)
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
    )


def map_inventories(raw_list: List[Dict[str, Any]]) -> List[Inventory]:
    """
    Map a batch of stock.quant records to Inventory domain models.

    Args:
        raw_list: list of dicts from OdooClient.get_stock_quants()
    """
    return [map_inventory(raw) for raw in raw_list]
