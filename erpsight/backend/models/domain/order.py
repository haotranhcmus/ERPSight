from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class OrderLine(BaseModel):
    line_id: int
    order_id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: float
    price_unit: float
    price_subtotal: float
    discount: float
    cost_price: float
    margin_pct: float

class Order(BaseModel):
    order_id: int
    name: str
    partner_id: int
    partner_name: Optional[str] = None
    date_order: datetime
    amount_total: float
    state: str
    lines: List[OrderLine] = Field(default_factory=list)
