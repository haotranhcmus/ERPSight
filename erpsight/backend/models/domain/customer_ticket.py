from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CustomerTicket(BaseModel):
    ticket_id: int
    number: str
    name: str
    description: str
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None
    stage_name: Optional[str] = None
    priority: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    create_date: datetime
    closed_date: Optional[datetime] = None
    closed: bool
    last_stage_update: Optional[datetime] = None
