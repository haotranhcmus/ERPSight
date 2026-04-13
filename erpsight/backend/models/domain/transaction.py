"""
backend/models/domain/transaction.py

Domain model for Accounting Transactions (Invoices / Vendor Bills).
Mapped from: account.move + account.move.line (Odoo)

Note: Odoo Community has no built-in margin field on account.move.line.
Margin is computed from product.product.standard_price vs price_unit.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):
    line_id: int
    move_id: int
    product_id: Optional[int] = None
    product_name: str = ""
    price_unit: float
    quantity: float
    price_subtotal: float
    discount: float = 0.0
    cost_price: float = 0.0     # from product.product.standard_price
    margin_pct: float = 0.0     # (price_unit - cost_price) / price_unit


class Transaction(BaseModel):
    move_id: int
    name: str
    partner_id: Optional[int] = None
    partner_name: str = ""
    invoice_date: datetime
    move_type: str              # out_invoice | in_invoice | out_refund | in_refund
    state: str                  # draft | posted | cancel
    amount_total: float
    amount_untaxed: float
    lines: List[InvoiceLine] = Field(default_factory=list)
    avg_margin_pct: float = 0.0   # weighted average across lines
