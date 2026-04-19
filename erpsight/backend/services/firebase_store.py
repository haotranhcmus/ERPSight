"""
services/firebase_store.py

Persistence layer for ERPSight.

When FIREBASE_CREDENTIALS_PATH is set in .env, uses Google Cloud Firestore
so data survives server restarts.  Otherwise falls back to an in-memory dict.

Firebase setup (one-time):
  1. Go to https://console.firebase.google.com → create a project
  2. Project Settings → Service accounts → Generate new private key → save JSON
  3. Set FIREBASE_CREDENTIALS_PATH=/absolute/path/to/service-account.json in .env
  4. (Optional) Set FIREBASE_PROJECT_ID=<your-project-id> in .env
  5. In Firebase console: Firestore Database → Create database (production mode)
  6. Restart the backend — "Firestore initialized" will appear in logs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Firestore client (lazy init) ──────────────────────────────────────────────

_db = None
_firestore_ready = False


def _init_firestore() -> bool:
    """Try to initialise Firebase Admin SDK + Firestore client. Idempotent."""
    global _db, _firestore_ready
    if _firestore_ready:
        return True
    try:
        from erpsight.backend.config.settings import settings  # local import to avoid circular
        creds_path = settings.FIREBASE_CREDENTIALS_PATH
        if not creds_path:
            return False
        import firebase_admin
        from firebase_admin import credentials, firestore as fs
        if not firebase_admin._apps:
            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
        _db = fs.client()
        _firestore_ready = True
        logger.info("Firestore initialized — data will persist across restarts")
        return True
    except Exception:
        logger.exception("Failed to initialize Firestore — using in-memory fallback")
        return False


# ── In-memory fallback ────────────────────────────────────────────────────────

_in_memory: Dict[str, Dict[str, Any]] = {
    "anomalies": {},
    "insight_reports": {},
    "approval_queue": {},
    "action_log": {},
}


# ── Generic CRUD helpers ──────────────────────────────────────────────────────

def _col(name: str):
    return _db.collection(name)


def _fs_save(collection: str, doc_id: str, data: Dict[str, Any]) -> None:
    _col(collection).document(doc_id).set(data)


def _fs_get(collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
    doc = _col(collection).document(doc_id).get()
    return doc.to_dict() if doc.exists else None


def _fs_get_all(collection: str) -> List[Dict[str, Any]]:
    return [d.to_dict() for d in _col(collection).stream()]


def _fs_update(collection: str, doc_id: str, patch: Dict[str, Any]) -> None:
    _col(collection).document(doc_id).update(patch)


# ── Anomalies ─────────────────────────────────────────────────────────────────

def save_anomaly(event_id: str, data: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_save("anomalies", event_id, data)
    else:
        _in_memory["anomalies"][event_id] = data


def get_anomaly(event_id: str) -> Optional[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get("anomalies", event_id)
    return _in_memory["anomalies"].get(event_id)


def get_all_anomalies() -> List[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get_all("anomalies")
    return list(_in_memory["anomalies"].values())


def update_anomaly(event_id: str, patch: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_update("anomalies", event_id, patch)
    elif event_id in _in_memory["anomalies"]:
        _in_memory["anomalies"][event_id].update(patch)


def find_active_anomaly(
    anomaly_type: str,
    product_id: Optional[int] = None,
    partner_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Tìm anomaly đang ACTIVE (chưa xử lý) cùng type + entity.
    Dùng để chống spam: nếu đã có active anomaly cho cùng sản phẩm/khách,
    pipeline không tạo thêm record mới.
    """
    for anomaly in get_all_anomalies():
        # Bỏ qua record đã resolved/dismissed (cho phép tạo mới nếu issue tái hiện)
        if anomaly.get("status") in ("resolved", "dismissed"):
            continue
        if anomaly.get("anomaly_type") != anomaly_type:
            continue
        if product_id is not None and anomaly.get("product_id") == product_id:
            return anomaly
        if partner_id is not None and anomaly.get("partner_id") == partner_id:
            return anomaly
    return None


def resolve_anomaly(event_id: str, log_id: Optional[str], resolution_type: str) -> None:
    """
    Đánh dấu anomaly đã xử lý xong.

    resolution_type values:
      "auto_executed"         — AI tự động thực thi
      "user_approved"         — Người dùng duyệt & thực thi
      "user_rejected"         — Người dùng từ chối đề xuất
      "advisory_acknowledged" — Đề xuất văn bản đã được xem xét
    """
    from datetime import datetime
    update_anomaly(event_id, {
        "status": "resolved",
        "resolved_at": datetime.utcnow().isoformat(),
        "resolved_by_log_id": log_id,
        "resolution_type": resolution_type,
    })


# ── Insight Reports ───────────────────────────────────────────────────────────

def save_report(report_id: str, data: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_save("insight_reports", report_id, data)
    else:
        _in_memory["insight_reports"][report_id] = data


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get("insight_reports", report_id)
    return _in_memory["insight_reports"].get(report_id)


def get_all_reports() -> List[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get_all("insight_reports")
    return list(_in_memory["insight_reports"].values())


# ── Approval Queue ────────────────────────────────────────────────────────────

def save_approval_item(approval_id: str, data: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_save("approval_queue", approval_id, data)
    else:
        _in_memory["approval_queue"][approval_id] = data


def get_approval_item(approval_id: str) -> Optional[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get("approval_queue", approval_id)
    return _in_memory["approval_queue"].get(approval_id)


def get_all_approval_items() -> List[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get_all("approval_queue")
    return list(_in_memory["approval_queue"].values())


def update_approval_item(approval_id: str, patch: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_update("approval_queue", approval_id, patch)
    elif approval_id in _in_memory["approval_queue"]:
        _in_memory["approval_queue"][approval_id].update(patch)


# ── Action Log ────────────────────────────────────────────────────────────────

def save_action_log(log_id: str, data: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_save("action_log", log_id, data)
    else:
        _in_memory["action_log"][log_id] = data


def get_action_log(log_id: str) -> Optional[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get("action_log", log_id)
    return _in_memory["action_log"].get(log_id)


def get_all_action_logs() -> List[Dict[str, Any]]:
    if _init_firestore():
        return _fs_get_all("action_log")
    return list(_in_memory["action_log"].values())


def update_action_log(log_id: str, patch: Dict[str, Any]) -> None:
    if _init_firestore():
        _fs_update("action_log", log_id, patch)
    elif log_id in _in_memory["action_log"]:
        _in_memory["action_log"][log_id].update(patch)


# ── Utilities ─────────────────────────────────────────────────────────────────

def clear_all() -> None:
    """Wipe all in-memory data (used by reset-demo endpoint)."""
    for collection in _in_memory.values():
        collection.clear()
    logger.info("firebase_store: all data cleared")
