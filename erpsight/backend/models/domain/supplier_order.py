from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class POLine(BaseModel):
    line_id: int
    po_id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: float
    price_unit: float
    date_planned: Optional[datetime] = None

class SupplierOrder(BaseModel):
    po_id: int
    name: str
    partner_id: int
    partner_name: Optional[str] = None
    date_order: datetime
    state: str
    lines: List[POLine] = Field(default_factory=list)
