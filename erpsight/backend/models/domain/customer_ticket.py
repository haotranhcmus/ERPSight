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
    name: str
    description: str = ""
    partner_id: Optional[int] = None
    partner_name: str = ""
    stage_id: Optional[int] = None
    stage_name: str = ""
    priority: str = "0"         # "0" normal | "1" high | "2" very high | "3" critical
    user_id: Optional[int] = None
    user_name: str = ""
    team_id: Optional[int] = None
    team_name: str = ""
    create_date: datetime
    # OCA helpdesk_mgmt v17 close fields
    closed_date: Optional[datetime] = None     # field: closed_date
    closed: bool = False                        # field: closed (boolean)
    last_stage_update: Optional[datetime] = None
    resolution_days: Optional[float] = None    # computed: (closed_date - create_date) in days
