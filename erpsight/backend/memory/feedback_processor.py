"""
memory/feedback_processor.py

Processes user feedback (approve/reject outcomes) and stores resolved
incidents in FAISS for future similarity matching.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from erpsight.backend.memory import faiss_store
from erpsight.backend.models.incident_record import IncidentRecord
from erpsight.backend.services import firebase_store

logger = logging.getLogger(__name__)


def record_outcome(
    event_id: str,
    report_id: str,
    outcome: str,
    actions_taken: List[str],
    user_feedback: str = "",
) -> IncidentRecord | None:
    """
    After a pipeline cycle completes (actions executed or approved/rejected),
    store the incident in FAISS for future reference.

    Args:
        event_id:       anomaly event id
        report_id:      insight report id
        outcome:        "resolved" | "false_positive" | "escalated"
        actions_taken:  list of action_type strings that were executed
        user_feedback:  optional reviewer comment

    Returns:
        The IncidentRecord persisted, or None if data not found.
    """
    anomaly = firebase_store.get_anomaly(event_id)
    report = firebase_store.get_report(report_id)

    if anomaly is None or report is None:
        logger.warning("Cannot record outcome — anomaly or report not found")
        return None

    record = IncidentRecord(
        incident_id=f"inc-{uuid.uuid4().hex[:8]}",
        event_id=event_id,
        anomaly_type=anomaly.get("anomaly_type", ""),
        scenario=report.get("scenario", ""),
        summary=report.get("summary", ""),
        outcome=outcome,
        actions_taken=actions_taken,
        user_feedback=user_feedback,
        confidence=report.get("confidence", 0),
    )

    if faiss_store.is_available():
        faiss_store.add_incident(record)
        logger.info("Stored incident %s in FAISS", record.incident_id)
    else:
        logger.info("FAISS unavailable — incident %s recorded locally only", record.incident_id)

    return record
