"""
models/approval_item.py

Schema for actions queued for human approval.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class ApprovalItem(BaseModel):
    approval_id: str
    event_id: str
    report_id: str
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "medium"
    confidence: float = 0.0
    reason: str = ""
    summary: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    # advisory_only=True: low-confidence — chỉ hiển thị text, không thực thi Odoo khi approve
    advisory_only: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
