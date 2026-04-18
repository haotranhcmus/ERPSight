"""
detectors/churn_detector.py

Detects VIP customers at risk of churning based on order-cycle analysis.
A customer is flagged when their silence period exceeds
CHURN_OVERDUE_FACTOR × their average order cycle.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.config.settings import settings
from erpsight.backend.models.anomaly_event import AnomalyEvent, AnomalyType
from erpsight.backend.services import data_service

logger = logging.getLogger(__name__)


def detect(
    client: OdooClient,
    window_days: int = 90,
) -> List[AnomalyEvent]:
    """
    Detect VIP customers who stopped ordering beyond their usual cycle.
    """
    overdue_factor = settings.CHURN_OVERDUE_FACTOR
    today = date.today()
    date_from = (today - timedelta(days=window_days)).isoformat()

    orders = data_service.fetch_orders(client, date_from=date_from, date_to=today.isoformat())

    # Aggregate order dates per customer
    customer_dates: Dict[int, List[date]] = defaultdict(list)
    customer_names: Dict[int, str] = {}

    for order in orders:
        d = order.date_order
        if isinstance(d, datetime):
            d = d.date()
        elif isinstance(d, str):
            d = date.fromisoformat(str(d)[:10])
        customer_dates[order.partner_id].append(d)
        if order.partner_name:
            customer_names[order.partner_id] = order.partner_name

    events: List[AnomalyEvent] = []

    for partner_id, dates in customer_dates.items():
        if len(dates) < 3:
            continue

        sorted_dates = sorted(set(dates))
        gaps = [
            (sorted_dates[i + 1] - sorted_dates[i]).days
            for i in range(len(sorted_dates) - 1)
        ]
        avg_cycle = sum(gaps) / len(gaps) if gaps else 30

        last_order = sorted_dates[-1]
        days_silent = (today - last_order).days

        if avg_cycle < 1:
            continue

        overdue_ratio = days_silent / avg_cycle

        if overdue_ratio >= overdue_factor:
            confidence = min(0.9, 0.5 + (overdue_ratio - 1) * 0.15)
            events.append(AnomalyEvent(
                event_id=uuid.uuid4().hex[:12],
                anomaly_type=AnomalyType.VIP_CHURN,
                partner_id=partner_id,
                partner_name=customer_names.get(partner_id),
                metric="overdue_factor",
                metric_value=round(overdue_ratio, 2),
                threshold=overdue_factor,
                score=round(overdue_ratio, 4),
                z_score=0.0,
                confidence=round(confidence, 3),
                severity="high" if overdue_ratio > 2 else "medium",
                details={
                    "days_silent": days_silent,
                    "avg_order_cycle_days": round(avg_cycle, 1),
                    "last_order_date": last_order.isoformat(),
                    "overdue_factor": round(overdue_ratio, 2),
                    "order_count": len(sorted_dates),
                },
            ))

    logger.info("churn_detector: %d VIP churn risks", len(events))
    return events
