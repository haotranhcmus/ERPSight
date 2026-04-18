"""
models/incident_record.py

FAISS metadata stored alongside embedding vectors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IncidentRecord(BaseModel):
    incident_id: str
    event_id: str
    anomaly_type: str = ""
    scenario: str = ""
    summary: str = ""
    outcome: str = ""
    actions_taken: List[str] = Field(default_factory=list)
    user_feedback: Optional[str] = None
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
