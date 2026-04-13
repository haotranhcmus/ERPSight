"""
backend/models/domain/order.py

Domain model for sales orders.
Mapped from: sale.order + sale.order.line (via order_mapper.py)
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class OrderLine(BaseModel):
    line_id: int
    order_id: int
    product_id: int
    product_name: str
    quantity: float
    price_unit: float
    price_subtotal: float
    discount: float = 0.0
    cost_price: float = 0.0     # from product.product.standard_price
    margin_pct: float = 0.0     # (price_unit - cost_price) / price_unit


class Order(BaseModel):
    order_id: int
    name: str                   # SO number e.g. "S00012"
    partner_id: int
    partner_name: str
    date_order: datetime
    amount_total: float
    amount_untaxed: float
    state: str                  # draft | sent | sale | done | cancel
    lines: List[OrderLine] = Field(default_factory=list)
