"""Action log routes."""

from __future__ import annotations

from fastapi import APIRouter

from erpsight.backend.agents import action_agent
from erpsight.backend.services import firebase_store

router = APIRouter()


@router.get("/action-logs")
def list_action_logs():
    return firebase_store.get_all_action_logs()


@router.get("/action-logs/{log_id}")
def get_action_log(log_id: str):
    item = firebase_store.get_action_log(log_id)
    if item is None:
        return {"error": "not_found"}
    return item


@router.post("/action-logs/{log_id}/undo")
def undo_action(log_id: str):
    """
    Hoàn tác action đã thực thi (chỉ với reversible=true trong whitelist).
    Ví dụ: huỷ PO nháp đã tạo, xoá activity task.
    """
    return action_agent.undo_action(log_id)
