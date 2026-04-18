# ERPSight

Hệ thống phát hiện bất thường ERP dựa trên AI, kết nối trực tiếp với Odoo.

---

## Cấu trúc thư mục

```
ERPSight/
├── .env                              # Biến môi trường thực (gitignored)
├── .env.example                      # Template cấu hình môi trường
├── examples/
│   ├── service_example.py            # Ví dụ fetch data
│   └── test_whitelist_actions.py     # Kiểm tra whitelist action
└── erpsight/
    ├── backend/
    │   ├── requirements.txt
    │   ├── demo_app.py               # Streamlit demo (legacy)
    │   ├── api/
    │   │   ├── main.py               # FastAPI app entry point (:8003)
    │   │   └── routes/
    │   │       ├── health.py         # GET /health
    │   │       ├── trigger.py        # POST /api/trigger — chạy pipeline
    │   │       ├── anomalies.py      # GET /api/anomalies
    │   │       ├── approval.py       # GET/POST /api/approvals
    │   │       └── action_log.py     # GET /api/action-logs
    │   ├── agents/
    │   │   ├── sentinel_agent.py     # Agent 1 — chạy detectors
    │   │   ├── insight_agent.py      # Agent 2 — phân tích KB + LLM
    │   │   └── action_agent.py       # Agent 3 — whitelist gate + approval queue
    │   ├── detectors/
    │   │   ├── stockout_detector.py  # Phát hiện nguy cơ hết hàng
    │   │   ├── margin_risk_detector.py # Phát hiện sụt giảm biên lợi nhuận
    │   │   ├── churn_detector.py     # Phát hiện khách hàng VIP có nguy cơ rời bỏ
    │   │   ├── zscore_detector.py    # Z-score doanh thu bất thường
    │   │   └── isolation_forest.py   # Isolation Forest đa biến
    │   ├── executor/
    │   │   ├── action_executor.py    # Dispatcher thực thi action
    │   │   ├── create_draft_po.py    # Tạo PO nháp trong Odoo
    │   │   ├── send_internal_alert.py# Gửi cảnh báo nội bộ (chatter)
    │   │   └── create_activity_task.py # Tạo activity/task trong Odoo
    │   ├── services/
    │   │   ├── data_service.py       # fetch_orders / fetch_inventories / ...
    │   │   ├── pipeline.py           # Orchestrator chạy toàn bộ pipeline
    │   │   ├── firebase_store.py     # CRUD anomalies/reports/approvals
    │   │   └── confidence_scorer.py  # Tính confidence score
    │   ├── adapters/
    │   │   ├── odoo_client.py        # XML-RPC client
    │   │   ├── order_mapper.py       # sale.order → Order
    │   │   ├── inventory_mapper.py   # stock.quant → Inventory
    │   │   ├── purchase_mapper.py    # purchase.order → SupplierOrder
    │   │   └── ticket_mapper.py      # helpdesk.ticket → CustomerTicket
    │   ├── models/
    │   │   ├── domain/               # Pydantic v2 domain models
    │   │   │   ├── order.py
    │   │   │   ├── inventory.py
    │   │   │   ├── supplier_order.py
    │   │   │   └── customer_ticket.py
    │   │   ├── anomaly_event.py      # AnomalyEvent
    │   │   ├── approval_item.py      # ApprovalItem
    │   │   └── insight_report.py     # InsightReport
    │   ├── memory/
    │   │   ├── faiss_store.py        # FAISS vector store
    │   │   ├── embedder.py           # Text embedder
    │   │   └── feedback_processor.py # Ghi nhận kết quả phê duyệt
    │   ├── tools/
    │   │   └── insight_tools.py      # LangChain tools cho InsightAgent
    │   ├── config/
    │   │   ├── settings.py           # Cấu hình tập trung (pydantic-settings)
    │   │   ├── logging_config.py     # Cấu hình logging
    │   │   └── whitelist.json        # Whitelist các write action được phép
    │   └── script/                   # Script seed/reset dữ liệu demo
    │       ├── seed_odoo.py
    │       ├── reset_demo.py
    │       └── seed_finalize.py
    └── frontend/
        ├── index.html
        ├── vite.config.js
        ├── package.json
        └── src/
            ├── App.jsx               # Router + layout
            ├── index.css             # Global styles
            ├── components/
            │   ├── Sidebar.jsx
            │   ├── Topbar.jsx
            │   ├── StatCard.jsx
            │   └── Badge.jsx
            ├── pages/
            │   ├── Dashboard.jsx     # Trang tổng quan
            │   ├── AnomaliesPage.jsx # Danh sách bất thường + phê duyệt inline
            │   ├── ApprovalsPage.jsx # Hàng đợi phê duyệt
            │   └── ActionLogsPage.jsx# Lịch sử hành động
            └── services/
                └── api.js            # Axios calls đến backend :8003
```

---

## Hướng dẫn chạy

### Yêu cầu

- Python 3.11+
- Node.js 18+
- Odoo instance có DB `erpsight` (cấu hình trong `.env`)
- (Tuỳ chọn) Firebase project + Gemini API key

### 1. Cài đặt môi trường

```bash
# Clone repo
git clone https://github.com/haotranhcmus/ERPSight.git
cd ERPSight

# Tạo và kích hoạt virtualenv
python -m venv .venv
source .venv/bin/activate

# Cài dependencies Python
pip install -r erpsight/backend/requirements.txt

# Tạo file cấu hình
cp .env.example .env
# Chỉnh sửa .env với thông tin Odoo và API key
```

### 2. Chạy Backend (FastAPI)

```bash
# Từ thư mục gốc ERPSight/
source .venv/bin/activate
uvicorn erpsight.backend.api.main:app --host 0.0.0.0 --port 8003 --reload
```

API sẽ chạy tại `http://localhost:8003`.
Docs: `http://localhost:8003/docs`

### 3. Chạy Frontend (React + Vite)

```bash
cd erpsight/frontend
npm install          # lần đầu
npm run dev
```

UI sẽ chạy tại `http://localhost:5173`.

### 4. Kích hoạt pipeline phát hiện bất thường

```bash
# Gọi API trigger (POST)
curl -X POST http://localhost:8003/api/trigger
```

Hoặc nhấn nút **"Chạy phân tích"** trên Dashboard trong UI.

### 5. (Tuỳ chọn) Seed dữ liệu demo vào Odoo

```bash
cd erpsight/backend/script
python seed_odoo.py
python seed_finalize.py
```

### 6. (Tuỳ chọn) Reset dữ liệu demo

```bash
cd erpsight/backend/script
python reset_demo.py
```

---
