from __future__ import annotations
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from erpsight.backend.config.settings import settings
from erpsight.backend.models.domain.agent_schemas import InsightReport, AnomalyData

# OdooClient được khởi tạo lazily khi gọi tool — không block lúc import
_client = None

def _get_client():
    global _client
    if _client is None:
        from erpsight.backend.adapters.odoo_client import OdooClient
        _client = OdooClient()
    return _client

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

TOOLS = [
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

def get_insight_agent():
    """Khởi tạo LangGraph ReAct Agent sử dụng Gemini Pro."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=0,
        google_api_key=settings.GEMINI_API_KEY,
    )
    agent = create_react_agent(llm, tools=TOOLS, prompt=REACT_SYSTEM_PROMPT)
    structured_llm = llm.with_structured_output(InsightReport)
    return agent, structured_llm

def process_anomaly_through_insight_agent(anomaly: AnomalyData) -> InsightReport:
    """Phân tích anomaly và trả về InsightReport chuẩn hóa."""
    agent, structured_parser = get_insight_agent()
    raw_result = agent.invoke({
        "messages": [(
            "user",
            f"Module: {anomaly.module} | Z-Score: {anomaly.z_score}\n"
            f"Raw Data Preview: {anomaly.raw_data_preview}"
        )]
    })
    return structured_parser.invoke(
        f"Trích xuất kết quả sau thành InsightReport Pydantic:\n\n{raw_result['messages'][-1].content}"
    )
