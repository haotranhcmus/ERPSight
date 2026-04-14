"""
backend/adapters/purchase_mapper.py

Maps raw Odoo purchase.order + purchase.order.line dicts → SupplierOrder domain model.

Usage:
    from erpsight.backend.adapters.purchase_mapper import map_supplier_orders
    pos = map_supplier_orders(raw_orders, raw_lines)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from erpsight.backend.adapters.mapper_utils import m2o_id as _m2o_id
from erpsight.backend.adapters.mapper_utils import m2o_name as _m2o_name
from erpsight.backend.adapters.mapper_utils import parse_dt as _parse_dt
from erpsight.backend.models.domain.supplier_order import POLine, SupplierOrder


def map_po_line(raw: Dict[str, Any], fallback_po_id: int) -> POLine:
    return POLine(
        line_id=int(raw["id"]),
        po_id=_m2o_id(raw.get("order_id")) or fallback_po_id,
        product_id=_m2o_id(raw.get("product_id")) or 0,
        product_name=_m2o_name(raw.get("product_id")),
        quantity=float(raw.get("product_qty") or 0),
        price_unit=float(raw.get("price_unit") or 0),
        date_planned=_parse_dt(raw.get("date_planned")),
    )


def map_supplier_order(
    raw: Dict[str, Any],
    lines: List[Dict[str, Any]],
) -> SupplierOrder:
    po_id = int(raw["id"])
    return SupplierOrder(
        po_id=po_id,
        name=raw.get("name", ""),
        partner_id=_m2o_id(raw.get("partner_id")) or 0,
        partner_name=_m2o_name(raw.get("partner_id")),
        date_order=_parse_dt(raw.get("date_order")) or datetime.now(),
        state=raw.get("state", ""),
        lines=[map_po_line(l, po_id) for l in lines],
    )


def map_supplier_orders(
    raw_orders: List[Dict[str, Any]],
    raw_lines: List[Dict[str, Any]],
) -> List[SupplierOrder]:
    """
    Map a batch of purchase.orders and their lines to SupplierOrder domain models.

    Args:
        raw_orders: list of dicts from OdooClient.get_purchase_orders()
        raw_lines:  list of dicts from OdooClient.get_purchase_order_lines()
    """
    lines_by_po: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for line in raw_lines:
        oid = _m2o_id(line.get("order_id"))
        if oid is not None:
            lines_by_po[oid].append(line)

    return [
        map_supplier_order(order, lines_by_po[order["id"]])
        for order in raw_orders
    ]
