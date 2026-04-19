"""
agents/insight_agent.py

Agent 2 — InsightAgent (Analysis).

Two modes:
  1. LLM mode  — LangGraph ReAct agent with Gemini 2.5 Pro (requires GEMINI_API_KEY)
  2. Rule-based fallback — deterministic analysis using KB1→KB3 templates

Public API used by pipeline:
    analyze(event: AnomalyEvent) -> InsightReport
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from erpsight.backend.config.settings import settings
from erpsight.backend.models.anomaly_event import AnomalyEvent, AnomalyType
from erpsight.backend.models.insight_report import InsightReport, RecommendedAction
from erpsight.backend.services.confidence_scorer import compute_confidence

logger = logging.getLogger(__name__)

# ── Circuit breaker — skip LLM for 5 min after quota-exhausted error ─────────
# Resets automatically; no server restart needed.
_quota_exhausted_until: float = 0.0


def _is_quota_exhausted() -> bool:
    return time.monotonic() < _quota_exhausted_until


def _mark_quota_exhausted(seconds: int = 300) -> None:
    global _quota_exhausted_until
    _quota_exhausted_until = time.monotonic() + seconds
    logger.warning(
        "LLM quota exhausted — rule-based fallback active for %d seconds.", seconds
    )


# ── Lazy OdooClient (shared by tool functions) ────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is None:
        from erpsight.backend.adapters.odoo_client import OdooClient
        _client = OdooClient()
    return _client


# ── LangChain tool definitions (unchanged, used by LangGraph agent) ───────────

def _define_tools():
    from langchain.tools import tool

    @tool
    def tool_fetch_sales_context(product_sku: str = None, date_from: str = None, date_to: str = None) -> dict:
        """Lấy ngữ cảnh doanh số: tổng đơn hàng, doanh thu, top sản phẩm, xu hướng theo ngày."""
        from erpsight.backend.tools.insight_tools import fetch_sales_context
        return fetch_sales_context(_get_client(), product_sku=product_sku, date_from=date_from, date_to=date_to)

    @tool
    def tool_fetch_inventory_context(product_sku: str) -> dict:
        """Kiểm tra mức tồn kho thực tế và PO nhập hàng đang chờ xử lý cho một sản phẩm cụ thể."""
        from erpsight.backend.tools.insight_tools import fetch_inventory_context
        return fetch_inventory_context(_get_client(), product_sku=product_sku)

    @tool
    def tool_fetch_purchase_context(product_sku: str) -> dict:
        """Xem lịch sử mua hàng: giá nhập cũ/mới, thay đổi giá, tên nhà cung cấp, lead time."""
        from erpsight.backend.tools.insight_tools import fetch_purchase_context
        return fetch_purchase_context(_get_client(), product_sku=product_sku)

    @tool
    def tool_fetch_helpdesk_context(partner_name: str = None, date_from: str = None) -> dict:
        """Tóm tắt phiếu hỗ trợ khách hàng: số lượng, mức độ ưu tiên, thời gian giải quyết."""
        from erpsight.backend.tools.insight_tools import fetch_helpdesk_context
        return fetch_helpdesk_context(_get_client(), partner_name=partner_name, date_from=date_from)

    return [
        tool_fetch_sales_context,
        tool_fetch_inventory_context,
        tool_fetch_purchase_context,
        tool_fetch_helpdesk_context,
    ]


REACT_SYSTEM_PROMPT = """Bạn là InsightAgent tại hệ thống ERPSight. Chẩn đoán bất thường từ Odoo ERP.

LUẬT BẮT BUỘC:
1. Ngôn ngữ: 100% Tiếng Việt.
2. Dùng tối thiểu 2 Tools để thu thập bằng chứng trước khi kết luận.
3. Suy luận 4 tầng:
   - Observation: Nhận diện bất thường.
   - Evidence: Dữ liệu cụ thể (số, mã) từ Tools. KHÔNG bịa số liệu.
   - Hypothesis: Phân tích nhân quả đa module.
   - Suggested Action: Đề xuất action code cụ thể (vd: create_purchase_order).
"""


# ── LLM mode (LangGraph ReAct) ───────────────────────────────────────────────

def _get_langgraph_agent():
    """Create LangGraph ReAct agent + structured parser (lazy init).

    Provider priority: Groq (if GROQ_API_KEY set) > Gemini (if GEMINI_API_KEY set).
    """
    from langgraph.prebuilt import create_react_agent
    from erpsight.backend.models.domain.agent_schemas import InsightReport as LGInsightReport

    if settings.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise ImportError(
                "langchain-groq not installed. Run: pip install langchain-groq"
            ) from exc
        llm = ChatGroq(
            model=settings.GROQ_MODEL,
            temperature=0,
            groq_api_key=settings.GROQ_API_KEY,
        )
        logger.debug("LLM provider: Groq (%s)", settings.GROQ_MODEL)
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0,
            google_api_key=settings.GEMINI_API_KEY,
            max_retries=0,  # disable SDK-level tenacity retry — fail fast on 429
        )
        logger.debug("LLM provider: Gemini (%s)", settings.GEMINI_MODEL)

    tools = _define_tools()
    agent = create_react_agent(llm, tools=tools, prompt=REACT_SYSTEM_PROMPT)
    structured_llm = llm.with_structured_output(LGInsightReport)
    return agent, structured_llm


def _llm_analyze(event: AnomalyEvent) -> InsightReport:
    """Run LangGraph agent then parse into the new InsightReport schema."""
    agent, structured_parser = _get_langgraph_agent()

    prompt = (
        f"Anomaly Type: {event.anomaly_type}\n"
        f"Product: {event.product_name or 'N/A'} (ID {event.product_id})\n"
        f"Customer: {event.partner_name or 'N/A'} (ID {event.partner_id})\n"
        f"Metric: {event.metric} = {event.metric_value:.2f} (threshold {event.threshold:.2f})\n"
        f"Z-Score: {event.z_score:.2f} | Severity: {event.severity}\n"
        f"Details: {event.details}"
    )

    raw_result = agent.invoke({"messages": [("user", prompt)]})
    lg_report = structured_parser.invoke(
        f"Trích xuất kết quả sau thành InsightReport Pydantic:\n\n{raw_result['messages'][-1].content}"
    )

    # Map old-schema LangGraph output → new InsightReport
    report_id = f"rpt-{uuid.uuid4().hex[:8]}"
    actions: List[RecommendedAction] = []
    for idx, action_type in enumerate(lg_report.suggested_actions or []):
        action_type = action_type.strip()
        if action_type:
            actions.append(RecommendedAction(
                action_type=action_type,
                reason=lg_report.hypothesis or "",
                priority=idx + 1,
            ))

    # Fallback: if LLM returned nothing usable, produce a generic alert
    if not actions:
        actions.append(RecommendedAction(
            action_type="send_internal_alert",
            reason=lg_report.hypothesis or "LLM phát hiện bất thường — cần xem xét thủ công.",
            priority=1,
        ))

    confidence = compute_confidence(event.score)

    return InsightReport(
        report_id=report_id,
        event_id=event.event_id,
        scenario=event.anomaly_type,
        summary=lg_report.observation or "",
        evidence=[lg_report.evidence] if lg_report.evidence else [],
        root_cause=lg_report.hypothesis or "",
        recommended_actions=actions,
        confidence=confidence,
        anomaly_score=event.score,
    )


# ── Rule-based fallback ──────────────────────────────────────────────────────

def _rule_based_analyze(event: AnomalyEvent) -> InsightReport:
    """Deterministic analysis for each known anomaly type (KB1–KB3)."""
    report_id = f"rpt-{uuid.uuid4().hex[:8]}"
    # Use the detector's own confidence (already calibrated per anomaly type).
    # compute_confidence(event.score) is wrong here because detectors use different
    # score scales (z-score, margin delta, days remaining) not normalised to 0-1.
    confidence = event.confidence
    d = event.details
    actions: List[RecommendedAction] = []
    evidence: List[str] = []
    summary = ""
    root_cause = ""
    deadline = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    atype = event.anomaly_type

    # ── KB1: Demand Spike / Stockout Risk ─────────────────────────────────
    if atype in (AnomalyType.DEMAND_SPIKE, AnomalyType.STOCKOUT_RISK):
        product = event.product_name or f"product#{event.product_id}"
        product_sku = d.get("product_sku", "")

        if atype == AnomalyType.DEMAND_SPIKE:
            current_qty = d.get("daily_qty", event.metric_value)
            mean_qty = d.get("mean_daily", 0)
            std_qty = d.get("std_daily", 0)
            z_val = d.get("z_score", event.z_score)
            window = d.get("window_days", 30)
            summary = f"Doanh số {product} tăng đột biến trong {window} ngày qua."
            if mean_qty > 0 and std_qty > 0:
                evidence.append(
                    f"Doanh số ngày gần nhất: {current_qty:.0f} SP. "
                    f"Trung bình {window} ngày: {mean_qty:.1f} ± {std_qty:.1f} SP/ngày. "
                    f"Z = ({current_qty:.1f} − {mean_qty:.1f}) ÷ {std_qty:.1f} = {z_val:.2f} "
                    f"→ vượt ngưỡng {event.threshold:.1f}σ."
                )
            else:
                evidence.append(f"Z-score {z_val:.2f} vượt ngưỡng {event.threshold:.1f}.")
            root_cause = "Nhu cầu tăng đột biến — có thể do chiến dịch marketing hoặc xu hướng mùa vụ."
        else:
            stock = d.get("available_qty", d.get("qty_available", 0))  # fix key mismatch
            avg_daily = d.get("avg_daily_sales", 0)
            days_rem = d.get("days_remaining", 0)
            summary = f"Tồn kho {product} còn ~{days_rem:.0f} ngày, dưới ngưỡng an toàn {int(event.threshold)} ngày."
            if avg_daily > 0:
                evidence.append(
                    f"Tồn kho hiện tại: {stock:.0f} SP. "
                    f"Tốc độ bán TB: {avg_daily:.2f} SP/ngày. "
                    f"Dự báo hết hàng: {stock:.0f} ÷ {avg_daily:.2f} = {days_rem:.0f} ngày. "
                    f"Ngưỡng an toàn tối thiểu: {int(event.threshold)} ngày."
                )
            else:
                evidence.append(f"Tồn kho {stock:.0f} SP, dự báo còn {days_rem:.0f} ngày.")
            root_cause = "Tốc độ bán vượt tốc độ nhập hàng — cần đặt thêm hàng ngay."

        # Send internal alert (low-risk, auto)
        alert_params = {
            "res_model": "product.template",
            "res_id_lookup": {"field": "default_code", "value": product_sku},
            "subject": f"[ERPSight] Cảnh báo tồn kho – {product}",
            "message_body": summary,
            "notify_user_logins": ["admin"],
        }
        if not product_sku and event.product_id:
            alert_params["_odoo_product_id"] = event.product_id
        # Suggest PO first (priority=1) when supplier info is available — this is the key action
        supplier = d.get("supplier_name", "")
        if supplier:
            actions.append(RecommendedAction(
                action_type="create_purchase_order",
                params={
                    "product_sku": product_sku,
                    "supplier_name": supplier,
                    "qty": int(d.get("suggested_qty", 50)),
                    "price_unit": d.get("last_price_unit", 0),
                    "date_planned": deadline,
                    "note": f"[AI] Auto-PO: {summary}",
                },
                reason="Bổ sung hàng để tránh hết tồn.",
                priority=1,
            ))
        # Internal alert fallback (priority=1 if no supplier, else priority=2)
        actions.append(RecommendedAction(
            action_type="send_internal_alert",
            params=alert_params,
            reason=root_cause,
            priority=1 if not supplier else 2,
        ))
        # Activity task (lowest priority)
        activity_params = {
            "res_model": "product.template",
            "res_id_lookup": {"field": "default_code", "value": product_sku},
            "activity_type_name": "To Do",
            "summary": f"Kiểm tra tồn kho {product}",
            "note": summary,
            "date_deadline": deadline,
            "assigned_to_login": "admin",
        }
        if not product_sku and event.product_id:
            activity_params["_odoo_product_id"] = event.product_id
        actions.append(RecommendedAction(
            action_type="create_activity_task",
            params=activity_params,
            reason="Tạo nhắc nhở kiểm tra và bổ sung hàng.",
            priority=3,
        ))

    # ── KB2: Margin Erosion ───────────────────────────────────────────────
    elif atype == AnomalyType.MARGIN_EROSION:
        product = event.product_name or f"product#{event.product_id}"
        margin = d.get("avg_margin_pct", 0)          # already in percent (e.g. 0.28 = 0.28%)
        sale_price = d.get("sale_price", 0)           # current selling price
        purchase_price = d.get("purchase_price", 0)   # latest PO / supplier price
        standard_price = d.get("standard_price", 0)   # Odoo standard cost (reference)
        threshold_pct = settings.MARGIN_RISK_THRESHOLD * 100

        summary = f"Biên lợi nhuận {product} chỉ còn {margin:.2f}%, dưới ngưỡng cảnh báo {threshold_pct:.0f}%."

        # Show the actual numbers used in the calculation
        cost = purchase_price if purchase_price > 0 else standard_price
        if sale_price > 0 and cost > 0:
            calc_margin = (sale_price - cost) / sale_price * 100
            evidence.append(
                f"Giá bán hiện tại: {sale_price:,.0f}đ | Giá vốn: {cost:,.0f}đ. "
                f"Biên LN = ({sale_price:,.0f} − {cost:,.0f}) ÷ {sale_price:,.0f} × 100 = {calc_margin:.2f}%. "
                f"Ngưỡng cảnh báo: {threshold_pct:.0f}%."
            )
            if standard_price > 0 and purchase_price > 0 and abs(purchase_price - standard_price) > 1:
                price_chg_pct = (purchase_price - standard_price) / standard_price * 100
                evidence.append(
                    f"Giá vốn tham chiếu (standard): {standard_price:,.0f}đ → "
                    f"Giá PO gần nhất: {purchase_price:,.0f}đ ({price_chg_pct:+.1f}%). "
                    f"Giá bán chưa được điều chỉnh tương ứng."
                )
        else:
            evidence.append(f"Biên lợi nhuận trung bình các đơn gần đây: {margin:.2f}%.")

        root_cause = "Giá nhập tăng nhưng giá bán chưa được cập nhật tương ứng."

        # Derived params
        price_change_pct = (
            (purchase_price - standard_price) / standard_price * 100
            if standard_price > 0 and purchase_price > 0 else 0
        )
        target_margin = 0.15
        suggested_sale = round(cost / (1 - target_margin) / 1000) * 1000 if cost > 0 else 0

        margin_params = {
            "product_sku": d.get("product_sku", ""),
            "old_purchase_price": standard_price,
            "new_purchase_price": purchase_price,
            "price_change_pct": round(price_change_pct, 1),
            "current_sale_price": sale_price,
            "current_margin_pct": margin,
            "projected_daily_loss": 0,
            "notify_user_logins": ["admin"],
        }
        if not margin_params["product_sku"] and event.product_id:
            margin_params["_odoo_product_id"] = event.product_id

        # Propose price update first (priority=1) — this is the key action user should act on
        if suggested_sale > 0 and sale_price > 0 and suggested_sale > sale_price:
            price_params = {
                "product_sku": d.get("product_sku", ""),
                "current_sale_price": sale_price,
                "new_sale_price": suggested_sale,
                "current_margin_pct": round(margin, 2),
                "reason": f"Tăng giá bán lên {suggested_sale:,.0f}đ để đạt margin ~{target_margin*100:.0f}%. Giá vốn hiện tại: {cost:,.0f}đ.",
            }
            if not price_params["product_sku"] and event.product_id:
                price_params["_odoo_product_id"] = event.product_id
            actions.append(RecommendedAction(
                action_type="update_sale_price",
                params=price_params,
                reason=f"Tăng giá bán lên {suggested_sale:,.0f}đ để đạt margin {target_margin*100:.0f}%.",
                priority=1,
            ))

        flag_params = {
            "product_sku": d.get("product_sku", ""),
            "current_cost": cost,
            "current_sale_price": sale_price,
            "current_margin_pct": margin,
            "suggested_new_sale_price": suggested_sale,
            "target_margin_pct": target_margin * 100,
            "note": f"[AI] {summary}",
        }
        if not flag_params["product_sku"] and event.product_id:
            flag_params["_odoo_product_id"] = event.product_id

        actions.append(RecommendedAction(
            action_type="flag_product_for_price_review",
            params=flag_params,
            reason="Gắn cờ sản phẩm cần xem xét và điều chỉnh giá bán.",
            priority=2,
        ))
        # Margin alert (lowest priority — informational)
        actions.append(RecommendedAction(
            action_type="send_margin_alert",
            params=margin_params,
            reason=root_cause,
            priority=3,
        ))

    # ── KB3: VIP Churn ────────────────────────────────────────────────────
    elif atype == AnomalyType.VIP_CHURN:
        partner = event.partner_name or f"partner#{event.partner_id}"
        silent = d.get("days_silent", 0)
        avg_cycle = d.get("avg_order_cycle_days", d.get("avg_cycle", 30))  # fix key mismatch
        last_order = d.get("last_order_date", "")
        overdue = d.get("overdue_factor", event.metric_value)
        order_count = d.get("order_count", 0)

        summary = f"Khách VIP {partner} im lặng {silent} ngày, vượt {overdue:.1f}× chu kỳ đặt hàng bình thường."
        evidence.append(
            f"Lịch sử 90 ngày: {order_count} đơn hàng, chu kỳ TB {avg_cycle:.0f} ngày/đơn. "
            f"Đơn hàng cuối: {last_order or 'N/A'}. "
            f"Đã im lặng {silent} ngày = {overdue:.2f}× chu kỳ bình thường "
            f"(ngưỡng cảnh báo: {event.threshold:.1f}×)."
        )
        root_cause = "Khách VIP có thể đã chuyển sang đối thủ hoặc gặp vấn đề chưa được giải quyết."

        churn_params = {
            "partner_name": partner,
            "last_order_date": last_order,
            "silent_days": silent,
            "avg_order_cycle": avg_cycle,
            "overdue_factor": overdue,
            "notify_user_logins": ["admin"],
        }
        if event.partner_id:
            churn_params["_odoo_partner_id"] = event.partner_id

        actions.append(RecommendedAction(
            action_type="send_churn_risk_alert",
            params=churn_params,
            reason=root_cause,
            priority=2,
        ))
        actions.append(RecommendedAction(
            action_type="create_helpdesk_ticket",
            params={
                "partner_name": partner,
                "ticket_name": f"[ERPSight KB3] Theo doi churn risk - {partner}",
                "description": (
                    f"[ERPSight] VIP Churn Alert\n"
                    f"Khach hang: {partner}\n"
                    f"Don hang cuoi: {last_order or 'N/A'}\n"
                    f"Im lang: {silent} ngay ({overdue:.2f}x chu ky trung binh {avg_cycle:.0f} ngay)\n"
                    f"Can lien he lai va xac nhan tinh trang, de xuat uu dai giu chan."
                ),
                "priority": "1",
                "silent_days": silent,
                "last_order_date": last_order,
                "overdue_factor": overdue,
            },
            reason="Tạo helpdesk ticket nội bộ để team Sales theo dõi và xử lý rủi ro mất khách VIP.",
            priority=1,
        ))
        actions.append(RecommendedAction(
            action_type="create_reengagement_activity",
            params={
                "partner_name": partner,
                "summary": f"Re-engage VIP {partner}",
                "date_deadline": deadline,
                "assigned_to_login": "admin",
                "note": summary,
                "last_order_date": last_order,
                "silent_days": silent,
                "has_recent_complaint": d.get("has_recent_complaint", False),
            },
            reason="Tạo hoạt động liên hệ lại khách VIP.",
            priority=3,
        ))

    # ── Catch-all (Isolation Forest / unknown) ────────────────────────────
    else:
        product_label = event.product_name or event.partner_name or f"product#{event.product_id}"
        details_lines = []
        if event.details:
            d_vals = event.details
            if d_vals.get("total_qty"):
                details_lines.append(f"Sản lượng bán: {d_vals['total_qty']:.0f}")
            if d_vals.get("avg_margin_pct") is not None:
                details_lines.append(f"Biên LN TB: {d_vals['avg_margin_pct']:.2f}%")
            if d_vals.get("available_qty") is not None:
                details_lines.append(f"Tồn kho: {d_vals['available_qty']:.0f}")
        detail_str = " | ".join(details_lines) if details_lines else f"Điểm bất thường: {event.metric_value:.3f}"

        summary = (
            f"Mô hình Isolation Forest phát hiện {product_label} có tổ hợp chỉ số bất thường. "
            f"{detail_str}."
        )
        evidence.append(
            f"IF anomaly score: {event.metric_value:.4f} (càng cao càng bất thường). "
            f"Sản phẩm này là outlier đa biến trong toàn bộ danh mục."
        )
        root_cause = (
            "Kết hợp bất thường của nhiều chỉ số (doanh số, biên LN, tồn kho) — "
            "không trùng với KB1–KB3, cần điều tra thêm."
        )
        # Use send_internal_alert (informational_only in whitelist → auto-execute, no approval queue)
        actions.append(RecommendedAction(
            action_type="send_internal_alert",
            params={
                "res_model": "product.template",
                "res_id_lookup": {"field": "id", "value": event.product_id},
                "subject": f"[ERPSight] Anomaly đa biến – {product_label}",
                "message_body": summary,
                "notify_user_logins": ["admin"],
            },
            reason=root_cause,
            priority=1,
        ))

    return InsightReport(
        report_id=report_id,
        event_id=event.event_id,
        scenario=atype,
        summary=summary,
        evidence=evidence,
        root_cause=root_cause,
        recommended_actions=actions,
        confidence=confidence,
        anomaly_score=event.score,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(event: AnomalyEvent) -> InsightReport:
    """
    Central entry point for Agent 2.

    Provider priority: Groq > Gemini > rule-based fallback.
    Circuit breaker: after a quota-exhausted (429) error, LLM is skipped
    for the next 5 minutes to keep the pipeline fast.
    """
    has_llm = bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY)

    if has_llm and not _is_quota_exhausted():
        try:
            report = _llm_analyze(event)
            logger.info("LLM analysis complete for %s", event.event_id)
            return report
        except Exception as exc:
            err = str(exc).upper()
            if "RESOURCE_EXHAUSTED" in err or "429" in err or "RATE_LIMIT" in err or "QUOTA" in err:
                _mark_quota_exhausted(300)  # skip LLM for 5 minutes
            else:
                logger.exception(
                    "LLM analysis failed for %s — falling back to rules", event.event_id
                )

    report = _rule_based_analyze(event)
    logger.info("Rule-based analysis complete for %s", event.event_id)
    return report
