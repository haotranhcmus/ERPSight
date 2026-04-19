"""
executor/create_activity_task.py

Executor for activity-based actions:
  - create_activity_task         → generic mail.activity on any model
  - create_reengagement_activity → Phone Call activity on res.partner
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from erpsight.backend.adapters.odoo_client import OdooClient

logger = logging.getLogger(__name__)

_client: OdooClient | None = None


def _get_client() -> OdooClient:
    global _client
    if _client is None:
        _client = OdooClient()
    return _client


def _resolve_record_id(model: str, lookup: Dict[str, str], product_id: int | None = None) -> int | None:
    client = _get_client()

    # Support direct product.product → product.template lookup
    if product_id and model == "product.template":
        pp = client.search_read(
            "product.product", [("id", "=", product_id)], ["product_tmpl_id"], limit=1,
        )
        if pp and pp[0].get("product_tmpl_id"):
            return int(pp[0]["product_tmpl_id"][0])

    field = lookup.get("field", "name")
    value = lookup.get("value", "")
    if not value:
        return None
    records = client.search_read(model, [(field, "=", value)], ["id"], limit=1)
    return records[0]["id"] if records else None


def _resolve_user_id(login: str) -> int | None:
    client = _get_client()
    records = client.search_read("res.users", [("login", "=", login)], ["id"], limit=1)
    return records[0]["id"] if records else None


def _resolve_partner_id(name: str) -> int | None:
    client = _get_client()
    records = client.search_read("res.partner", [("name", "ilike", name)], ["id"], limit=1)
    return records[0]["id"] if records else None


# ── create_activity_task ──────────────────────────────────────────────────────

def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a mail.activity (To-Do / task) on an Odoo record."""
    client = _get_client()
    model = params.get("res_model", "product.template")
    lookup = params.get("res_id_lookup", {})
    product_id_override = params.get("_odoo_product_id")
    res_id = _resolve_record_id(model, lookup, product_id=product_id_override)
    if res_id is None:
        return {"success": False, "error": f"Cannot resolve record: {lookup}"}

    user_id = _resolve_user_id(params.get("assigned_to_login", "admin"))

    activity_id = client.create_activity(
        model=model,
        res_id=res_id,
        summary=params.get("summary", ""),
        note=params.get("note", ""),
        date_deadline=params.get("date_deadline"),
        user_id=user_id,
    )
    return {"success": True, "record_id": activity_id}


# ── create_reengagement_activity ──────────────────────────────────────────────

def execute_reengagement(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Phone Call activity on res.partner for VIP re-engagement."""
    client = _get_client()
    partner_name = params.get("partner_name", "")
    partner_id = _resolve_partner_id(partner_name)
    if partner_id is None:
        return {"success": False, "error": f"Partner '{partner_name}' not found"}

    user_id = _resolve_user_id(params.get("assigned_to_login", "admin"))

    note_parts = [
        params.get("note", ""),
        f"Don hang cuoi: {params.get('last_order_date', 'N/A')}",
        f"Im lang: {params.get('silent_days', 0)} ngay",
    ]
    if params.get("has_recent_complaint"):
        note_parts.append("Co khieu nai gan day — can xu ly truoc khi goi.")
    if params.get("suggested_offer"):
        note_parts.append(f"Goi y uu dai: {params['suggested_offer']}")

    full_note = "\n".join(note_parts)

    activity_id = client.create_activity(
        model="res.partner",
        res_id=partner_id,
        summary=params.get("summary", f"Re-engage VIP {partner_name}"),
        note=full_note,
        date_deadline=params.get("date_deadline"),
        user_id=user_id,
    )
    return {"success": True, "record_id": activity_id}


# ── create_helpdesk_ticket ───────────────────────────────────────────────────

def execute_helpdesk_ticket(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a helpdesk ticket for VIP churn follow-up (KB3)."""
    client = _get_client()
    partner_name = params.get("partner_name", "")
    partner_id = _resolve_partner_id(partner_name)
    if partner_id is None:
        return {"success": False, "error": f"Partner '{partner_name}' not found"}

    teams = client.search_read("helpdesk.ticket.team", [], ["id"], limit=1)
    team_id = teams[0]["id"] if teams else False

    stages = client.search_read("helpdesk.ticket.stage", [], ["id", "name"])
    stage_id = None
    for s in stages:
        if any(kw in s["name"].lower() for kw in ["new", "open", "in progress"]):
            stage_id = s["id"]
            break
    if stage_id is None and stages:
        stage_id = stages[0]["id"]

    ticket_vals = {
        "name": params.get("ticket_name", f"[ERPSight KB3] Follow-up VIP - {partner_name}"),
        "partner_id": partner_id,
        "description": params.get("description", ""),
        "priority": str(params.get("priority", "1")),
    }
    if team_id:
        ticket_vals["team_id"] = team_id
    if stage_id:
        ticket_vals["stage_id"] = stage_id

    ticket_id = client.execute_kw("helpdesk.ticket", "create", [ticket_vals])
    logger.info("Created helpdesk ticket id=%d for partner '%s'", ticket_id, partner_name)
    return {"success": True, "record_id": ticket_id}
