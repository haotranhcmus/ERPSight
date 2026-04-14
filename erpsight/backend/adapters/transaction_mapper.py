"""
backend/adapters/transaction_mapper.py

Maps raw Odoo account.move + account.move.line dicts → Transaction domain model.

Margin computation:
  Odoo Community has no built-in margin field on account.move.line.
  Margin is computed as:
      margin_pct = (price_unit - cost_price) / price_unit
  where cost_price comes from product.product.standard_price
  (passed in as product_costs dict).

Usage:
    from erpsight.backend.adapters.transaction_mapper import map_transactions
    transactions = map_transactions(raw_moves, raw_lines, product_costs)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from erpsight.backend.adapters.mapper_utils import m2o_id as _m2o_id
from erpsight.backend.adapters.mapper_utils import m2o_name as _m2o_name
from erpsight.backend.adapters.mapper_utils import parse_dt as _parse_dt
from erpsight.backend.models.domain.transaction import InvoiceLine, Transaction


def _compute_avg_margin(lines: List[InvoiceLine]) -> float:
    """Weighted average margin across lines (by revenue contribution)."""
    total_revenue = sum(l.price_subtotal for l in lines)
    if total_revenue <= 0:
        return 0.0
    total_cost = sum(l.cost_price * l.quantity for l in lines)
    return round((total_revenue - total_cost) / total_revenue, 4)


def map_invoice_line(
    raw: Dict[str, Any],
    fallback_move_id: int,
    product_costs: Dict[int, float],
) -> InvoiceLine:
    prod_id = _m2o_id(raw.get("product_id"))
    price_unit = float(raw.get("price_unit") or 0)
    cost = product_costs.get(prod_id, 0.0) if prod_id is not None else 0.0
    margin_pct = (price_unit - cost) / price_unit if price_unit > 0 else 0.0

    return InvoiceLine(
        line_id=int(raw["id"]),
        move_id=_m2o_id(raw.get("move_id")) or fallback_move_id,
        product_id=prod_id,
        product_name=_m2o_name(raw.get("product_id")),
        price_unit=price_unit,
        quantity=float(raw.get("quantity") or 0),
        price_subtotal=float(raw.get("price_subtotal") or 0),
        discount=float(raw.get("discount") or 0),
        cost_price=cost,
        margin_pct=round(margin_pct, 4),
    )


def map_transaction(
    raw: Dict[str, Any],
    raw_lines: List[Dict[str, Any]],
    product_costs: Optional[Dict[int, float]] = None,
) -> Transaction:
    product_costs = product_costs or {}
    move_id = int(raw["id"])
    invoice_lines = [
        map_invoice_line(l, move_id, product_costs) for l in raw_lines
    ]
    return Transaction(
        move_id=move_id,
        name=raw.get("name", ""),
        partner_id=_m2o_id(raw.get("partner_id")),
        partner_name=_m2o_name(raw.get("partner_id")),
        invoice_date=_parse_dt(raw.get("invoice_date")) or datetime.now(),
        move_type=raw.get("move_type", ""),
        state=raw.get("state", ""),
        amount_total=float(raw.get("amount_total") or 0),
        amount_untaxed=float(raw.get("amount_untaxed") or 0),
        lines=invoice_lines,
        avg_margin_pct=_compute_avg_margin(invoice_lines),
    )


def map_transactions(
    raw_moves: List[Dict[str, Any]],
    raw_lines: List[Dict[str, Any]],
    product_costs: Optional[Dict[int, float]] = None,
) -> List[Transaction]:
    """
    Map a batch of account.moves and their lines to Transaction domain models.

    Args:
        raw_moves:     list of dicts from OdooClient.get_invoices()
        raw_lines:     list of dicts from OdooClient.get_invoice_lines()
        product_costs: {product_id: standard_price} from OdooClient.get_product_cost_map()
    """
    product_costs = product_costs or {}
    lines_by_move: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for line in raw_lines:
        mid = _m2o_id(line.get("move_id"))
        if mid is not None:
            lines_by_move[mid].append(line)

    return [
        map_transaction(move, lines_by_move[move["id"]], product_costs)
        for move in raw_moves
    ]
