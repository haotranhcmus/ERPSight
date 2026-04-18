"""
models/anomaly_event.py

Unified anomaly event schema — output of SentinelAgent (Agent 1),
input to InsightAgent (Agent 2).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    DEMAND_SPIKE = "demand_spike"
    STOCKOUT_RISK = "stockout_risk"
    MARGIN_EROSION = "margin_erosion"
    VIP_CHURN = "vip_churn"
    ISOLATION_FOREST = "isolation_forest"


class AnomalyEvent(BaseModel):
    event_id: str
    anomaly_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Entity references (product or customer)
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None

    # Detection metrics
    metric: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    score: float = 0.0
    z_score: float = 0.0
    confidence: float = 0.5
    severity: str = "medium"

    # Raw data from detector
    details: Dict[str, Any] = Field(default_factory=dict)
