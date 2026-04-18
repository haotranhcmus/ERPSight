"""
agents/action_agent.py

Agent 3 — ActionAgent (Execution Gating).

Consumes InsightReport.recommended_actions, validates each against
whitelist.json, and either auto-executes (low-risk + high confidence)
or queues for human approval.

Results are persisted to firebase_store (approval_queue + action_log).
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List

from erpsight.backend.models.action_log import ActionLog
from erpsight.backend.models.approval_item import ApprovalItem, ApprovalStatus
from erpsight.backend.models.insight_report import InsightReport, RecommendedAction
from erpsight.backend.services import firebase_store

logger = logging.getLogger(__name__)

_WHITELIST_PATH = Path(__file__).resolve().parent.parent / "config" / "whitelist.json"


def _load_whitelist() -> Dict[str, Any]:
    try:
        with open(_WHITELIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load whitelist.json")
        return {}


# ── Executor dispatch ─────────────────────────────────────────────────────────

def _execute_action(action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Route to the correct executor module and run."""
    from erpsight.backend.executor import (
        create_activity_task,
        create_draft_po,
        send_internal_alert,
    )

    _DISPATCH = {
        "send_internal_alert": send_internal_alert.execute,
        "send_margin_alert": send_internal_alert.execute_margin_alert,
        "send_churn_risk_alert": send_internal_alert.execute_churn_alert,
        "create_activity_task": create_activity_task.execute,
        "create_reengagement_activity": create_activity_task.execute_reengagement,
        "flag_product_for_price_review": send_internal_alert.execute_flag_review,
        "create_purchase_order": create_draft_po.execute,
        "update_sale_price": create_draft_po.execute_update_price,
    }

    handler = _DISPATCH.get(action_type)
    if handler is None:
        return {"success": False, "error": f"No executor for action '{action_type}'"}

    return handler(params)


# ── Public API ────────────────────────────────────────────────────────────────


class ActionResult:
    """Summary returned to the pipeline after processing all actions."""

    def __init__(self) -> None:
        self.auto_executed: List[ActionLog] = []
        self.queued_for_approval: List[ApprovalItem] = []
        self.skipped: List[Dict[str, str]] = []


def process(report: InsightReport) -> ActionResult:
    """
    For each RecommendedAction in the report:
      1. Validate against whitelist
      2. Decide auto-execute vs queue
      3. Persist results
    """
    whitelist = _load_whitelist()
    result = ActionResult()

    for action in report.recommended_actions:
        action_type = action.action_type
        wl_entry = whitelist.get(action_type)

        # ── Unknown action → skip ─────────────────────────────────────
        if wl_entry is None:
            logger.warning("Action '%s' not in whitelist — skipped", action_type)
            result.skipped.append({"action_type": action_type, "reason": "not_in_whitelist"})
            continue

        risk = wl_entry.get("risk_level", "high")
        requires_approval = wl_entry.get("requires_approval", False)
        min_conf = wl_entry.get("auto_execute_min_confidence")

        can_auto = (
            not requires_approval
            and risk == "low"
            and min_conf is not None
            and report.confidence >= min_conf
        )

        if can_auto:
            # ── Auto-execute ──────────────────────────────────────────
            log_id = f"log-{uuid.uuid4().hex[:8]}"
            try:
                exec_result = _execute_action(action_type, action.params)
                success = exec_result.get("success", True)
                error_msg = exec_result.get("error")
            except Exception as exc:
                logger.exception("Executor error for %s", action_type)
                success = False
                exec_result = {}
                error_msg = str(exc)

            log_entry = ActionLog(
                log_id=log_id,
                event_id=report.event_id,
                report_id=report.report_id,
                action_type=action_type,
                params=action.params,
                auto_executed=True,
                success=success,
                result=exec_result,
                error_message=error_msg,
                undo_record_id=exec_result.get("record_id"),
            )
            firebase_store.save_action_log(log_id, log_entry.model_dump(mode="json"))
            result.auto_executed.append(log_entry)
            logger.info("Auto-executed %s → success=%s", action_type, success)

        else:
            # ── Queue for approval ────────────────────────────────────
            approval_id = f"apv-{uuid.uuid4().hex[:8]}"
            item = ApprovalItem(
                approval_id=approval_id,
                event_id=report.event_id,
                report_id=report.report_id,
                action_type=action_type,
                params=action.params,
                risk_level=risk,
                confidence=report.confidence,
                reason=action.reason,
                summary=report.summary,
            )
            firebase_store.save_approval_item(approval_id, item.model_dump(mode="json"))
            result.queued_for_approval.append(item)
            logger.info("Queued %s for approval (risk=%s, conf=%.2f)", action_type, risk, report.confidence)

    return result


def approve_and_execute(approval_id: str, reviewer: str = "admin") -> Dict[str, Any]:
    """
    Called by the API when a human approves a queued action.
    Executes then logs the result.
    """
    item_data = firebase_store.get_approval_item(approval_id)
    if item_data is None:
        return {"success": False, "error": "Approval item not found"}

    item = ApprovalItem(**item_data)
    if item.status != ApprovalStatus.PENDING:
        return {"success": False, "error": f"Item already {item.status}"}

    # Execute
    exec_result = _execute_action(item.action_type, item.params)
    success = exec_result.get("success", True)

    # Update approval status — FAILED if executor returned success=False
    new_status = ApprovalStatus.APPROVED if success else ApprovalStatus.FAILED
    firebase_store.update_approval_item(approval_id, {
        "status": new_status.value,
        "reviewed_by": reviewer,
    })

    # Log
    log_id = f"log-{uuid.uuid4().hex[:8]}"
    log_entry = ActionLog(
        log_id=log_id,
        event_id=item.event_id,
        report_id=item.report_id,
        action_type=item.action_type,
        params=item.params,
        auto_executed=False,
        success=success,
        result=exec_result,
        error_message=exec_result.get("error"),
        undo_record_id=exec_result.get("record_id"),
    )
    firebase_store.save_action_log(log_id, log_entry.model_dump(mode="json"))
    return {"success": success, "log_id": log_id, "result": exec_result}


def reject(approval_id: str, reviewer: str = "admin", reason: str = "") -> Dict[str, Any]:
    """Mark queued action as rejected."""
    item_data = firebase_store.get_approval_item(approval_id)
    if item_data is None:
        return {"success": False, "error": "Approval item not found"}

    firebase_store.update_approval_item(approval_id, {
        "status": ApprovalStatus.REJECTED.value,
        "reviewed_by": reviewer,
        "reject_reason": reason,
    })
    return {"success": True, "approval_id": approval_id}


def update_approval_params(approval_id: str, params_patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Overwrite (merge) params on a PENDING approval item before it is approved.
    Only PENDING items can be edited.
    """
    item_data = firebase_store.get_approval_item(approval_id)
    if item_data is None:
        return {"success": False, "error": "Approval item not found"}

    item = ApprovalItem(**item_data)
    if item.status != ApprovalStatus.PENDING:
        return {"success": False, "error": f"Cannot edit — item already {item.status}"}

    merged = {**item.params, **params_patch}
    firebase_store.update_approval_item(approval_id, {"params": merged})
    logger.info("Params updated for approval %s: %s", approval_id, list(params_patch.keys()))
    return {"success": True, "approval_id": approval_id, "params": merged}
