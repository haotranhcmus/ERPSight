#!/usr/bin/env python3
"""
examples/service_example.py

Example file for AI developer (Phase 2+).
Run from project root ERPSight/:
    .venv/bin/python examples/service_example.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from erpsight.backend.config.logging_config import setup_logging
setup_logging("WARNING")

from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.services import data_service


def separator(title: str) -> None:
    print(f"\n{'─'*60}\n  {title}\n{'─'*60}")


def main() -> None:
    client = OdooClient()

    # ──  Fetch cost_map once, share across fetch calls ──────────────────────
    cost_map = client.get_product_cost_map()
    print(f"  cost_map: {len(cost_map)} products")

    # ──  Fetch all data via service layer ───────────────────────────────────
    date_from = (date.today() - timedelta(days=90)).isoformat()

    orders      = data_service.fetch_orders(client, date_from=date_from, cost_map=cost_map)
    inventories = data_service.fetch_inventories(client)
    sup_orders  = data_service.fetch_supplier_orders(client)
    tickets     = data_service.fetch_tickets(client)

    # print(f"  orders:       {len(orders)}")
    # print(f"  inventories:  {len(inventories)}")
    # print(f"  sup_orders:   {len(sup_orders)}")
    # print(f"  tickets:      {len(tickets)}")

    # print(orders[0])
    # print(inventories[0])
    # print(sup_orders[0])
    print(tickets[0])


if __name__ == "__main__":
    main()
