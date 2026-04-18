"""
detectors/stockout_detector.py

Detects products at risk of stockout based on current inventory
vs average daily sales velocity.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.config.settings import settings
from erpsight.backend.models.anomaly_event import AnomalyEvent, AnomalyType
from erpsight.backend.services import data_service

logger = logging.getLogger(__name__)


def detect(
    client: OdooClient,
    sales_window_days: int = 30,
) -> List[AnomalyEvent]:
    """
    Return AnomalyEvent for each product whose days_of_stock_remaining
    is below settings.MIN_DAYS_OF_STOCK.
    """
    min_days = settings.MIN_DAYS_OF_STOCK
    today = date.today()
    date_from = (today - timedelta(days=sales_window_days)).isoformat()
    date_to = today.isoformat()

    cost_map = client.get_product_cost_map()
    orders = data_service.fetch_orders(client, date_from=date_from, date_to=date_to, cost_map=cost_map)
    inventories = data_service.fetch_inventories(client)

    # Compute avg daily sales per product
    total_qty: Dict[int, float] = defaultdict(float)
    product_names: Dict[int, str] = {}
    product_skus: Dict[int, str] = {}
    for order in orders:
        for line in order.lines:
            total_qty[line.product_id] += line.quantity
            if line.product_name:
                product_names[line.product_id] = line.product_name
            if hasattr(line, "default_code") and line.default_code:
                product_skus[line.product_id] = line.default_code

    # Aggregate stock per product
    stock_by_product: Dict[int, float] = defaultdict(float)
    for inv in inventories:
        stock_by_product[inv.product_id] += inv.available_qty
        if inv.product_name:
            product_names[inv.product_id] = inv.product_name

    # Fetch latest supplier info from purchase orders (for create_purchase_order action)
    try:
        recent_pos = data_service.fetch_supplier_orders(client, date_from=date_from, date_to=date_to)
        # latest_supplier[product_id] = (supplier_name, last_price_unit)
        latest_supplier: Dict[int, tuple] = {}
        for po in recent_pos:
            for pl in po.lines:
                latest_supplier[pl.product_id] = (po.partner_name or "", pl.price_unit)
    except Exception:
        latest_supplier = {}

    events: List[AnomalyEvent] = []

    for pid, stock in stock_by_product.items():
        avg_daily = total_qty.get(pid, 0) / max(sales_window_days, 1)
        if avg_daily < 0.01:
            continue

        days_remaining = stock / avg_daily

        if days_remaining < min_days:
            confidence = min(0.9, 0.6 + (min_days - days_remaining) * 0.05)
            sup_name, sup_price = latest_supplier.get(pid, ("", 0))
            # estimate a sensible reorder qty: enough for 30 days at avg rate
            suggested_qty = max(50, round(avg_daily * 30))
            events.append(AnomalyEvent(
                event_id=uuid.uuid4().hex[:12],
                anomaly_type=AnomalyType.STOCKOUT_RISK,
                product_id=pid,
                product_name=product_names.get(pid),
                metric="days_of_stock_remaining",
                metric_value=round(days_remaining, 2),
                threshold=float(min_days),
                score=round(max(0, min_days - days_remaining), 4),
                z_score=0.0,
                confidence=round(confidence, 3),
                severity="high" if days_remaining < 1 else "medium",
                details={
                    "available_qty": round(stock, 1),
                    "avg_daily_sales": round(avg_daily, 2),
                    "days_remaining": round(days_remaining, 2),
                    "supplier_name": sup_name,
                    "last_price_unit": sup_price,
                    "suggested_qty": suggested_qty,
                },
            ))

    logger.info("stockout_detector: %d stockout risks", len(events))
    return events
