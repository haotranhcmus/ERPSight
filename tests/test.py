#!/usr/bin/env python3
"""
tests/test.py — Data reference for the next AI developer.

Run this file to see the exact dict structure returned by each OdooClient method.
This is enough to write detectors/agents without reading Odoo docs or XML-RPC internals.

Usage (from project root):
    .venv/bin/python tests/test.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from erpsight.backend.adapters.odoo_client import OdooClient


def header(index: int, title: str) -> None:
    print(f"\n{'='*68}\n  [{index}] {title}\n{'='*68}")

def print_data(label: str, records: list, n: int = 3) -> None:
    print(f"\n# {label} → {len(records)} records (showing up to {n}):")
    for item in records[:n]:
        print(" ", json.dumps(item, ensure_ascii=False, default=str))


def main() -> None:
    client = OdooClient()

    # [1] Connection
    header(1, "Odoo Connection")
    print("check_connection():", client.check_connection())
    uid = client.authenticate()
    version = client.get_server_version()
    print(f"uid = {uid}  |  Odoo version = {version.get('server_version')}")

    # [2] Sale Orders
    # Returns: id, name, partner_id [id, name], date_order, amount_total,
    #          amount_untaxed, state (draft|sale|done|cancel), order_line [ids]
    header(2, "Sale Orders  →  get_sale_orders()")
    date_from = (date.today() - timedelta(days=365)).isoformat()
    sale_orders = client.get_sale_orders(date_from=date_from, limit=5)
    print_data("sale.order", sale_orders)

    # [3] Sale Order Lines
    # Returns: id, order_id, product_id, product_uom_qty, price_unit,
    #          price_subtotal, discount
    header(3, "Sale Order Lines  →  get_sale_order_lines(order_ids)")
    sale_order_ids = [o["id"] for o in sale_orders]
    sale_lines = client.get_sale_order_lines(sale_order_ids)
    print_data("sale.order.line", sale_lines)

    # [4] Stock Quants
    # get_stock_quants()     → internal locations only (excludes virtual/transit)
    # get_all_stock_quants() → all locations
    # Returns: id, product_id, quantity, reserved_quantity, location_id, in_date
    header(4, "Stock Quants  →  get_stock_quants()")
    stock_quants = client.get_stock_quants()
    print_data("stock.quant", stock_quants)

    # [5] Products
    # get_products()         → list[dict]: id, name, standard_price, list_price
    # get_product_cost_map() → dict[product_id, cost]  (used for margin calc)
    header(5, "Products  →  get_products()  +  get_product_cost_map()")
    products = client.get_products()
    print_data("product.product", products, n=3)

    product_ids = [p["id"] for p in products[:3]]
    cost_map = client.get_product_cost_map(product_ids=product_ids)
    print(f"\n# get_product_cost_map({product_ids}):")
    print(" ", json.dumps(cost_map, ensure_ascii=False))

    # [6] Purchase Orders
    # Returns: id, name, partner_id, date_order, amount_total, amount_untaxed,
    #          state (draft|purchase|done|cancel), order_line [ids]
    header(6, "Purchase Orders  →  get_purchase_orders()")
    purchase_orders = client.get_purchase_orders(limit=5)
    print_data("purchase.order", purchase_orders)

    # [7] Purchase Order Lines
    # Returns: id, order_id, product_id, product_qty, price_unit,
    #          price_subtotal, date_planned
    header(7, "Purchase Order Lines  →  get_purchase_order_lines(po_ids)")
    purchase_order_ids = [o["id"] for o in purchase_orders]
    purchase_lines = client.get_purchase_order_lines(purchase_order_ids)
    print_data("purchase.order.line", purchase_lines)

    # [8] Helpdesk Tickets
    # Returns: id, name, description, partner_id, stage_id, priority
    #          (0=normal 1=high 2=very high 3=urgent), user_id, team_id,
    #          create_date, closed_date, closed (bool), last_stage_update
    header(8, "Helpdesk Tickets  →  get_helpdesk_tickets()")
    tickets = client.get_helpdesk_tickets(limit=5)
    print_data("helpdesk.ticket", tickets)

    # [9] Invoices + Invoice Lines
    # get_invoices()      → id, name, partner_id, invoice_date, invoice_line_ids,
    #                        state (draft|posted|cancel), move_type
    #                        (out_invoice=sale / in_invoice=purchase), amount_total
    # get_invoice_lines() → same as sale.order.line but uses 'quantity' not 'product_uom_qty'
    header(9, "Invoices  →  get_invoices()  +  get_invoice_lines()")
    invoices = client.get_invoices(limit=5)
    print_data("account.move", invoices)

    invoice_ids = [i["id"] for i in invoices]
    invoice_lines = client.get_invoice_lines(invoice_ids)
    print_data("account.move.line", invoice_lines)

    # [10] Partners
    # Returns: id, name, email, phone, customer_rank (>0 means active customer)
    header(10, "Partners  →  get_partners(partner_ids)")
    partner_ids = sorted({
        r["partner_id"][0]
        for r in sale_orders
        if isinstance(r.get("partner_id"), list)
    })
    partners = client.get_partners(partner_ids[:5])
    print_data("res.partner", partners)

    print("\n" + "="*68)
    print("  Done. All raw Odoo data printed above.")
    print("  Use the return structure comments in each section to write")
    print("  detectors and agents — no need to read Odoo internals.")
    print("="*68)


if __name__ == "__main__":
    main()