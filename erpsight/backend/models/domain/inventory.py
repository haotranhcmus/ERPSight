from pydantic import BaseModel, Field
from typing import Optional

class Inventory(BaseModel):
    quant_id: int
    product_id: int
    product_name: Optional[str] = None
    qty_on_hand: float
    reserved_quantity: float
    available_qty: float
    location_id: int
    location_name: Optional[str] = None
    avg_daily_sales: float = 0.0
    days_of_stock_remaining: Optional[float] = None
