"""
detectors/margin_risk_detector.py

Detects products whose gross margin has fallen below the configured
threshold (default 5%), typically caused by purchase-price increases
that haven't been reflected in the sale price.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Tuple

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.config.settings import settings
from erpsight.backend.models.anomaly_event import AnomalyEvent, AnomalyType
from erpsight.backend.services import data_service

logger = logging.getLogger(__name__)


def detect(
    client: OdooClient,
    window_days: int = 30,
) -> List[AnomalyEvent]:
    """
    Detect products selling at or near a loss.

    Compares latest purchase price with current sale price to compute
    gross margin.  Flags products below MARGIN_RISK_THRESHOLD.
    """
    margin_threshold = settings.MARGIN_RISK_THRESHOLD
    today = date.today()
    date_from = (today - timedelta(days=window_days)).isoformat()

    cost_map = client.get_product_cost_map()
    orders = data_service.fetch_orders(
        client, date_from=date_from, date_to=today.isoformat(), cost_map=cost_map,
    )

    # Track avg margin per product
    product_margins: Dict[int, List[float]] = defaultdict(list)
    product_info: Dict[int, Dict] = {}

    for order in orders:
        for line in order.lines:
            if line.price_unit > 0:
                margin = line.margin_pct
                product_margins[line.product_id].append(margin)
                if line.product_id not in product_info:
                    product_info[line.product_id] = {
                        "name": line.product_name,
                        "sale_price": line.price_unit,
                        "cost_price": line.cost_price,
                    }

    # Also pull latest PO prices for comparison
    pos = data_service.fetch_supplier_orders(client, date_from=date_from, date_to=today.isoformat())
    latest_po_price: Dict[int, float] = {}
    for po in pos:
        for pl in po.lines:
            latest_po_price[pl.product_id] = pl.price_unit

    events: List[AnomalyEvent] = []

    for pid, margins in product_margins.items():
        avg_margin = sum(margins) / len(margins) if margins else 0
        if avg_margin >= margin_threshold:
            continue

        info = product_info.get(pid, {})
        po_price = latest_po_price.get(pid, info.get("cost_price", 0))
        sale_price = info.get("sale_price", 0)
        confidence = min(0.9, 0.6 + abs(margin_threshold - avg_margin) * 2)

        events.append(AnomalyEvent(
            event_id=uuid.uuid4().hex[:12],
            anomaly_type=AnomalyType.MARGIN_EROSION,
            product_id=pid,
            product_name=info.get("name"),
            metric="margin_pct",
            metric_value=round(avg_margin * 100, 2),
            threshold=round(margin_threshold * 100, 2),
            score=round(abs(margin_threshold - avg_margin), 4),
            z_score=0.0,
            confidence=round(confidence, 3),
            severity="high" if avg_margin < 0 else "medium",
            details={
                "avg_margin_pct": round(avg_margin * 100, 2),
                "sale_price": sale_price,
                "purchase_price": po_price,
                "standard_price": cost_map.get(pid, 0),
            },
        ))

    logger.info("margin_risk_detector: %d margin alerts", len(events))
    return events
