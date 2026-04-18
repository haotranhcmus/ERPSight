"""Action log routes."""

from __future__ import annotations

from fastapi import APIRouter

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
