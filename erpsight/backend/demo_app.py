"""
demo_app.py — ERPSight AI Simulation & Live Dashboard

Bản Dashboard hoàn chỉnh kết nối trực tiếp với Agent 2 (InsightAgent) 
và Agent 3 (ActionExecutor) hàng thật.
"""
import os
import sys
import json
import uuid
import datetime
import streamlit as st

# ─── sys.path setup ──────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))      # ERPSight/
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Thêm path cho backend để đảm bảo import pydantic models đúng
_BACKEND = os.path.join(_ROOT, "erpsight", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Cấu hình Page
st.set_page_config(page_title="ERPSight AI Live Dashboard", layout="wide", page_icon="🛡️")

# ─── Lazy Imports ───────────────────────────────────────────────────────────
# Load .env trước khi import bất kỳ component nào sử dụng settings
from erpsight.backend.config.settings import settings

def load_agents_live():
    """Import và khởi tạo Agent 2 và Agent 3 hàng thật."""
    from erpsight.backend.agents.insight_agent import process_anomaly_through_insight_agent
    from erpsight.backend.executor.action_executor import ActionExecutor
    return process_anomaly_through_insight_agent, ActionExecutor()

# ─── Paths ────────────────────────────────────────────────────────────────────
QUEUE_PATH     = os.path.join(_ROOT, "erpsight", "backend", "api", "routes", "approval_queue.json")
FEEDBACK_PATH  = os.path.join(_ROOT, "erpsight", "backend", "api", "routes", "feedback_loop.json")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _load_json(path: str) -> list:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_json(path: str, data: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Session State ────────────────────────────────────────────────────────────
for key in ["insight", "action_req", "incident_id", "eval_result", "error"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ─── UI ───────────────────────────────────────────────────────────────────────
st.title("🛡️ ERPSight Live Agent Dashboard")
st.markdown("Luồng xử lý **Agentic** thực tế: Phối hợp giữa Agent 2 (Reasoning) và Agent 3 (Gatekeeper).")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ Agent 1 — Sensor Input")
    module_sel = st.selectbox("Module ERP Target", ["stock.quant", "sale.order", "purchase.order", "helpdesk.ticket"])
    z_input    = st.number_input("Z-Score (Severity):", value=3.5, step=0.1)
    raw_text   = st.text_area(
        "Raw Data (JSON):",
        value='{"product_name": "RAM Corsair 32GB", "qty_on_hand": -5, "location": "WH/Stock"}',
        height=100,
    )
    st.info(f"GEMINI_API_KEY: {'✅ Sẵn sàng' if settings.GEMINI_API_KEY else '❌ Thiếu'}")
    st.divider()
    run_btn = st.button("🚨 Chạy Toàn Bộ Pipeline", use_container_width=True, type="primary")

# ── MAIN PIPELINE EXECUTION ───────────────────────────────────────────────────
if run_btn:
    try:
        # 1. Parse Input
        raw_dict = json.loads(raw_text)
        st.session_state.error = None
        st.session_state.incident_id = f"inc_{str(uuid.uuid4())[:6]}"
        
        # 2. Load Real Components
        process_insight, executor = load_agents_live()
        
        with st.spinner("🧠 Agent 2: Gemini Pro đang suy luận qua 4 tầng..."):
            # Import schema đúng chỗ
            from erpsight.backend.models.domain.agent_schemas import AnomalyData, ActionRequest
            
            # Khởi tạo anomaly data
            anomaly = AnomalyData(
                module=module_sel,
                z_score=z_input,
                raw_data_preview=raw_dict
            )
            
            # --- AGENT 2 CALLBACK (LIVE) ---
            insight_report = process_insight(anomaly)
            st.session_state.insight = insight_report
            
            # --- AGENT 3 PREPARATION ---
            # Giả lập similarity và coverage (trong thực tế lấy từ FAISS/Tool metadata)
            conf_score = executor.calculate_composite_score(
                z_score=z_input, 
                similarity_score=0.85, 
                data_coverage=0.92
            )
            
            # Tạo ActionRequest
            action_request = ActionRequest(
                action_type=insight_report.suggested_action,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                confidence_score=conf_score,
                payload={"product_sku": raw_dict.get("product_name", "UNKNOWN"), "reason": insight_report.suggested_action},
                status="pending"
            )
            st.session_state.action_req = action_request
            
            # --- AGENT 3 CALLBACK (GATEKEEPER) ---
            eval_result = executor.evaluate_and_execute(action_request, st.session_state.incident_id)
            st.session_state.eval_result = eval_result

    except Exception as e:
        st.session_state.error = f"Lỗi hệ thống: {str(e)}"
        st.session_state.insight = None
        st.session_state.action_req = None

# ── Display ───────────────────────────────────────────────────────────────────
if st.session_state.error:
    st.error(f"⚠️ {st.session_state.error}")

col1, col2 = st.columns([1.6, 1])

with col1:
    st.subheader("🧠 Báo cáo Phân Tích (Agent 2)")
    if st.session_state.insight:
        r = st.session_state.insight
        st.info(f"**🔍 Quan Sát:**\n\n{r.observation}")
        evidence_md = "\n".join(f"- {e}" for e in r.evidence)
        st.warning(f"**📊 Bằng Chứng (Live Data):**\n\n{evidence_md}")
        st.error(f"**🧠 Giả Thuyết:**\n\n{r.hypothesis}")
        st.success(f"**🎯 Đề Xuất Hành Động:**\n\n`{r.suggested_action}`")
    else:
        st.info("Chờ kích hoạt pipeline...")

with col2:
    st.subheader("🛡️ Cổng An Toàn (Agent 3)")
    if st.session_state.action_req and st.session_state.eval_result:
        a_req = st.session_state.action_req
        res = st.session_state.eval_result

        st.metric("Confidence Score", f"{a_req.confidence_score:.4f}")
        st.caption(f"Yêu cầu: `{a_req.action_type}`")

        if res.get("status") == "auto_executed":
            st.success(f"✅ **AUTO-EXECUTED**\n\nIdempotency Key: `{res.get('idempotency_key')}`")
        else:
            st.warning(f"🚫 **Safety Gate Blocked**\n\nLý do: {res.get('reason', 'Rủi ro danh mục')}")
            st.markdown("#### Human in the Loop")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Phê Duyệt", use_container_width=True):
                    # Manual execute (Agent 3 logic)
                    _, executor = load_agents_live()
                    executor.execute_action(a_req.action_type, a_req.payload, f"manual_{st.session_state.incident_id}")
                    # Xoá queue
                    q = _load_json(QUEUE_PATH)
                    q = [x for x in q if x.get("incident_id") != st.session_state.incident_id]
                    _save_json(QUEUE_PATH, q)
                    st.success("Đã thi hành thủ công.")
            with c2:
                if st.button("❌ Từ Chối", use_container_width=True):
                    # Lưu feedback loop
                    fb = _load_json(FEEDBACK_PATH)
                    q = _load_json(QUEUE_PATH)
                    target = next((x for x in q if x.get("incident_id") == st.session_state.incident_id), None)
                    if target:
                        target.update({"user_feedback": "Manual Reject", "status": "rejected_by_human"})
                        fb.append(target)
                        _save_json(FEEDBACK_PATH, fb)
                        q = [x for x in q if x.get("incident_id") != st.session_state.incident_id]
                        _save_json(QUEUE_PATH, q)
                        st.error("Đã ghi nhận Feedback.")
    else:
        st.info("Phòng tuyến an ninh đang chờ...")

# ── Logs ──────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Backend Logs (Real-time JSON)")
lc1, lc2 = st.columns(2)
with lc1:
    st.caption("📦 Hàng chờ phê duyệt (approval_queue.json)")
    st.json(_load_json(QUEUE_PATH))
with lc2:
    st.caption("🧠 Feedback Loop (feedback_loop.json)")
    st.json(_load_json(FEEDBACK_PATH))
