import { useEffect, useState } from "react";
import { Play, Loader2 } from "lucide-react";
import Topbar from "../components/Topbar";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";
import {
  triggerPipeline,
  getPipelineStatus,
  getAnomalies,
  getReports,
  getApprovals,
  getActionLogs,
} from "../services/api";

const TYPE_LABELS = {
  demand_spike: "Nhu cầu tăng đột biến",
  stockout_risk: "Nguy cơ hết hàng",
  margin_erosion: "Lợi nhuận đang giảm",
  vip_churn: "Khách VIP có thể rời bỏ",
  isolation_forest: "Nhiều chỉ số bất thường",
};

const SEVERITY_LABELS = {
  high: "Khẩn cấp",
  medium: "Cần chú ý",
  low: "Theo dõi",
};

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

export default function Dashboard() {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [reports, setReports] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [logs, setLogs] = useState([]);

  const refresh = async () => {
    const [a, r, ap, l] = await Promise.all([
      getAnomalies(),
      getReports(),
      getApprovals(),
      getActionLogs(),
    ]);
    setAnomalies(a.data);
    setReports(r.data);
    setApprovals(ap.data);
    setLogs(l.data);
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleTrigger = async () => {
    setRunning(true);
    setStatus(null);
    await triggerPipeline();
    // Poll for completion
    const poll = setInterval(async () => {
      const res = await getPipelineStatus();
      if (res.data && !res.data.status?.includes("no_run")) {
        setStatus(res.data);
        setRunning(false);
        clearInterval(poll);
        refresh();
      }
    }, 2000);
  };

  const pendingCount = approvals.filter((a) => a.status === "pending").length;

  return (
    <>
      <Topbar title="Tổng quan">
        <button
          className="btn btn-primary"
          onClick={handleTrigger}
          disabled={running}
        >
          {running ? (
            <>
              <Loader2 size={15} className="spin" /> Đang phân tích...
            </>
          ) : (
            <>
              <Play size={15} /> Chạy phân tích
            </>
          )}
        </button>
      </Topbar>
      <div className="page-content">
        {status && (
          <div className="pipeline-bar">
            <span className="status-text">
              Kết quả lần cuối: phát hiện {status.anomalies_detected} bất thường
              → {status.actions_auto_executed} tự thực thi,{" "}
              {status.actions_queued_for_approval} chờ duyệt
            </span>
          </div>
        )}

        <div className="stat-grid">
          <StatCard value={anomalies.length} label="Bất thường phát hiện" />
          <StatCard value={reports.length} label="Báo cáo phân tích" />
          <StatCard value={pendingCount} label="Chờ phê duyệt" />
          <StatCard value={logs.length} label="Đã thực hiện" />
        </div>

        {/* Recent anomalies (card grid) */}
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <span className="card-title">Bất thường gần đây</span>
          </div>
          {anomalies.length === 0 ? (
            <div className="empty-state">
              <h3>Chưa có dữ liệu</h3>
              <p>Nhấn "Chạy phân tích" để quét dữ liệu từ Odoo.</p>
            </div>
          ) : (
            <div className="anomaly-grid">
              {anomalies.slice(0, 6).map((a) => {
                const report = reports.find((r) => r.event_id === a.event_id);
                return (
                  <div className="anomaly-card" key={a.event_id}>
                    <div className="anomaly-card-header">
                      <strong>
                        {TYPE_LABELS[a.anomaly_type] || a.anomaly_type}
                      </strong>
                      <Badge type={a.severity}>
                        {SEVERITY_LABELS[a.severity] || a.severity}
                      </Badge>
                    </div>
                    <div className="anomaly-card-body">
                      <p>
                        <strong>
                          {a.product_name || a.partner_name || "—"}
                        </strong>
                      </p>
                      {report && (
                        <p
                          style={{
                            color: "var(--text)",
                            fontStyle: "italic",
                            fontSize: 13,
                          }}
                        >
                          {report.summary}
                        </p>
                      )}
                      {report?.recommended_actions?.length > 0 && (
                        <ul className="anomaly-actions-list">
                          {report.recommended_actions.map((act, i) => (
                            <li key={i}>
                              <span>
                                {ACTION_LABELS[act.action_type] ||
                                  act.action_type}
                              </span>
                              <Badge type="info">P{act.priority}</Badge>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent action logs */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Hành động gần đây</span>
          </div>
          {logs.length === 0 ? (
            <div className="empty-state">
              <p>Chưa có hành động nào được thực thi.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Hành động</th>
                    <th>Chế độ</th>
                    <th>Kết quả</th>
                    <th>Thời gian</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.slice(0, 10).map((l) => (
                    <tr key={l.log_id}>
                      <td>{ACTION_LABELS[l.action_type] || l.action_type}</td>
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
