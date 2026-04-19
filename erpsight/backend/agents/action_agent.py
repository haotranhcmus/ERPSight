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
from typing import Any, Dict, List, Optional

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
        "create_helpdesk_ticket": create_activity_task.execute_helpdesk_ticket,
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


# Confidence dưới ngưỡng này → chỉ hiển thị text đề xuất, không thực thi Odoo
ADVISORY_CONFIDENCE_THRESHOLD = 0.45


def process(report: InsightReport) -> ActionResult:
    """
    Chọn DUY NHẤT action ưu tiên cao nhất từ report, sau đó:
      1. Validate against whitelist
      2. Nếu confidence thấp → advisory only (text + acknowledge, không thực thi)
      3. Nếu informational_only → auto-execute + resolve ngay
      4. Nếu requires_approval → queue cho người dùng duyệt
    """
    whitelist = _load_whitelist()
    result = ActionResult()

    if not report.recommended_actions:
        return result

    # Chỉ xử lý 1 action: ưu tiên thấp nhất (priority=1 > priority=2)
    action = min(report.recommended_actions, key=lambda a: a.priority)
    action_type = action.action_type
    wl_entry = whitelist.get(action_type)

    # ── Unknown action → skip ─────────────────────────────────────────
    if wl_entry is None:
        logger.warning("Action '%s' not in whitelist — skipped", action_type)
        result.skipped.append({"action_type": action_type, "reason": "not_in_whitelist"})
        return result

    risk = wl_entry.get("risk_level", "high")
    requires_approval = wl_entry.get("requires_approval", False)
    min_conf = wl_entry.get("auto_execute_min_confidence")
    informational_only = wl_entry.get("informational_only", False)

    # ── Low confidence → advisory only ───────────────────────────────
    # Không thực thi Odoo, chỉ hiển thị text đề xuất để người dùng xem xét
    if report.confidence < ADVISORY_CONFIDENCE_THRESHOLD and not informational_only:
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
            advisory_only=True,
        )
        firebase_store.save_approval_item(approval_id, item.model_dump(mode="json"))
        result.queued_for_approval.append(item)
        logger.info("Advisory-only item created for %s (conf=%.2f < %.2f)", action_type, report.confidence, ADVISORY_CONFIDENCE_THRESHOLD)
        return result

    # ── Decide auto vs queue ──────────────────────────────────────────
    can_auto = (
        informational_only
        or (
            not requires_approval
            and risk == "low"
            and min_conf is not None
            and report.confidence >= min_conf
        )
    )

    if can_auto:
        # ── Auto-execute + resolve immediately ────────────────────────
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

        # Resolve ngay sau auto-execute thành công
        if success:
            firebase_store.resolve_anomaly(report.event_id, log_id, "auto_executed")

    else:
        # ── Queue for human approval ──────────────────────────────────
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
    Người dùng duyệt một queued action.

    - advisory_only=True: không thực thi Odoo, chỉ ghi nhận đã xem xét
    - advisory_only=False: thực thi và resolve với resolution_type="user_approved"
    """
    item_data = firebase_store.get_approval_item(approval_id)
    if item_data is None:
        return {"success": False, "error": "Approval item not found"}

    item = ApprovalItem(**item_data)
    if item.status != ApprovalStatus.PENDING:
        return {"success": False, "error": f"Item already {item.status}"}

    # ── Advisory-only: acknowledge without executing ──────────────────
    if item.advisory_only:
        firebase_store.update_approval_item(approval_id, {
            "status": ApprovalStatus.APPROVED.value,
            "reviewed_by": reviewer,
        })
        log_id = f"log-{uuid.uuid4().hex[:8]}"
        log_entry = ActionLog(
            log_id=log_id,
            event_id=item.event_id,
            report_id=item.report_id,
            action_type=item.action_type,
            params=item.params,
            auto_executed=False,
            success=True,
            result={"advisory": True, "message": "Đã xem xét đề xuất, không thực thi Odoo"},
        )
        firebase_store.save_action_log(log_id, log_entry.model_dump(mode="json"))
        firebase_store.resolve_anomaly(item.event_id, log_id, "advisory_acknowledged")
        logger.info("Advisory acknowledged for %s (event=%s)", item.action_type, item.event_id)
        return {"success": True, "log_id": log_id, "advisory": True}

    # ── Normal execution ──────────────────────────────────────────────
    try:
        exec_result = _execute_action(item.action_type, item.params)
        success = exec_result.get("success", True)
    except Exception as exc:
        logger.exception("Executor error for %s", item.action_type)
        exec_result = {"success": False, "error": str(exc)}
        success = False

    new_status = ApprovalStatus.APPROVED if success else ApprovalStatus.FAILED
    firebase_store.update_approval_item(approval_id, {
        "status": new_status.value,
        "reviewed_by": reviewer,
    })

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

    if success:
        firebase_store.resolve_anomaly(item.event_id, log_id, "user_approved")
        logger.info("Approved & executed %s → resolved=user_approved (event=%s)", item.action_type, item.event_id)

    return {"success": success, "log_id": log_id, "result": exec_result}


def reject(approval_id: str, reviewer: str = "admin", reason: str = "") -> Dict[str, Any]:
    """
    Người dùng từ chối đề xuất.
    Anomaly vẫn chuyển sang resolved với resolution_type="user_rejected"
    để lịch sử theo dõi được đầy đủ.
    """
    item_data = firebase_store.get_approval_item(approval_id)
    if item_data is None:
        return {"success": False, "error": "Approval item not found"}

    firebase_store.update_approval_item(approval_id, {
        "status": ApprovalStatus.REJECTED.value,
        "reviewed_by": reviewer,
        "reject_reason": reason,
    })

    event_id = item_data.get("event_id", "")
    if event_id:
        firebase_store.resolve_anomaly(event_id, None, "user_rejected")
        logger.info("Rejected %s → resolved=user_rejected (event=%s)", item_data.get("action_type"), event_id)

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


# ── Undo / Fallback ───────────────────────────────────────────────────────────

def undo_action(log_id: str) -> Dict[str, Any]:
    """
    Hoàn tác một action đã thực thi (nếu whitelist đánh dấu reversible=true).

    Quy trình:
    1. Tải ActionLog
    2. Kiểm tra whitelist có undo_handler không
    3. Gọi undo handler tương ứng
    4. Đánh dấu log.undone = True
    5. Nếu anomaly đã resolved → đặt lại thành active
    """
    log_data = firebase_store.get_action_log(log_id)
    if not log_data:
        return {"success": False, "error": "Action log not found"}

    if log_data.get("undone"):
        return {"success": False, "error": "Action đã được hoàn tác trước đó"}

    if not log_data.get("success"):
        return {"success": False, "error": "Không thể hoàn tác action đã thất bại"}

    wl = _load_whitelist()
    action_type = log_data.get("action_type", "")
    wl_entry = wl.get(action_type, {})

    if not wl_entry.get("reversible"):
        return {"success": False, "error": f"Action '{action_type}' không hỗ trợ hoàn tác"}

    undo_handler = wl_entry.get("undo_handler")
    record_id = log_data.get("undo_record_id")

    if not record_id:
        return {"success": False, "error": "Không có record_id để hoàn tác (action có thể là chatter note)"}

    result = _execute_undo(undo_handler, record_id)
    if result.get("success"):
        firebase_store.update_action_log(log_id, {"undone": True})
        # Nếu anomaly đã resolved, đặt lại active để user có thể xử lý lại
        event_id = log_data.get("event_id", "")
        if event_id:
            anomaly = firebase_store.get_anomaly(event_id)
            if anomaly and anomaly.get("status") == "resolved":
                firebase_store.update_anomaly(event_id, {
                    "status": "active",
                    "resolved_at": None,
                    "resolved_by_log_id": None,
                    "resolution_type": None,
                })
                logger.info("Anomaly %s reopened after undo of log %s", event_id, log_id)
        logger.info("Undo successful for log %s (handler=%s)", log_id, undo_handler)

    return result


def _execute_undo(undo_handler: Optional[str], record_id: Any) -> Dict[str, Any]:
    """Dispatch to correct undo handler."""
    if not undo_handler:
        return {"success": False, "error": "Không có undo handler"}

    from erpsight.backend.adapters.odoo_client import OdooClient
    client = OdooClient()

    try:
        if undo_handler == "cancel_purchase_order":
            ok = client.cancel_purchase_order(int(record_id))
            return {"success": ok, "message": f"PO #{record_id} đã bị huỷ"}

        elif undo_handler == "delete_activity":
            client.execute_kw("mail.activity", "unlink", [[int(record_id)]])
            return {"success": True, "message": f"Activity #{record_id} đã được xoá"}

        elif undo_handler == "remove_flag_note":
            # mail.message không thể xoá qua XML-RPC nên post note correction
            return {
                "success": False,
                "error": "Chatter note không thể xoá qua API — vui lòng xoá thủ công trong Odoo",
            }

        else:
            return {"success": False, "error": f"Undo handler '{undo_handler}' chưa được triển khai"}

    except Exception as exc:
        logger.exception("Undo handler %s failed", undo_handler)
        return {"success": False, "error": str(exc)}
