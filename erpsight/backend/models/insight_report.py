"""
models/insight_report.py

Extended InsightReport schema — output of InsightAgent (Agent 2),
input to ActionAgent (Agent 3).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendedAction(BaseModel):
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    priority: int = 1


class InsightReport(BaseModel):
    report_id: str
    event_id: str
    scenario: str = ""

    # Human-readable analysis (Vietnamese)
    summary: str = ""
    evidence: List[str] = Field(default_factory=list)
    root_cause: str = ""

    # Actions proposed by the agent
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)

    # Scoring
    confidence: float = 0.0
    anomaly_score: float = 0.0
    similarity_score: float = 0.0
    data_coverage: float = 0.0

    # Context data gathered by insight tools
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
