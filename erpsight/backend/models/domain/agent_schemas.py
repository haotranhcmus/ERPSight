from typing import Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field

class AnomalyData(BaseModel):
    module: str = Field(..., description="Tên module trong Odoo phát sinh bất thường (ví dụ: 'Sales', 'Inventory').")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Thời gian phát hiện bất thường.")
    z_score: float = Field(..., description="Điểm Z-score mức độ bất thường do mô hình phân tích trả về.")
    raw_data_preview: Dict[str, Any] = Field(..., description="Bản xem trước dữ liệu thô gây ra bất thường.")

class InsightReport(BaseModel):
    observation: str = Field(..., description="Tầng 1: Quan sát tổng quan về dữ liệu bất thường phát hiện được.")
    evidence: List[str] = Field(..., description="Tầng 2: Danh sách các bằng chứng cụ thể rút ra từ Odoo.")
    hypothesis: str = Field(..., description="Tầng 3: Giả thuyết nguyên nhân liên module (tiếng Việt).")
    suggested_action: str = Field(..., description="Tầng 4: Đề xuất hành động khắc phục.")

class ActionRequest(BaseModel):
    action_type: str = Field(..., description="LOW, MEDIUM, HIGH để quyết định phê duyệt.")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Điểm tin cậy (0 đến 1) tính từ Z-score và similar incidents.")
    payload: Dict[str, Any] = Field(..., description="Payload đẩy về Odoo qua Adapter.")
    status: str = Field(default="pending_approval", description="pending_approval, auto_executed, rejected")
