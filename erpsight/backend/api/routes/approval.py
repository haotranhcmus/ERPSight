"""Approval queue routes — list, approve, reject, patch params."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel
from fastapi import APIRouter

from erpsight.backend.agents import action_agent
from erpsight.backend.services import firebase_store
from erpsight.backend.agents.action_agent import _load_whitelist

router = APIRouter()


@router.get("/approvals")
def list_approvals():
    return firebase_store.get_all_approval_items()


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: str):
    item = firebase_store.get_approval_item(approval_id)
    if item is None:
        return {"error": "not_found"}
    # Attach editable_fields from whitelist so the UI knows what to render
    wl = _load_whitelist()
    entry = wl.get(item.get("action_type"), {})
    panel = entry.get("approval_panel", {})
    item["editable_fields"] = panel.get("editable_fields", [])
    item["panel_title"] = panel.get("title", "")
    item["panel_warning"] = panel.get("warning", "")
    return item


class ApproveRequest(BaseModel):
    reviewer: str = "admin"


class RejectRequest(BaseModel):
    reviewer: str = "admin"
    reason: str = ""


class PatchParamsRequest(BaseModel):
    params: Dict[str, Any]


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, body: ApproveRequest):
    return action_agent.approve_and_execute(approval_id, reviewer=body.reviewer)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, body: RejectRequest):
    return action_agent.reject(approval_id, reviewer=body.reviewer, reason=body.reason)


@router.patch("/approvals/{approval_id}/params")
def patch_params(approval_id: str, body: PatchParamsRequest):
    """Edit params of a PENDING approval before approving."""
    return action_agent.update_approval_params(approval_id, body.params)
