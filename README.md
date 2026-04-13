## Cấu trúc thư mục

```
ERPSight/
├── .env.example                      # Template cấu hình môi trường
├── whitelist.json                    # Danh sách hành động được phép ghi vào Odoo
└── erpsight/
    └── backend/
        ├── config/
        │   ├── settings.py           # Cấu hình tập trung (pydantic-settings)
        │   ├── logging_config.py     # Cấu hình logging
        │   └── whitelist.json        # Whitelist các write action
        ├── models/domain/            # Domain models (Pydantic)
        │   ├── order.py              # Order + OrderLine
        │   ├── inventory.py          # Inventory (stock.quant)
        │   ├── supplier_order.py     # SupplierOrder + POLine
        │   ├── customer_ticket.py    # CustomerTicket (OCA helpdesk)
        │   └── transaction.py        # Transaction + InvoiceLine
        ├── adapters/                 # Adapter layer
        │   ├── odoo_client.py        # XML-RPC client chính
        │   ├── order_mapper.py       # sale.order → Order
        │   ├── inventory_mapper.py   # stock.quant → Inventory
        │   ├── purchase_mapper.py    # purchase.order → SupplierOrder
        │   ├── ticket_mapper.py      # helpdesk.ticket → CustomerTicket
        │   └── transaction_mapper.py # account.move → Transaction
        ├── agents/                   # SentinelAgent (Phase 2)
        ├── detectors/                # Anomaly detectors (Phase 2)
        ├── executor/                 # ActionExecutor (Phase 2)
        ├── memory/                   # FAISS + Firebase (Phase 3 — AI Team)
        ├── services/                 # Business services
        ├── tools/                    # LangChain tools (Phase 3)
        └── api/                      # FastAPI routes (Phase 4)
```

---
