"""
agents/sentinel_agent.py

Agent 1 — SentinelAgent (Detection).
Wraps the individual detectors and produces a unified List[AnomalyEvent].
"""

from __future__ import annotations

import logging
from typing import List

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.detectors import (
    churn_detector,
    isolation_forest,
    margin_risk_detector,
    stockout_detector,
    zscore_detector,
)
from erpsight.backend.models.anomaly_event import AnomalyEvent

logger = logging.getLogger(__name__)


class SentinelAgent:
    """
    Agent 1 — run all detectors and return a combined anomaly list.

    Each detector is independent and returns List[AnomalyEvent].
    Failures in one detector do not block the others.
    """

    def __init__(self, client: OdooClient) -> None:
        self._client = client

    def run(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> List[AnomalyEvent]:
        """Execute all detectors and merge results."""
        all_events: List[AnomalyEvent] = []

        # 1. Z-score demand spike
        try:
            events = zscore_detector.detect(self._client)
            all_events.extend(events)
            logger.info("zscore_detector → %d events", len(events))
        except Exception:
            logger.exception("zscore_detector failed")

        # 2. Stockout risk
        try:
            events = stockout_detector.detect(self._client)
            all_events.extend(events)
            logger.info("stockout_detector → %d events", len(events))
        except Exception:
            logger.exception("stockout_detector failed")

        # 3. Margin erosion
        try:
            events = margin_risk_detector.detect(self._client)
            all_events.extend(events)
            logger.info("margin_risk_detector → %d events", len(events))
        except Exception:
            logger.exception("margin_risk_detector failed")

        # 4. VIP churn
        try:
            events = churn_detector.detect(self._client)
            all_events.extend(events)
            logger.info("churn_detector → %d events", len(events))
        except Exception:
            logger.exception("churn_detector failed")

        # 5. Isolation Forest (multivariate)
        try:
            events = isolation_forest.detect(self._client)
            all_events.extend(events)
            logger.info("isolation_forest → %d events", len(events))
        except Exception:
            logger.exception("isolation_forest failed")

        logger.info("SentinelAgent total: %d anomaly events", len(all_events))
        return all_events
