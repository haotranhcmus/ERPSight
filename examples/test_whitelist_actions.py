#!/usr/bin/env python3
"""
examples/test_whitelist_actions.py

Test cases for whitelist actions executed against Odoo.
Run from project root ERPSight/:
    .venv/bin/python examples/test_whitelist_actions.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from erpsight.backend.config.logging_config import setup_logging
setup_logging("WARNING")

from erpsight.backend.adapters.odoo_client import OdooClient


def separator(title: str) -> None:
    print(f"\n{'─'*60}\n  {title}\n{'─'*60}")


# ── KB3: Tạo helpdesk ticket cho kịch bản VIP Churn ─────────────────────────

def test_kb3_create_ticket() -> None:
    """
    Test: tạo helpdesk ticket theo dõi churn risk cho khách VIP.
    Kịch bản: Cửa hàng Hùng Laptop Cần Thơ im lặng 11 ngày sau đơn 08/04/2026.
    ERPSight phát hiện → tạo ticket nội bộ để team Sales theo dõi.
    """
    separator("KB3 – Tạo helpdesk ticket: VIP Churn Follow-up")

    client = OdooClient()

    # 1. Tìm partner
    partner_name = "Hùng Laptop Cần Thơ"
    partners = client.search_read(
        "res.partner",
        [("name", "ilike", partner_name)],
        ["id", "name"],
        limit=1,
    )
    if not partners:
        print(f"  [FAIL] Không tìm thấy partner '{partner_name}'")
        return
    partner_id = partners[0]["id"]
    print(f"  Partner: {partners[0]['name']} (id={partner_id})")

    # 2. Tìm helpdesk team
    teams = client.search_read("helpdesk.ticket.team", [], ["id", "name"], limit=1)
    if not teams:
        print("  [FAIL] Không tìm thấy helpdesk team. Module helpdesk_mgmt chua cai?")
        return
    team_id = teams[0]["id"]
    print(f"  Team: {teams[0]['name']} (id={team_id})")

    # 3. Tìm stage "New" / "In Progress"
    stages = client.search_read("helpdesk.ticket.stage", [], ["id", "name"])
    stage_id = None
    for s in stages:
        if any(kw in s["name"].lower() for kw in ["new", "open", "in progress"]):
            stage_id = s["id"]
            print(f"  Stage: {s['name']} (id={stage_id})")
            break
    if stage_id is None and stages:
        stage_id = stages[0]["id"]
        print(f"  Stage (fallback): {stages[0]['name']} (id={stage_id})")

    # 4. Tạo ticket
    deadline = (date.today() + timedelta(days=2)).isoformat()
    ticket_vals = {
        "name": f"[ERPSight KB3] Follow-up churn risk - {partner_name}",
        "partner_id": partner_id,
        "team_id": team_id,
        "description": (
            "[ERPSight] VIP Churn Alert\n"
            f"Khach hang: {partner_name}\n"
            "Don hang cuoi: 2026-04-08\n"
            "Im lang: 11 ngay (qua han 1.57x chu ky trung binh 7 ngay)\n"
            "Hanh dong can thiet: Lien he lai khach, xac nhan tinh trang, de xuat uu dai giu chan.\n"
            f"Deadline xu ly: {deadline}"
        ),
        "priority": "1",
    }
    if stage_id:
        ticket_vals["stage_id"] = stage_id

    ticket_id = client.execute_kw("helpdesk.ticket", "create", [ticket_vals])
    print(f"  [OK] Ticket tao thanh cong: id={ticket_id}")
    print(f"  Xem: Odoo -> Helpdesk -> id={ticket_id}")
    return ticket_id


if __name__ == "__main__":
    test_kb3_create_ticket()
