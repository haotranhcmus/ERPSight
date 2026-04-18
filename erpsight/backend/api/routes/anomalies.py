"""Anomaly & InsightReport read routes."""

from __future__ import annotations

from fastapi import APIRouter

from erpsight.backend.services import firebase_store

router = APIRouter()


@router.get("/anomalies")
def list_anomalies():
    return firebase_store.get_all_anomalies()


@router.get("/anomalies/{event_id}")
def get_anomaly(event_id: str):
    item = firebase_store.get_anomaly(event_id)
    if item is None:
        return {"error": "not_found"}
    return item


@router.get("/reports")
def list_reports():
    return firebase_store.get_all_reports()


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    item = firebase_store.get_report(report_id)
    if item is None:
        return {"error": "not_found"}
    return item
