"""
detectors/zscore_detector.py

Z-score based demand-spike detector for sales velocity.
Operates on daily order-line quantities per product.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.config.settings import settings
from erpsight.backend.models.anomaly_event import AnomalyEvent, AnomalyType
from erpsight.backend.services import data_service

logger = logging.getLogger(__name__)


def detect(
    client: OdooClient,
    window_days: int = 30,
    threshold: float | None = None,
) -> List[AnomalyEvent]:
    """
    Detect demand spikes by computing Z-score of recent daily sales qty
    per product.

    Returns AnomalyEvent for each product where |Z| >= threshold.
    """
    threshold = threshold or settings.ZSCORE_THRESHOLD
    today = date.today()
    date_from = (today - timedelta(days=window_days)).isoformat()
    date_to = today.isoformat()

    cost_map = client.get_product_cost_map()
    orders = data_service.fetch_orders(client, date_from=date_from, date_to=date_to, cost_map=cost_map)

    # Aggregate daily quantities by product
    daily_qty: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    product_names: Dict[int, str] = {}

    for order in orders:
        d_str = str(order.date_order)[:10]
        for line in order.lines:
            daily_qty[line.product_id][d_str] += line.quantity
            if line.product_name:
                product_names[line.product_id] = line.product_name

    events: List[AnomalyEvent] = []

    for pid, date_map in daily_qty.items():
        values = list(date_map.values())
        if len(values) < 3:
            continue

        import statistics
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 0.001
        if std_val < 0.001:
            continue

        # Use the most recent day as "current"
        sorted_dates = sorted(date_map.keys())
        current_val = date_map[sorted_dates[-1]]
        z = (current_val - mean_val) / std_val

        if abs(z) >= threshold:
            confidence = min(0.9, 0.5 + abs(z) * 0.1)
            events.append(AnomalyEvent(
                event_id=uuid.uuid4().hex[:12],
                anomaly_type=AnomalyType.DEMAND_SPIKE,
                product_id=pid,
                product_name=product_names.get(pid),
                metric="daily_qty",
                metric_value=round(current_val, 2),
                threshold=round(mean_val + threshold * std_val, 2),
                score=round(abs(z), 4),
                z_score=round(z, 4),
                confidence=round(confidence, 3),
                severity="high" if abs(z) > 4 else "medium",
                details={
                    "daily_qty": round(current_val, 2),
                    "mean_daily": round(mean_val, 2),
                    "std_daily": round(std_val, 2),
                    "z_score": round(z, 4),
                    "window_days": window_days,
                },
            ))

    logger.info("zscore_detector: %d demand spikes from %d products", len(events), len(daily_qty))
    return events
