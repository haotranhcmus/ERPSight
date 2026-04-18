"""
services/pipeline.py

Orchestrates the 3-agent pipeline:
    SentinelAgent (detect) → InsightAgent (analyze) → ActionAgent (execute/queue)

Persists results at each step via firebase_store.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.agents import action_agent, insight_agent
from erpsight.backend.agents.sentinel_agent import SentinelAgent
from erpsight.backend.models.anomaly_event import AnomalyEvent
from erpsight.backend.models.insight_report import InsightReport
from erpsight.backend.services import firebase_store

logger = logging.getLogger(__name__)


def run_full_pipeline() -> Dict[str, Any]:
    """
    Execute the full detect → analyze → act pipeline.

    Returns a summary dict with counts and details suitable for API response.
    """
    client = OdooClient()

    # ── Step 1: Detection ─────────────────────────────────────────────────
    sentinel = SentinelAgent(client)
    events: List[AnomalyEvent] = sentinel.run()
    logger.info("Pipeline Step 1: %d anomaly events detected", len(events))

    # Persist events
    for ev in events:
        firebase_store.save_anomaly(ev.event_id, ev.model_dump(mode="json"))

    # ── Step 2: Analysis ──────────────────────────────────────────────────
    reports: List[InsightReport] = []
    for ev in events:
        try:
            report = insight_agent.analyze(ev)
            reports.append(report)
            firebase_store.save_report(report.report_id, report.model_dump(mode="json"))
        except Exception:
            logger.exception("InsightAgent failed for event %s", ev.event_id)

    logger.info("Pipeline Step 2: %d insight reports generated", len(reports))

    # ── Step 3: Action gating ─────────────────────────────────────────────
    total_auto = 0
    total_queued = 0
    total_skipped = 0
    for report in reports:
        try:
            result = action_agent.process(report)
            total_auto += len(result.auto_executed)
            total_queued += len(result.queued_for_approval)
            total_skipped += len(result.skipped)
        except Exception:
            logger.exception("ActionAgent failed for report %s", report.report_id)

    logger.info(
        "Pipeline Step 3: %d auto-executed, %d queued, %d skipped",
        total_auto, total_queued, total_skipped,
    )

    return {
        "anomalies_detected": len(events),
        "reports_generated": len(reports),
        "actions_auto_executed": total_auto,
        "actions_queued_for_approval": total_queued,
        "actions_skipped": total_skipped,
    }
