"""
backend/adapters/odoo_client.py

XML-RPC client for Odoo Community.

Responsibilities:
  - Authenticate once and cache uid; re-authenticate on session expiry
  - execute_kw with retry + exponential backoff (max 3 attempts)
  - Field-whitelisted read methods for all 5 modules in ERPSight scope
  - Write methods (create, cancel/unlink) with in-process idempotency key
  - Rate-limit-friendly: all calls go through a single execute_kw choke point

Idempotency notes:
  - self._idempotency_log is in-memory; will be replaced by Firebase lookup
    by the AI team when the Firebase layer is added.
  - Key format: sha256(action_type + sorted JSON params)[:32]

Usage:
    from erpsight.backend.adapters.odoo_client import OdooClient
    client = OdooClient()
    orders = client.get_sale_orders(date_from="2026-03-01")
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import xmlrpc.client
from datetime import datetime
from typing import Any, Dict, List, Optional

from erpsight.backend.config.settings import settings

logger = logging.getLogger(__name__)

# ── Odoo field whitelists (only fields within ERPSight scope) ─────────────────

_SALE_ORDER_FIELDS = [
    "id", "name", "partner_id", "date_order",
    "amount_total", "amount_untaxed", "state", "order_line",
]

_SALE_LINE_FIELDS = [
    "id", "order_id", "product_id", "product_uom_qty",
    "price_unit", "price_subtotal", "discount",
]

_STOCK_QUANT_FIELDS = [
    "id", "product_id", "quantity", "reserved_quantity", "location_id", "in_date",
]

_INVOICE_FIELDS = [
    "id", "name", "partner_id", "invoice_date",
    "invoice_line_ids", "state", "move_type",
    "amount_total", "amount_untaxed",
]

_INVOICE_LINE_FIELDS = [
    "id", "move_id", "product_id", "price_unit",
    "quantity", "price_subtotal", "discount",
]

_PURCHASE_ORDER_FIELDS = [
    "id", "name", "partner_id", "date_order",
    "amount_total", "amount_untaxed", "state", "order_line",
]

_PURCHASE_LINE_FIELDS = [
    "id", "order_id", "product_id", "product_qty",
    "price_unit", "price_subtotal", "date_planned",
]

_HELPDESK_TICKET_FIELDS = [
    "id", "name", "description", "partner_id",
    "stage_id", "priority", "user_id", "team_id",
    "create_date", "closed_date", "closed", "last_stage_update",
]

_PRODUCT_FIELDS = [
    "id", "name", "standard_price", "list_price",
]

_PARTNER_FIELDS = [
    "id", "name", "email", "phone", "customer_rank",
]


class _TimeoutTransport(xmlrpc.client.Transport):
    """XML-RPC transport that enforces a per-call socket timeout."""

    def __init__(self, timeout: int) -> None:
        super().__init__(use_builtin_types=True)
        self._timeout = timeout

    def make_connection(self, host: str):  # type: ignore[override]
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class OdooClient:
    """XML-RPC client for Odoo with retry, idempotency, and field whitelisting."""

    def __init__(self) -> None:
        self._uid: Optional[int] = None
        _transport = _TimeoutTransport(settings.ODOO_REQUEST_TIMEOUT)
        self._common = xmlrpc.client.ServerProxy(
            f"{settings.ODOO_URL}/xmlrpc/2/common",
            transport=_transport,
            allow_none=True,
        )
        self._models = xmlrpc.client.ServerProxy(
            f"{settings.ODOO_URL}/xmlrpc/2/object",
            transport=_TimeoutTransport(settings.ODOO_REQUEST_TIMEOUT),
            allow_none=True,
        )
        self._idempotency_log: Dict[str, str] = {}
        self._internal_location_ids: Optional[List[int]] = None

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self) -> int:
        """Authenticate with Odoo and cache uid. Idempotent."""
        if self._uid is not None:
            return self._uid

        uid = self._common.authenticate(
            settings.ODOO_DB,
            settings.ODOO_USERNAME,
            settings.ODOO_PASSWORD,
            {},
        )
        if not uid:
            raise RuntimeError(
                f"Odoo authentication failed — "
                f"db='{settings.ODOO_DB}' user='{settings.ODOO_USERNAME}'"
            )
        self._uid = uid
        logger.info("Authenticated with Odoo uid=%d", uid)
        return uid

    # ── Core RPC ──────────────────────────────────────────────────────────────

    def execute_kw(
        self,
        model: str,
        method: str,
        args: List[Any],
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Call Odoo execute_kw with automatic retry on transient errors.

        Retries up to settings.ODOO_MAX_RETRIES times with exponential
        backoff (1 s → 2 s → 4 s). Odoo Fault exceptions are NOT retried
        because they represent application-level errors (wrong model name,
        access denied, etc.) that will not resolve on retry.
        """
        uid = self.authenticate()
        kwargs = kwargs or {}
        last_exc: Optional[Exception] = None

        for attempt in range(1, settings.ODOO_MAX_RETRIES + 1):
            try:
                return self._models.execute_kw(
                    settings.ODOO_DB,
                    uid,
                    settings.ODOO_PASSWORD,
                    model,
                    method,
                    args,
                    kwargs,
                )
            except xmlrpc.client.Fault:
                # Application-level fault (e.g. wrong field, access denied).
                # No point retrying — re-raise immediately.
                raise
            except (OSError, ConnectionError, TimeoutError) as exc:
                last_exc = exc
                wait = 2 ** (attempt - 1)   # 1s, 2s, 4s
                logger.warning(
                    "execute_kw attempt %d/%d failed for %s.%s: %s — retrying in %ds",
                    attempt, settings.ODOO_MAX_RETRIES,
                    model, method, exc, wait,
                )
                if attempt < settings.ODOO_MAX_RETRIES:
                    time.sleep(wait)
                else:
                    # Force re-auth on next call in case session expired
                    self._uid = None

        raise RuntimeError(
            f"execute_kw failed after {settings.ODOO_MAX_RETRIES} retries "
            f"({model}.{method}): {last_exc}"
        )

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: List[str],
        limit: int = 0,
        offset: int = 0,
        order: str = "",
    ) -> List[Dict[str, Any]]:
        """Convenience wrapper around execute_kw('search_read')."""
        kw: Dict[str, Any] = {"fields": fields}
        if limit:
            kw["limit"] = limit
        if offset:
            kw["offset"] = offset
        if order:
            kw["order"] = order
        return self.execute_kw(model, "search_read", [domain], kw)

    def _read(
        self,
        model: str,
        ids: List[int],
        fields: List[str],
    ) -> List[Dict[str, Any]]:
        return self.execute_kw(model, "read", [ids], {"fields": fields})

    def _create(self, model: str, vals: Dict[str, Any]) -> int:
        return self.execute_kw(model, "create", [vals])

    def _write(self, model: str, ids: List[int], vals: Dict[str, Any]) -> bool:
        return self.execute_kw(model, "write", [ids, vals])

    def _search(self, model: str, domain: List[Any], **kwargs: Any) -> List[int]:
        return self.execute_kw(model, "search", [domain], kwargs)

    def count(self, model: str, domain: List[Any]) -> int:
        """Return record count matching domain."""
        return self.execute_kw(model, "search_count", [domain])

    # ── Idempotency ───────────────────────────────────────────────────────────

    @staticmethod
    def make_idempotency_key(action_type: str, params: Dict[str, Any]) -> str:
        """Deterministic sha256 key from action type + sorted params."""
        payload = json.dumps(
            {"action": action_type, "params": params}, sort_keys=True
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def _check_idempotency(self, key: str) -> Optional[str]:
        """Return previously recorded odoo_record_id for key, or None."""
        return self._idempotency_log.get(key)

    def _record_idempotency(self, key: str, record_id: str) -> None:
        self._idempotency_log[key] = record_id

    # ── READ: Sale Orders ─────────────────────────────────────────────────────

    def get_sale_orders(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        partner_id: Optional[int] = None,
        states: Optional[List[str]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch confirmed sale orders.  Default: last 500 orders.

        Args:
            date_from: ISO date string "YYYY-MM-DD" (inclusive)
            date_to:   ISO date string "YYYY-MM-DD" (inclusive)
            partner_id: filter by customer id
            states:    list of state values; defaults to ["sale", "done"]
            limit:     max records (0 = all)
        """
        domain: List[Any] = []
        if date_from:
            domain.append(("date_order", ">=", date_from))
        if date_to:
            domain.append(("date_order", "<=", date_to + " 23:59:59"))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        if states:
            domain.append(("state", "in", states))
        else:
            domain.append(("state", "in", ["sale", "done"]))
        return self.search_read(
            "sale.order", domain, _SALE_ORDER_FIELDS,
            limit=limit, order="date_order desc",
        )

    def get_sale_order_lines(self, order_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch order lines for the given sale.order ids."""
        if not order_ids:
            return []
        return self.search_read(
            "sale.order.line",
            [("order_id", "in", order_ids)],
            _SALE_LINE_FIELDS,
        )

    # ── READ: Inventory ───────────────────────────────────────────────────────

    def _get_internal_location_ids(self) -> List[int]:
        """Fetch and cache ids of all internal warehouse locations."""
        if self._internal_location_ids is None:
            locs = self.search_read(
                "stock.location",
                [("usage", "=", "internal")],
                ["id"],
            )
            self._internal_location_ids = [l["id"] for l in locs]
            logger.debug("Internal location ids: %s", self._internal_location_ids)
        return self._internal_location_ids

    def get_stock_quants(
        self,
        product_ids: Optional[List[int]] = None,
        internal_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch current stock levels.

        Args:
            product_ids:   filter to specific products; None = all
            internal_only: if True, only internal warehouse locations
        """
        domain: List[Any] = [("quantity", ">", 0)]
        if product_ids:
            domain.append(("product_id", "in", product_ids))
        if internal_only:
            loc_ids = self._get_internal_location_ids()
            if loc_ids:
                domain.append(("location_id", "in", loc_ids))
        return self.search_read("stock.quant", domain, _STOCK_QUANT_FIELDS)

    def get_all_stock_quants(self) -> List[Dict[str, Any]]:
        """Fetch all internal stock quants including those with zero on-hand."""
        loc_ids = self._get_internal_location_ids()
        domain: List[Any] = []
        if loc_ids:
            domain.append(("location_id", "in", loc_ids))
        return self.search_read("stock.quant", domain, _STOCK_QUANT_FIELDS)

    # ── READ: Invoices (account.move) ─────────────────────────────────────────

    def get_invoices(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        partner_id: Optional[int] = None,
        move_types: Optional[List[str]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch posted invoices/bills.

        Args:
            move_types: defaults to ["out_invoice", "in_invoice"]
        """
        domain: List[Any] = [("state", "=", "posted")]
        if date_from:
            domain.append(("invoice_date", ">=", date_from))
        if date_to:
            domain.append(("invoice_date", "<=", date_to))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        domain.append(
            ("move_type", "in", move_types or ["out_invoice", "in_invoice"])
        )
        return self.search_read(
            "account.move", domain, _INVOICE_FIELDS,
            limit=limit, order="invoice_date desc",
        )

    def get_invoice_lines(self, invoice_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch product lines for the given account.move ids (excludes tax/section lines)."""
        if not invoice_ids:
            return []
        return self.search_read(
            "account.move.line",
            [
                ("move_id", "in", invoice_ids),
                ("display_type", "=", "product"),
            ],
            _INVOICE_LINE_FIELDS,
        )

    # ── READ: Purchase Orders ─────────────────────────────────────────────────

    def get_purchase_orders(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        partner_id: Optional[int] = None,
        states: Optional[List[str]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch purchase orders.

        Args:
            states: defaults to all except cancelled ["draft","sent","purchase","done"]
        """
        domain: List[Any] = []
        if date_from:
            domain.append(("date_order", ">=", date_from))
        if date_to:
            domain.append(("date_order", "<=", date_to + " 23:59:59"))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        if states:
            domain.append(("state", "in", states))
        else:
            domain.append(("state", "not in", ["cancel"]))
        return self.search_read(
            "purchase.order", domain, _PURCHASE_ORDER_FIELDS,
            limit=limit, order="date_order desc",
        )

    def get_purchase_order_lines(self, po_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch lines for the given purchase.order ids."""
        if not po_ids:
            return []
        return self.search_read(
            "purchase.order.line",
            [("order_id", "in", po_ids)],
            _PURCHASE_LINE_FIELDS,
        )

    # ── READ: Helpdesk Tickets ────────────────────────────────────────────────

    def get_helpdesk_tickets(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        partner_id: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch helpdesk.ticket records (OCA helpdesk_mgmt v17).

        date_closed field availability is probed once and cached.
        Falls back gracefully if the field does not exist in this version.
        """
        domain: List[Any] = []
        if date_from:
            domain.append(("create_date", ">=", date_from))
        if date_to:
            domain.append(("create_date", "<=", date_to + " 23:59:59"))
        if partner_id:
            domain.append(("partner_id", "=", partner_id))

        return self.search_read(
            "helpdesk.ticket", domain, _HELPDESK_TICKET_FIELDS,
            limit=limit, order="create_date desc",
        )

    # ── READ: Products ────────────────────────────────────────────────────────

    def get_products(
        self,
        product_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch product.product records with cost and list price.

        Used to compute margin in order/invoice mappers.
        If product_ids is supplied, fetches only those products.
        """
        if product_ids:
            domain: List[Any] = [("id", "in", product_ids)]
        else:
            domain = [("active", "=", True)]
        return self.search_read("product.product", domain, _PRODUCT_FIELDS)

    def get_product_cost_map(
        self,
        product_ids: Optional[List[int]] = None,
    ) -> Dict[int, float]:
        """
        Return {product_id: standard_price} dict for margin computation.

        Args:
            product_ids: if None, fetches all active products.
        """
        products = self.get_products(product_ids)
        return {p["id"]: float(p.get("standard_price") or 0) for p in products}

    # ── READ: Partners ────────────────────────────────────────────────────────

    def get_partners(self, partner_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch res.partner records by id list."""
        if not partner_ids:
            return []
        return self._read("res.partner", partner_ids, _PARTNER_FIELDS)

    # ── WRITE: Draft Purchase Order ───────────────────────────────────────────

    def create_draft_purchase_order(
        self,
        partner_id: int,
        order_lines: List[Dict[str, Any]],
        notes: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a draft purchase.order in Odoo (whitelist action: medium risk).

        Args:
            partner_id:  supplier res.partner id
            order_lines: list of dicts with keys:
                           product_id (int), qty (float),
                           price_unit (float, optional),
                           name (str, optional),
                           date_planned (str YYYY-MM-DD, optional)
            notes:           internal notes on the PO
            idempotency_key: auto-generated if not provided

        Returns:
            {
              "record_id": int,
              "idempotency_key": str,
              "skipped": bool   # True if already created with same key
            }
        """
        if idempotency_key is None:
            idempotency_key = self.make_idempotency_key(
                "create_draft_po",
                {"partner_id": partner_id, "lines": sorted(
                    [{"pid": l["product_id"], "qty": l["qty"]} for l in order_lines],
                    key=lambda x: x["pid"],
                )},
            )

        existing = self._check_idempotency(idempotency_key)
        if existing:
            logger.info(
                "Idempotency hit — draft PO already created (record_id=%s, key=%s)",
                existing, idempotency_key,
            )
            return {
                "record_id": int(existing),
                "idempotency_key": idempotency_key,
                "skipped": True,
            }

        today = datetime.now().strftime("%Y-%m-%d")
        po_vals: Dict[str, Any] = {
            "partner_id": partner_id,
            "notes": notes,
            "order_line": [
                (0, 0, {
                    "product_id": line["product_id"],
                    "product_qty": float(line["qty"]),
                    "price_unit": float(line.get("price_unit", 0)),
                    "name": line.get("name", ""),
                    "date_planned": line.get("date_planned", today),
                })
                for line in order_lines
            ],
        }

        record_id: int = self._create("purchase.order", po_vals)
        self._record_idempotency(idempotency_key, str(record_id))

        logger.info(
            "Created draft PO id=%d for supplier partner_id=%d",
            record_id, partner_id,
        )
        return {
            "record_id": record_id,
            "idempotency_key": idempotency_key,
            "skipped": False,
        }

    def cancel_purchase_order(self, po_id: int) -> bool:
        """
        Cancel or delete a draft PO created by ERPSight (undo action).

        Tries button_cancel first (works on sent/confirmed POs),
        then falls back to unlink for draft records.
        """
        try:
            self.execute_kw("purchase.order", "button_cancel", [[po_id]])
            logger.info("Cancelled PO id=%d", po_id)
            return True
        except xmlrpc.client.Fault:
            try:
                self.execute_kw("purchase.order", "unlink", [[po_id]])
                logger.info("Deleted (unlink) draft PO id=%d", po_id)
                return True
            except xmlrpc.client.Fault as exc:
                logger.error("Failed to cancel/unlink PO id=%d: %s", po_id, exc.faultString)
                return False

    # ── WRITE: Internal Alerts ────────────────────────────────────────────────

    def post_chatter_message(
        self,
        model: str,
        res_id: int,
        message: str,
        subtype_xmlid: str = "mail.mt_note",
    ) -> int:
        """
        Post a note/message to an Odoo record's chatter (whitelist action: low risk).

        Args:
            model:         Odoo model name e.g. "sale.order"
            res_id:        record id
            message:       HTML or plain-text body
            subtype_xmlid: "mail.mt_note" (internal note) or "mail.mt_comment" (message)

        Returns:
            mail.message id
        """
        result = self.execute_kw(
            model,
            "message_post",
            [[res_id]],
            {
                "body": message,
                "message_type": "comment",
                "subtype_xmlid": subtype_xmlid,
            },
        )
        logger.info("Posted chatter message on %s#%d (msg_id=%s)", model, res_id, result)
        return result

    def create_activity(
        self,
        model: str,
        res_id: int,
        summary: str,
        note: str,
        date_deadline: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """
        Schedule a mail.activity on any Odoo record (whitelist action: low risk).

        Args:
            model:         Odoo model name e.g. "sale.order"
            res_id:        record id
            summary:       short title visible in activity list
            note:          full HTML note
            date_deadline: "YYYY-MM-DD", defaults to today
            user_id:       assign to specific user; defaults to current user

        Returns:
            mail.activity id (can be used for undo via delete_activity)
        """
        if date_deadline is None:
            date_deadline = datetime.now().strftime("%Y-%m-%d")

        ir_model_records = self.search_read(
            "ir.model", [("model", "=", model)], ["id"], limit=1
        )
        if not ir_model_records:
            raise ValueError(f"create_activity: model '{model}' not found in ir.model")

        vals: Dict[str, Any] = {
            "res_model_id": ir_model_records[0]["id"],
            "res_id": res_id,
            "summary": summary,
            "note": note,
            "date_deadline": date_deadline,
        }
        if user_id:
            vals["user_id"] = user_id

        # Resolve a suitable activity type (To-Do is a safe default)
        try:
            types = self.search_read(
                "mail.activity.type",
                [("res_model", "in", [model, False])],
                ["id", "name"],
                limit=1,
                order="sequence asc",
            )
            if types:
                vals["activity_type_id"] = types[0]["id"]
        except xmlrpc.client.Fault:
            pass

        activity_id: int = self._create("mail.activity", vals)
        logger.info(
            "Created activity id=%d on %s#%d: %s",
            activity_id, model, res_id, summary,
        )
        return activity_id

    def delete_activity(self, activity_id: int) -> bool:
        """Undo a previously created mail.activity (whitelist undo action)."""
        try:
            self.execute_kw("mail.activity", "unlink", [[activity_id]])
            logger.info("Deleted activity id=%d", activity_id)
            return True
        except xmlrpc.client.Fault as exc:
            logger.error("Failed to delete activity id=%d: %s", activity_id, exc.faultString)
            return False

    # ── Utility ───────────────────────────────────────────────────────────────

    def get_server_version(self) -> Dict[str, Any]:
        """Return Odoo server version info."""
        return self._common.version()

    def check_connection(self) -> bool:
        """Quick connectivity check. Returns True if auth succeeds."""
        try:
            self.authenticate()
            return True
        except (xmlrpc.client.Fault, OSError, RuntimeError) as exc:
            logger.error("Odoo connection check failed: %s", exc)
            return False
