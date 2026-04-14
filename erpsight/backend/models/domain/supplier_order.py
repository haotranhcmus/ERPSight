"""
backend/models/domain/supplier_order.py

Domain model for purchase orders.
Mapped from: purchase.order + purchase.order.line (via purchase_mapper.py)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class POLine(BaseModel):
    line_id: int
    po_id: int
    product_id: int
    product_name: str
    quantity: float
    price_unit: float
    date_planned: Optional[datetime] = None   # expected delivery date


class SupplierOrder(BaseModel):
    po_id: int
    name: str                   # PO number e.g. "P00005"
    partner_id: int
    partner_name: str
    date_order: datetime
    state: str                  # draft | sent | purchase | done | cancel
    lines: List[POLine] = Field(default_factory=list)
