import { useEffect, useState } from "react";
import { History } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import { getActionLogs } from "../services/api";

const ACTION_LABELS = {
  send_internal_alert: "Gửi cảnh báo nội bộ",
  send_margin_alert: "Gửi cảnh báo lợi nhuận",
  send_churn_risk_alert: "Cảnh báo khách hàng",
  create_activity_task: "Tạo nhắc nhở",
  create_reengagement_activity: "Tạo lịch gọi điện",
  flag_product_for_price_review: "Đánh dấu xem xét giá",
  create_purchase_order: "Tạo đơn đặt hàng",
  update_sale_price: "Cập nhật giá bán",
};

export default function ActionLogsPage() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    getActionLogs().then((r) => setLogs(r.data));
  }, []);

  return (
    <>
      <Topbar title="Lịch sử hành động" />
      <div className="page-content">
        <div className="card">
          {logs.length === 0 ? (
            <div className="empty-state">
              <History
                size={40}
                color="var(--text-secondary)"
                style={{ marginBottom: 10 }}
              />
              <h3>Chưa có lịch sử</h3>
              <p>Các hành động đã thực thi sẽ hiển thị ở đây.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Hành động</th>
                    <th>Chế độ</th>
                    <th>Kết quả</th>
                    <th>Lỗi</th>
                    <th>Thời gian</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => (
                    <tr key={l.log_id}>
                      <td>
                        <strong>
                          {ACTION_LABELS[l.action_type] || l.action_type}
                        </strong>
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--text-secondary)",
                            marginTop: 2,
                          }}
                        >
                          {l.params?.product_sku ||
                            l.params?.partner_name ||
                            ""}
                        </div>
                      </td>
                      <td>
                        {l.auto_executed ? (
                          <Badge type="info">Tự động</Badge>
                        ) : (
                          <Badge type="warning">Thủ công</Badge>
                        )}
                      </td>
                      <td>
                        {l.success ? (
                          <Badge type="success">Thành công</Badge>
                        ) : (
                          <Badge type="danger">Thất bại</Badge>
                        )}
                      </td>
                      <td
                        style={{
                          fontSize: 12,
                          color: "var(--danger)",
                          maxWidth: 200,
                        }}
                      >
                        {l.error_message || "—"}
                      </td>
                      <td
                        style={{ fontSize: 12, color: "var(--text-secondary)" }}
                      >
                        {l.created_at?.slice(0, 19).replace("T", " ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
