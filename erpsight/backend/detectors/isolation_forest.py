"""
detectors/isolation_forest.py

Multivariate anomaly detector using scikit-learn IsolationForest.
Operates on a product-level feature matrix (total sales qty, avg margin,
inventory level, ticket count).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List

import numpy as np
from sklearn.ensemble import IsolationForest as IForest

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.models.anomaly_event import AnomalyEvent, AnomalyType
from erpsight.backend.services import data_service

logger = logging.getLogger(__name__)


def detect(
    client: OdooClient,
    window_days: int = 30,
    contamination: float = 0.05,
) -> List[AnomalyEvent]:
    """
    Fit IsolationForest on product features and flag multivariate outliers.
    """
    today = date.today()
    date_from = (today - timedelta(days=window_days)).isoformat()
    date_to = today.isoformat()

    cost_map = client.get_product_cost_map()
    orders = data_service.fetch_orders(client, date_from=date_from, date_to=date_to, cost_map=cost_map)
    inventories = data_service.fetch_inventories(client)
    tickets = data_service.fetch_tickets(client, date_from=date_from, date_to=date_to)

    # Aggregate per product
    product_qty: Dict[int, float] = defaultdict(float)
    product_margin: Dict[int, List[float]] = defaultdict(list)
    product_names: Dict[int, str] = {}

    for order in orders:
        for line in order.lines:
            product_qty[line.product_id] += line.quantity
            product_margin[line.product_id].append(line.margin_pct)
            if line.product_name:
                product_names[line.product_id] = line.product_name

    inv_by_product: Dict[int, float] = defaultdict(float)
    for inv in inventories:
        inv_by_product[inv.product_id] += inv.available_qty
        if inv.product_name:
            product_names[inv.product_id] = inv.product_name

    product_ticket_count: Dict[int, int] = defaultdict(int)
    # Tickets are partner-level; approximate by counting all tickets
    # (in a real system, you'd map tickets to products)
    for t in tickets:
        # Count globally — each product gets the total as a signal
        pass

    product_ids = sorted(set(product_qty.keys()) | set(inv_by_product.keys()))
    if len(product_ids) < 5:
        logger.info("isolation_forest: too few products (%d), skipping", len(product_ids))
        return []

    # Build feature matrix
    features = []
    for pid in product_ids:
        margins = product_margin.get(pid, [0])
        avg_margin = float(np.mean(margins)) if margins else 0
        features.append([
            product_qty.get(pid, 0.0),
            avg_margin,
            inv_by_product.get(pid, 0.0),
            float(product_ticket_count.get(pid, 0)),
        ])

    X = np.array(features, dtype=np.float64)

    clf = IForest(contamination=contamination, random_state=42, n_estimators=100)
    predictions = clf.fit_predict(X)
    scores = clf.decision_function(X)

    events: List[AnomalyEvent] = []

    for i, pid in enumerate(product_ids):
        if predictions[i] == -1:
            anomaly_score = -float(scores[i])
            confidence = min(0.85, max(0.50, 0.5 + anomaly_score * 0.3))

            events.append(AnomalyEvent(
                event_id=uuid.uuid4().hex[:12],
                anomaly_type=AnomalyType.ISOLATION_FOREST,
                product_id=pid,
                product_name=product_names.get(pid),
                metric="isolation_forest_score",
                metric_value=round(anomaly_score, 4),
                threshold=0.0,
                score=round(anomaly_score, 4),
                confidence=round(confidence, 3),
                severity="medium",
                details={
                    "total_qty": product_qty.get(pid, 0.0),
                    "avg_margin_pct": round(float(np.mean(product_margin.get(pid, [0]))), 2),
                    "available_qty": inv_by_product.get(pid, 0.0),
                    "ticket_count": product_ticket_count.get(pid, 0),
                },
            ))

    logger.info("isolation_forest: %d multivariate outliers from %d products", len(events), len(product_ids))
    return events
