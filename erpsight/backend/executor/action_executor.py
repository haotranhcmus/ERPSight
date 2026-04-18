import json
import logging
import math
import os
import datetime
from typing import Dict, Any

from erpsight.backend.models.domain.agent_schemas import ActionRequest
from erpsight.backend.adapters.odoo_client import OdooClient

logger = logging.getLogger(__name__)

class ActionExecutor:
    """Quản trị luồng thay đổi thực trạng xuống Odoo đảm bảo rủi ro tối thiểu."""
    
    def __init__(
        self, 
        whitelist_path: str = "erpsight/backend/config/whitelist.json", 
        approval_queue_path: str = "erpsight/backend/api/routes/approval_queue.json"
    ):
        self.odoo_client = OdooClient()
        self.approval_queue_path = approval_queue_path
        
        try:
            with open(whitelist_path, 'r', encoding='utf-8') as f:
                self.whitelist = json.load(f)
        except Exception:
            self.whitelist = {}

        os.makedirs(os.path.dirname(self.approval_queue_path), exist_ok=True)

    def calculate_composite_score(self, z_score: float, similarity_score: float, data_coverage: float) -> float:
        """
        Trọng số tính điểm tin cậy tổng thể:
        w1 (0.4): Anomaly_score - Chuyển hóa Logit Sigmoid đưa mức độ nghiêm trọng về tỉ lệ [0,1].
        w2 (0.4): Similarity_score - So khớp vector FAISS với tiền lệ giải quyết trong DB của cty.
        w3 (0.2): Data_coverage - Độ phủ và đầy đủ context LLM điều tra.
        """
        w1, w2, w3 = 0.4, 0.4, 0.2
        anomaly_score = 1 / (1 + math.exp(-z_score))
        
        confidence = (w1 * anomaly_score) + (w2 * similarity_score) + (w3 * data_coverage)
        return min(max(confidence, 0.0), 1.0)

    def evaluate_and_execute(self, request: ActionRequest, incident_id: str) -> Dict[str, Any]:
        """Kiểm soát tính an toàn của một Action trước khi xuống Adapter Odoo."""
        action_name = request.action_type
        action_info = self.whitelist.get(action_name, {})
        risk_level = action_info.get("risk_level", "high")

        # Safety Gate: Điểm tin cậy trên 0.85 đồng thời hành động phải nằm trong khung an toàn Low Risk.
        if request.confidence_score < 0.85 or risk_level != "low":
            request.status = "pending_approval"
            self._push_to_approval_queue(request, incident_id, reason=f"Safety Gate block: Score {request.confidence_score:.2f}, Risk {risk_level}")
            return {"status": "pending_approval", "incident_id": incident_id}

        # Idempotency Key: Khóa sinh ra từ incident_id cấu thành nên rào chặn trùng lặp thao tác/spam xuống hạ tầng ERP.
        idempotency_key = f"idx_{incident_id}_{action_name}"
        return self.execute_action(action_name, request.payload, idempotency_key)

    def _push_to_approval_queue(self, request: ActionRequest, incident_id: str, reason: str):
        """
        Hàng chờ duyệt: Nơi cất giữ các hành vi bị chặn để chờ Human duyệt và lưu lý do vào Feedback Loop.
        """
        queue_data = []
        if os.path.exists(self.approval_queue_path):
            with open(self.approval_queue_path, 'r', encoding='utf-8') as f:
                try:
                    queue_data = json.load(f)
                except Exception:
                    pass
                    
        queue_data.append({
            "incident_id": incident_id,
            "reason": reason,
            "action_type": request.action_type,
            "confidence_score": request.confidence_score,
            "payload": request.payload,
            "status": "pending_approval",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        
        with open(self.approval_queue_path, 'w', encoding='utf-8') as f:
            json.dump(queue_data, f, ensure_ascii=False, indent=2)

    def execute_action(self, action_name: str, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        """Khớp và kích nổ lệnh ERP trực tiếp thông qua các Action được Team lập trình sẵn."""
        method = getattr(self.odoo_client, action_name, None)
        if callable(method):
            try:
                kwargs = payload.copy()
                kwargs['idempotency_key'] = idempotency_key
                result = method(**kwargs)
                return {"status": "auto_executed", "result": result, "idempotency_key": idempotency_key}
            except Exception as e:
                return {"status": "failed", "error": str(e), "idempotency_key": idempotency_key}
        
        return {"status": "failed", "error": "Action out of support."}
