"""
backend/models/domain/customer_ticket.py

Domain model for Helpdesk Tickets.
Mapped from: helpdesk.ticket (OCA helpdesk_mgmt v17)
date_closed is Optional — field availability varies by OCA version.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CustomerTicket(BaseModel):
    ticket_id: int
    number: str = ""            # ticket reference e.g. "HT00001" (_rec_name)
    name: str
    description: str = ""
    partner_id: Optional[int] = None
    partner_name: str = ""
    stage_name: str = ""
    priority: str = "0"         # "0" low | "1" medium | "2" high | "3" very high
    user_id: Optional[int] = None
    user_name: str = ""
    create_date: datetime
    # OCA helpdesk_mgmt v17 close fields
    closed_date: Optional[datetime] = None     # field: closed_date
    closed: bool = False                        # field: closed (boolean)
    last_stage_update: Optional[datetime] = None
