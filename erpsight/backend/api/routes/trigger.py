"""Pipeline trigger route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from erpsight.backend.services import pipeline

logger = logging.getLogger(__name__)

router = APIRouter()

# Store latest pipeline result for polling
_latest_result: dict | None = None


def _run_pipeline():
    global _latest_result
    try:
        _latest_result = pipeline.run_full_pipeline()
    except Exception:
        logger.exception("Pipeline run failed")
        _latest_result = {"error": "Pipeline run failed"}


@router.post("/trigger")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """Kick off the full detect → analyze → act pipeline in the background."""
    background_tasks.add_task(_run_pipeline)
    return {"status": "pipeline_started"}


@router.get("/trigger/status")
def pipeline_status():
    """Return the latest pipeline run result."""
    if _latest_result is None:
        return {"status": "no_run_yet"}
    return _latest_result
