"""
models/action_log.py

Schema for executed-action history (auto + approved).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ActionLog(BaseModel):
    log_id: str
    event_id: str
    report_id: str
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    auto_executed: bool = False
    success: bool = False
    result: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    undo_record_id: Optional[int] = None
    undone: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
