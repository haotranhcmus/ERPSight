"""
backend/adapters/order_mapper.py

Maps raw Odoo sale.order + sale.order.line dicts → Order domain model.

Margin is computed from product.standard_price rather than any Odoo
calculated field (Community edition has no built-in margin on SO).

Usage:
    from erpsight.backend.adapters.order_mapper import map_orders
    orders = map_orders(raw_orders, raw_lines, product_costs)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from erpsight.backend.adapters.mapper_utils import m2o_id as _m2o_id
from erpsight.backend.adapters.mapper_utils import m2o_name as _m2o_name
from erpsight.backend.adapters.mapper_utils import parse_dt as _parse_dt
from erpsight.backend.models.domain.order import Order, OrderLine


# ── public API ─────────────────────────────────────────────────────────────────


def map_order_line(
    raw: Dict[str, Any],
    fallback_order_id: int,
    product_costs: Dict[int, float],
) -> OrderLine:
    prod_id = _m2o_id(raw.get("product_id"))
    price_unit = float(raw.get("price_unit") or 0)
    cost = product_costs.get(prod_id, 0.0) if prod_id is not None else 0.0
    margin_pct = (price_unit - cost) / price_unit if price_unit > 0 else 0.0

    return OrderLine(
        line_id=int(raw["id"]),
        order_id=_m2o_id(raw.get("order_id")) or fallback_order_id,
        product_id=prod_id or 0,
        product_name=_m2o_name(raw.get("product_id")),
        quantity=float(raw.get("product_uom_qty") or 0),
        price_unit=price_unit,
        price_subtotal=float(raw.get("price_subtotal") or 0),
        discount=float(raw.get("discount") or 0),
        cost_price=cost,
        margin_pct=round(margin_pct, 4),
    )


def map_order(
    raw: Dict[str, Any],
    lines: List[Dict[str, Any]],
    product_costs: Optional[Dict[int, float]] = None,
) -> Order:
    product_costs = product_costs or {}
    order_id = int(raw["id"])
    return Order(
        order_id=order_id,
        name=raw.get("name", ""),
        partner_id=_m2o_id(raw.get("partner_id")) or 0,
        partner_name=_m2o_name(raw.get("partner_id")),
        date_order=_parse_dt(raw.get("date_order")) or datetime.now(),
        amount_total=float(raw.get("amount_total") or 0),
        state=raw.get("state", ""),
        lines=[map_order_line(l, order_id, product_costs) for l in lines],
    )


def map_orders(
    raw_orders: List[Dict[str, Any]],
    raw_lines: List[Dict[str, Any]],
    product_costs: Optional[Dict[int, float]] = None,
) -> List[Order]:
    """
    Map a batch of sale.orders and their lines to Order domain models.

    Args:
        raw_orders:    list of dicts from OdooClient.get_sale_orders()
        raw_lines:     list of dicts from OdooClient.get_sale_order_lines()
        product_costs: {product_id: standard_price} from OdooClient.get_product_cost_map()
    """
    product_costs = product_costs or {}
    lines_by_order: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for line in raw_lines:
        oid = _m2o_id(line.get("order_id"))
        if oid is not None:
            lines_by_order[oid].append(line)

    return [
        map_order(order, lines_by_order[order["id"]], product_costs)
        for order in raw_orders
    ]
