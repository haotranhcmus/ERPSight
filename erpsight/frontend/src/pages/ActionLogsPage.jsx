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
                    <th>Đối tượng</th>
                    <th>Chế độ</th>
                    <th>Kết quả</th>
                    <th>Thời gian</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => {
                    const entity =
                      l.params?.product_sku || l.params?.partner_name || "—";
                    return (
                      <tr key={l.log_id}>
                        <td>
                          <strong style={{ fontSize: 13 }}>
                            {ACTION_LABELS[l.action_type] || l.action_type}
                          </strong>
                          {l.error_message && (
                            <div
                              style={{
                                fontSize: 11,
                                color: "var(--danger)",
                                marginTop: 2,
                              }}
                            >
                              {l.error_message}
                            </div>
                          )}
                        </td>
                        <td
                          style={{
                            fontSize: 13,
                            color: "var(--text-secondary)",
                          }}
                        >
                          {entity}
                        </td>
                        <td>
                          {l.auto_executed ? (
                            <Badge type="info">Tự động</Badge>
                          ) : (
                            <Badge type="warning">Thủ công</Badge>
                          )}
                        </td>
                        <td>
                          {l.undone ? (
                            <Badge type="secondary">Đã hoàn tác</Badge>
                          ) : l.success ? (
                            <Badge type="success">Thành công</Badge>
                          ) : (
                            <Badge type="danger">Thất bại</Badge>
                          )}
                        </td>
                        <td
                          style={{
                            fontSize: 12,
                            color: "var(--text-secondary)",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {l.created_at?.slice(0, 19).replace("T", " ")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
