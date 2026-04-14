## Cấu trúc thư mục

```
ERPSight/
├── .env.example                      # Template cấu hình môi trường
├── examples/
│   └── service_example.py            # Ví dụ fetch data + inject derived fields
└── erpsight/
    └── backend/
        ├── requirements.txt
        ├── config/
        │   ├── settings.py           # Cấu hình tập trung (pydantic-settings)
        │   ├── logging_config.py     # Cấu hình logging
        │   └── whitelist.json        # Whitelist các write action được phép
        ├── models/domain/            # Domain models (Pydantic v2)
        │   ├── order.py              # Order + OrderLine
        │   ├── inventory.py          # Inventory (stock.quant)
        │   ├── supplier_order.py     # SupplierOrder + POLine
        │   └── customer_ticket.py    # CustomerTicket (OCA helpdesk_mgmt)
        ├── adapters/                 # Adapter layer — Phase 1 hoàn chỉnh
        │   ├── odoo_client.py        # XML-RPC client
        │   ├── mapper_utils.py       # Shared helpers: m2o_id, m2o_name, parse_dt
        │   ├── order_mapper.py       # sale.order → Order
        │   ├── inventory_mapper.py   # stock.quant → Inventory
        │   ├── purchase_mapper.py    # purchase.order → SupplierOrder
        │   └── ticket_mapper.py      # helpdesk.ticket → CustomerTicket
        ├── services/                 # Service layer — entry point cho AI team
        │   └── data_service.py       # fetch_orders / fetch_inventories / fetch_supplier_orders / fetch_tickets
        ├── agents/                   # SentinelAgent (Phase 2)
        ├── detectors/                # Anomaly detectors (Phase 2)
        ├── executor/                 # ActionExecutor (Phase 2)
        ├── memory/                   # FAISS + Firebase (Phase 3)
        ├── tools/                    # LangChain tools (Phase 3)
        └── api/                      # FastAPI routes (Phase 4)
            └── routes/
```

---
