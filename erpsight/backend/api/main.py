"""
api/main.py

FastAPI application for ERPSight backend.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from erpsight.backend.api.routes import (
    action_log,
    anomalies,
    approval,
    health,
    trigger,
)
from erpsight.backend.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ERPSight API",
    version="0.1.0",
    description="AI-powered ERP anomaly detection and action engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(trigger.router, prefix="/api", tags=["Pipeline"])
app.include_router(anomalies.router, prefix="/api", tags=["Anomalies"])
app.include_router(approval.router, prefix="/api", tags=["Approval"])
app.include_router(action_log.router, prefix="/api", tags=["Action Log"])
