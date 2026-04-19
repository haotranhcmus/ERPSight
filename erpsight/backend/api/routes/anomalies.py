"""Anomaly & InsightReport read routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter

from erpsight.backend.models.anomaly_event import AnomalyEvent
from erpsight.backend.models.approval_item import ApprovalItem
from erpsight.backend.models.insight_report import InsightReport, RecommendedAction
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


@router.post("/debug/inject-kb3-ticket-test")
def inject_kb3_ticket_test():
    """
    Inject a test KB3 vip_churn anomaly with a pending create_helpdesk_ticket approval.
    Use this to test the full UI flow without running the pipeline.
    """
    event_id = f"test-kb3-{uuid.uuid4().hex[:8]}"
    report_id = f"rpt-{uuid.uuid4().hex[:8]}"
    approval_id = f"apv-{uuid.uuid4().hex[:8]}"

    ticket_params = {
        "partner_name": "Hùng Laptop Cần Thơ",
        "ticket_name": "[ERPSight KB3] Theo doi churn risk - Hung Laptop Can Tho",
        "description": (
            "[ERPSight] VIP Churn Alert\n"
            "Khach hang: Hung Laptop Can Tho\n"
            "Don hang cuoi: 2026-04-08\n"
            "Im lang: 11 ngay (1.57x chu ky trung binh 7 ngay)\n"
            "Can lien he lai va xac nhan tinh trang, de xuat uu dai giu chan."
        ),
        "priority": "1",
        "silent_days": 11,
        "last_order_date": "2026-04-08",
        "overdue_factor": 1.57,
    }

    event = AnomalyEvent(
        event_id=event_id,
        anomaly_type="vip_churn",
        partner_name="Hùng Laptop Cần Thơ",
        metric="overdue_factor",
        metric_value=1.57,
        threshold=1.2,
        score=0.82,
        confidence=0.82,
        severity="high",
        status="active",
        details={
            "days_silent": 11,
            "avg_order_cycle_days": 7,
            "last_order_date": "2026-04-08",
            "overdue_factor": 1.57,
            "order_count": 8,
            "has_recent_complaint": False,
        },
    )
    firebase_store.save_anomaly(event_id, event.model_dump(mode="json"))

    report = InsightReport(
        report_id=report_id,
        event_id=event_id,
        scenario="vip_churn",
        summary="Khách VIP Hùng Laptop Cần Thơ im lặng 11 ngày, vượt 1.57× chu kỳ đặt hàng bình thường.",
        evidence=[
            "Lịch sử 90 ngày: 8 đơn hàng, chu kỳ TB 7 ngày/đơn.",
            "Đơn hàng cuối: 2026-04-08. Đã im lặng 11 ngày = 1.57× chu kỳ bình thường (ngưỡng 1.2×).",
        ],
        root_cause="Khách VIP có thể đã chuyển sang đối thủ hoặc gặp vấn đề chưa được giải quyết.",
        recommended_actions=[
            RecommendedAction(
                action_type="create_helpdesk_ticket",
                params=ticket_params,
                reason="Tạo ticket nội bộ để team Sales theo dõi và xử lý rủi ro mất khách VIP.",
                priority=1,
            )
        ],
        confidence=0.82,
    )
    firebase_store.save_report(report_id, report.model_dump(mode="json"))

    item = ApprovalItem(
        approval_id=approval_id,
        event_id=event_id,
        report_id=report_id,
        action_type="create_helpdesk_ticket",
        params=ticket_params,
        risk_level="low",
        confidence=0.82,
        reason="Tạo ticket nội bộ để team Sales theo dõi và xử lý rủi ro mất khách VIP.",
        summary="Khách VIP Hùng Laptop Cần Thơ im lặng 11 ngày, vượt 1.57× chu kỳ bình thường.",
        advisory_only=False,
    )
    firebase_store.save_approval_item(approval_id, item.model_dump(mode="json"))

    return {
        "status": "ok",
        "event_id": event_id,
        "report_id": report_id,
        "approval_id": approval_id,
        "message": "Test KB3 anomaly injected. Kiểm tra tab Bất thường trong UI.",
    }
