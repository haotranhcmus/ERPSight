# ERPSight Backend & AI Layer by @ethan-kiennt

## 1. Luồng chạy hệ thống (Workflow)

1. **InsightAgent (Agent 2)**: Sử dụng LangGraph & Gemini Pro phân tích cảnh báo từ Agent 1. Tự động truy xuất Data Service (Sale, Inventory, v.v.) để lấy bằng chứng thực tế và trả về một Pydantic model đề xuất.
2. **ActionExecutor (Agent 3)**: Định tuyến luồng xử lý và đánh giá thông qua điểm tin cậy tổng hợp (Confidence Score).
    - **Score >= 0.85 & Low Risk (Whitelist)**: Thực thi lệnh thẳng xuống Odoo bằng `idempotency_key` một cách tự động (Auto-Execute).
    - **Score < 0.85 hoặc High Risk**: Chặn Auto-Execute và đưa request lưu trữ vào Approval Queue chờ con người phê duyệt.

> **Công thức Confidence Score:**
> `Score = 0.4 * Sigmoid(Anomaly_Z_Score) + 0.4 * Similarity_Score + 0.2 * Data_Coverage`

## 2. Giao tiếp API (FastAPI)

Tầng API đặt ở `api/routes/incidents.py` phục vụ giao diện người dùng (Frontend) tương tác với hàng đợi phê duyệt (Approval Queue).

- `GET /incidents`
  - Lấy danh sách các sự cố bất thường và đề xuất đang chờ phê duyệt.
- `POST /incidents/{incident_id}/approve`
  - Xác nhận approval. Trigger Agent 3 lấy thông tin payload tương ứng và đẩy lệnh vào Odoo Adapter. Sử dụng idempotency key chống lặp request.
- `POST /incidents/{incident_id}/reject`
  - Flow từ chối hành động. Xoá khỏi queue và ghi log lý do của người dùng vào tệp `feedback_loop.json` làm raw data huấn luyện AI sau này.

---
**Run server:**
```bash
uvicorn erpsight.backend.api.main:app --reload
```
