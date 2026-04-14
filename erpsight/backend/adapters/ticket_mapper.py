"""
backend/adapters/ticket_mapper.py

Maps raw Odoo helpdesk.ticket dicts → CustomerTicket domain model.
Compatible with OCA helpdesk_mgmt v17.

date_closed may be absent depending on OCA version — handled gracefully.

Usage:
    from erpsight.backend.adapters.ticket_mapper import map_tickets
    tickets = map_tickets(raw_tickets)
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List

from erpsight.backend.adapters.mapper_utils import m2o_id as _m2o_id
from erpsight.backend.adapters.mapper_utils import m2o_name as _m2o_name
from erpsight.backend.adapters.mapper_utils import parse_dt as _parse_dt
from erpsight.backend.models.domain.customer_ticket import CustomerTicket


def map_ticket(raw: Dict[str, Any]) -> CustomerTicket:
    create_dt = _parse_dt(raw.get("create_date")) or datetime.now()
    close_dt = _parse_dt(raw.get("closed_date"))
    last_stage_dt = _parse_dt(raw.get("last_stage_update"))

    return CustomerTicket(
        ticket_id=int(raw["id"]),
        number=raw.get("number") or "",
        name=raw.get("name") or "",
        description=raw.get("description") or "",
        partner_id=_m2o_id(raw.get("partner_id")),
        partner_name=_m2o_name(raw.get("partner_id")),
        stage_name=_m2o_name(raw.get("stage_id")),
        priority=str(raw.get("priority") or "0"),
        user_id=_m2o_id(raw.get("user_id")),
        user_name=_m2o_name(raw.get("user_id")),
        create_date=create_dt,
        closed_date=close_dt,
        closed=bool(raw.get("closed") or False),
        last_stage_update=last_stage_dt,
    )


def map_tickets(raw_list: List[Dict[str, Any]]) -> List[CustomerTicket]:
    """
    Map a batch of helpdesk.ticket records to CustomerTicket domain models.

    Args:
        raw_list: list of dicts from OdooClient.get_helpdesk_tickets()
    """
    return [map_ticket(raw) for raw in raw_list]
