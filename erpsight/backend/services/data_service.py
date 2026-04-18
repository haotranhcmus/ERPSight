"""
backend/services/data_service.py

Thin service layer — wraps OdooClient + mappers into single-call functions.
This is the entry point for AI detectors and agents (Phase 2+).

Usage:
    from erpsight.backend.adapters.odoo_client import OdooClient
    from erpsight.backend.services import data_service

    client = OdooClient()
    orders = data_service.fetch_orders(client, date_from="2026-01-01")
"""

from __future__ import annotations

from typing import Dict, List, Optional

from erpsight.backend.adapters.inventory_mapper import map_inventories
from erpsight.backend.adapters.odoo_client import OdooClient
from erpsight.backend.adapters.order_mapper import map_orders
from erpsight.backend.adapters.purchase_mapper import map_supplier_orders
from erpsight.backend.adapters.ticket_mapper import map_tickets

from erpsight.backend.models.domain.customer_ticket import CustomerTicket
from erpsight.backend.models.domain.inventory import Inventory
from erpsight.backend.models.domain.order import Order
from erpsight.backend.models.domain.supplier_order import SupplierOrder


def fetch_orders(
    client: OdooClient,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    partner_id: Optional[int] = None,
    states: Optional[List[str]] = None,
    limit: int = 500,
    cost_map: Optional[Dict[int, float]] = None,
) -> List[Order]:
    """
    Fetch and map sale orders to Order domain models.

    Args:
        client:     active OdooClient instance
        date_from:  ISO date "YYYY-MM-DD" (inclusive)
        date_to:    ISO date "YYYY-MM-DD" (inclusive)
        partner_id: filter by customer id
        states:     defaults to ["sale", "done"]
        limit:      max records (0 = all)
        cost_map:   pre-fetched {product_id: cost} — pass when calling multiple
                    fetch functions in one session to avoid redundant API calls
    """
    raw_orders = client.get_sale_orders(
        date_from=date_from,
        date_to=date_to,
        partner_id=partner_id,
        states=states,
        limit=limit,
    )
    if not raw_orders:
        return []

    raw_lines = client.get_sale_order_lines([o["id"] for o in raw_orders])
    resolved_cost_map = cost_map if cost_map is not None else client.get_product_cost_map()
    return map_orders(raw_orders, raw_lines, resolved_cost_map)


def fetch_inventories(
    client: OdooClient,
    product_ids: Optional[List[int]] = None,
    internal_only: bool = True,
) -> List[Inventory]:
    """
    Fetch and map stock quants to Inventory domain models.

    Note: avg_daily_sales and days_of_stock_remaining are left at their
    defaults (0.0 and None). Inject them in your detector after this call.

    Args:
        client:        active OdooClient instance
        product_ids:   filter to specific products; None = all
        internal_only: only internal warehouse locations (default True)
    """
    raw_quants = client.get_stock_quants(
        product_ids=product_ids,
        internal_only=internal_only,
    )
    return map_inventories(raw_quants)


def fetch_supplier_orders(
    client: OdooClient,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    partner_id: Optional[int] = None,
    states: Optional[List[str]] = None,
    limit: int = 500,
    pending_only: bool = False,
) -> List[SupplierOrder]:
    """
    Fetch and map purchase orders to SupplierOrder domain models.

    Args:
        client:       active OdooClient instance
        date_from:    ISO date "YYYY-MM-DD" (inclusive)
        date_to:      ISO date "YYYY-MM-DD" (inclusive)
        partner_id:   filter by supplier id
        states:       defaults to all except cancelled
        limit:        max records (0 = all)
        pending_only: when True, excludes POs where receipt_status='full'.
                      Use for stockout/pending-receipt scans — in Odoo 17,
                      confirmed POs remain in 'purchase' state even after
                      full receipt, so state alone is not enough.
    """
    raw_pos = client.get_purchase_orders(
        date_from=date_from,
        date_to=date_to,
        partner_id=partner_id,
        states=states,
        limit=limit,
        exclude_fully_received=pending_only,
    )
    if not raw_pos:
        return []

    raw_lines = client.get_purchase_order_lines([po["id"] for po in raw_pos])
    return map_supplier_orders(raw_pos, raw_lines)


def fetch_tickets(
    client: OdooClient,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    partner_id: Optional[int] = None,
    limit: int = 500,
) -> List[CustomerTicket]:
    """
    Fetch and map helpdesk tickets to CustomerTicket domain models.

    Args:
        client:     active OdooClient instance
        date_from:  ISO date "YYYY-MM-DD" — filters by create_date
        date_to:    ISO date "YYYY-MM-DD"
        partner_id: filter by customer id
        limit:      max records (0 = all)
    """
    raw_tickets = client.get_helpdesk_tickets(
        date_from=date_from,
        date_to=date_to,
        partner_id=partner_id,
        limit=limit,
    )
    return map_tickets(raw_tickets)
