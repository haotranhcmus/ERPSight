"""
backend/models/domain/inventory.py

Domain model for inventory levels.
Mapped from: stock.quant (via inventory_mapper.py)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Inventory(BaseModel):
    quant_id: int
    product_id: int
    product_name: str
    qty_on_hand: float           # Odoo 17: maps from stock.quant.quantity
    reserved_quantity: float = 0.0
    available_qty: float = 0.0   # qty_on_hand - reserved_quantity
    location_id: int
    location_name: str
    last_movement: Optional[datetime] = None  # from stock.quant.in_date

    # Derived — populated by SentinelAgent.compute_derived_metrics()
    avg_daily_sales: float = 0.0
    days_of_stock_remaining: Optional[float] = None
