import { useEffect, useState } from "react";
import {
  TrendingDown, UserX, Zap, Package, Activity,
  ShoppingCart, Bell, Phone, Tag, ClipboardList,
  DollarSign, CheckCircle, CheckCircle2, AlertTriangle,
  BarChart3, X, Loader2, XCircle, MessageSquare,
  ChevronRight, Info, ArrowRight, Settings,
} from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import {
  getAnomalies, getReports, getApprovals, getApproval,
  approveAction, rejectAction, updateApprovalParams,
} from "../services/api";

// ── Type Config ───────────────────────────────────────────────────────────────

const TYPE_CONFIG = {
  demand_spike:     { label: "Nhu cầu tăng đột biến",    icon: Zap,          color: "#e67e22" },
  stockout_risk:    { label: "Nguy cơ hết hàng",          icon: Package,      color: "#e74c3c" },
  margin_erosion:   { label: "Lợi nhuận đang giảm mạnh", icon: TrendingDown, color: "#c0392b" },
  vip_churn:        { label: "Khách VIP có thể rời bỏ",  icon: UserX,        color: "#8e44ad" },
  isolation_forest: { label: "Nhiều chỉ số bất thường",  icon: Activity,     color: "#2980b9" },
};

const SEVERITY_LABELS = { high: "Khẩn cấp", medium: "Cần chú ý", low: "Theo dõi" };

// ── Action Config (desc + riskLevel + requiresApproval + odooPath) ────────────

const ACTION_CONFIG = {
  send_internal_alert: {
    label: "Gửi cảnh báo nội bộ", icon: Bell,
    desc: "Đăng thông báo cảnh báo vào chatter sản phẩm trong Odoo.",
    riskLevel: "low", requiresApproval: false,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  },
  send_margin_alert: {
    label: "Gửi cảnh báo lợi nhuận", icon: TrendingDown,
    desc: "Đăng bảng phân tích margin chi tiết vào chatter sản phẩm trong Odoo.",
    riskLevel: "low", requiresApproval: false,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  },
  send_churn_risk_alert: {
    label: "Gửi cảnh báo rủi ro churn", icon: UserX,
    desc: "Đăng thông tin phân tích churn vào chatter hồ sơ khách hàng trong Odoo.",
    riskLevel: "low", requiresApproval: false,
    odooPath: "Liên hệ → [khách hàng] → tab Chatter",
  },
  create_activity_task: {
    label: "Tạo nhắc nhở nội bộ", icon: ClipboardList,
    desc: "Tạo hoạt động nhắc nhở (mail.activity) gắn vào record trong Odoo.",
    riskLevel: "low", requiresApproval: false,
    odooPath: "Thảo luận → Hoạt động của tôi",
  },
  create_reengagement_activity: {
    label: "Tạo lịch gọi điện chăm sóc", icon: Phone,
    desc: "Tạo hoạt động 'Phone Call' trên hồ sơ khách hàng để nhắc nhở tái chăm sóc.",
    riskLevel: "low", requiresApproval: false,
    odooPath: "Liên hệ → [khách hàng] → tab Hoạt động",
  },
  flag_product_for_price_review: {
    label: "Gắn cờ xem xét lại giá", icon: Tag,
    desc: "Ghi chú nội bộ trên sản phẩm, đánh dấu cần điều chỉnh giá bán.",
    riskLevel: "low", requiresApproval: false,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  },
  create_purchase_order: {
    label: "Tạo đơn đặt hàng nhà cung cấp", icon: ShoppingCart,
    desc: "Tạo đơn mua hàng (draft PO) trong Odoo từ nhà cung cấp. Cần xác nhận thêm trước khi gửi đi.",
    riskLevel: "medium", requiresApproval: true,
    odooPath: "Mua hàng → Đơn mua → lọc trạng thái Nháp",
  },
  update_sale_price: {
    label: "Cập nhật giá bán", icon: DollarSign,
    desc: "Thay đổi trực tiếp giá bán của sản phẩm trong Odoo và ghi audit log.",
    riskLevel: "medium", requiresApproval: true,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → Giá bán",
  },
};

// ── Param display helpers ─────────────────────────────────────────────────────

const PARAM_LABELS = {
  product_sku: "Mã sản phẩm", partner_name: "Khách hàng",
  supplier_name: "Nhà cung cấp", old_purchase_price: "Giá nhập cũ",
  new_purchase_price: "Giá nhập mới", price_change_pct: "Giá nhập tăng",
  current_sale_price: "Giá bán hiện tại", current_margin_pct: "Biên lợi nhuận",
  projected_daily_loss: "Tổn thất ước tính/ngày", last_order_date: "Đơn hàng cuối",
  silent_days: "Số ngày im lặng", avg_order_cycle: "Chu kỳ đặt hàng TB",
  overdue_factor: "Mức độ quá hạn", qty: "Số lượng đặt",
  price_unit: "Đơn giá mua", date_planned: "Ngày nhận hàng dự kiến",
  new_sale_price: "Giá bán mới", suggested_new_sale_price: "Giá đề xuất",
  target_margin_pct: "Biên lợi nhuận mục tiêu", date_deadline: "Thời hạn",
  last_price_unit: "Giá PO gần nhất", suggested_qty: "Số lượng đề xuất",
  assigned_to_login: "Phân công cho",
};

const HIDDEN_PARAMS = new Set([
  "res_model", "res_id_lookup", "notify_user_logins", "activity_type_name",
  "attachment_context", "has_recent_complaint", "suggested_offer",
  "_odoo_product_id", "_odoo_partner_id", "message_body", "note", "subject", "reason",
]);

const CURRENCY_PARAMS = new Set([
  "old_purchase_price", "new_purchase_price", "current_sale_price",
  "projected_daily_loss", "price_unit", "new_sale_price",
  "suggested_new_sale_price", "last_price_unit",
]);

function formatParamValue(key, value) {
  if (CURRENCY_PARAMS.has(key)) return `${Number(value).toLocaleString("vi-VN")}đ`;
  if (key === "current_margin_pct" || key === "target_margin_pct") return `${Number(value).toFixed(2)}%`;
  if (key === "price_change_pct") return `+${Number(value).toFixed(1)}%`;
  if (key === "overdue_factor") return `${Number(value).toFixed(2)}×`;
  if (key === "silent_days") return `${value} ngày`;
  if (key === "avg_order_cycle") return `${Number(value).toFixed(0)} ngày`;
  return String(value);
}

const METRIC_LABELS = {
  margin_pct:             (v) => `Biên lợi nhuận: ${Number(v).toFixed(2)}%`,
  overdue_factor:         (v) => `Im lặng: ${Number(v).toFixed(2)}× chu kỳ bình thường`,
  isolation_forest_score: (v) => `Chỉ số bất thường: ${Number(v).toFixed(3)}`,
  z_score:                (v) => `Z-Score: ${Number(v).toFixed(2)}`,
  days_without_order:     (v) => `${v} ngày không đặt hàng`,
};

function getMetricDisplay(metric, value) {
  const fn = METRIC_LABELS[metric];
  return fn ? fn(value) : `${metric}: ${Number(value).toFixed(2)}`;
}

function getTypeConfig(type) {
  return TYPE_CONFIG[type] || { label: type, icon: Activity, color: "#555" };
}

// ── Result Banner ─────────────────────────────────────────────────────────────

function ResultBanner({ success, rejected, actionType }) {
  const cfg = ACTION_CONFIG[actionType] || {};

  if (rejected) {
    return (
      <div className="result-banner result-banner--rejected">
        <XCircle size={18} />
        <div>
          <div className="result-banner-title">Đã từ chối</div>
          <div className="result-banner-desc">Hành động không được thực thi. Phản hồi đã được ghi lại.</div>
        </div>
      </div>
    );
  }
  if (!success) {
    return (
      <div className="result-banner result-banner--error">
        <AlertTriangle size={18} />
        <div>
          <div className="result-banner-title">Thực thi thất bại</div>
          <div className="result-banner-desc">Có lỗi khi gửi lệnh xuống Odoo. Kiểm tra logs để biết thêm.</div>
        </div>
      </div>
    );
  }
  return (
    <div className="result-banner result-banner--success">
      <CheckCircle2 size={18} />
      <div>
        <div className="result-banner-title">
          {cfg.label ? `${cfg.label} — Thành công` : "Thực thi thành công"}
        </div>
        {cfg.odooPath && (
          <div className="result-banner-path">
            <ArrowRight size={12} />
            <span>Xem trong Odoo: <strong>{cfg.odooPath}</strong></span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── ActionApprovalModal ───────────────────────────────────────────────────────

function ActionApprovalModal({ approvalId, onClose, onDone }) {
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    getApproval(approvalId).then((r) => {
      setDetail(r.data);
      setDraft({ ...r.data.params });
    });
  }, [approvalId]);

  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, busy]);

  const handleApprove = async () => {
    setBusy(true);
    try {
      if (detail.editable_fields?.length > 0) await updateApprovalParams(approvalId, draft);
      const res = await approveAction(approvalId);
      setResult({ success: res.data?.success ?? true, rejected: false });
      onDone?.();
    } catch {
      setResult({ success: false, rejected: false });
    }
    setBusy(false);
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await rejectAction(approvalId, "admin", rejectReason);
      setResult({ success: false, rejected: true });
      onDone?.();
    } catch {
      setResult({ success: false, rejected: false });
    }
    setBusy(false);
  };

  const cfg = ACTION_CONFIG[detail?.action_type] || {};
  const AIcon = cfg.icon || Bell;
  const editableFields = detail?.editable_fields || [];
  const readOnlyParams = detail
    ? Object.entries(detail.params || {}).filter(
        ([k]) => !HIDDEN_PARAMS.has(k) && !editableFields.some((f) => f.name === k)
      )
    : [];
  const confPct = detail ? Math.round(Number(detail.confidence) * 100) : 0;

  const coerce = (value, type) => {
    if (type === "int") return parseInt(value, 10) || 0;
    if (type === "float") return parseFloat(value) || 0;
    return value;
  };

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={onClose}>
      <div className="modal-box" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {detail && (
              <span style={{
                width: 40, height: 40, borderRadius: 8, flexShrink: 0,
                background: cfg.riskLevel === "medium" ? "#fff4cc" : "#eef3fc",
                color: cfg.riskLevel === "medium" ? "#b07d00" : "var(--primary)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <AIcon size={20} />
              </span>
            )}
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{cfg.label || "Phê duyệt hành động"}</div>
              {cfg.riskLevel && (
                <Badge type={cfg.riskLevel === "medium" ? "medium" : "low"}>
                  Rủi ro {cfg.riskLevel === "medium" ? "Trung bình" : "Thấp"}
                </Badge>
              )}
            </div>
          </div>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>

        {/* Loading */}
        {!detail && (
          <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-secondary)" }}>
            <Loader2 size={22} className="spin" />
            <p style={{ marginTop: 8, fontSize: 13 }}>Đang tải...</p>
          </div>
        )}

        {/* Result state */}
        {detail && result && (
          <div style={{ paddingTop: 16 }}>
            <ResultBanner success={result.success} rejected={result.rejected} actionType={detail.action_type} />
            <div style={{ textAlign: "center", marginTop: 20 }}>
              <button className="btn btn-secondary" onClick={onClose}>Đóng</button>
            </div>
          </div>
        )}

        {/* Approval form */}
        {detail && !result && (
          <>
            {cfg.desc && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <Info size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />
                  Hành động trong Odoo
                </span>
                <p className="approval-detail-text">{cfg.desc}</p>
              </div>
            )}

            <div className="approval-detail-section">
              <span className="approval-detail-label">
                <BarChart3 size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />
                Độ tin cậy AI
              </span>
              <span className="conf-pill" style={{
                background: confPct >= 70 ? "#d4edda" : confPct >= 50 ? "#fff4d6" : "#fde8ea",
                color: confPct >= 70 ? "#155724" : confPct >= 50 ? "#8a6d0b" : "#c0392b",
              }}>{confPct}%</span>
            </div>

            {(detail.params?.message_body || detail.params?.note) && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <MessageSquare size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />
                  Nội dung sẽ đăng trong Odoo
                </span>
                {detail.params.subject && (
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 6 }}>
                    <strong>Tiêu đề:</strong> {detail.params.subject}
                  </div>
                )}
                <div className="approval-preview-body">{detail.params.message_body || detail.params.note}</div>
              </div>
            )}

            {detail.panel_warning && (
              <div className="approval-warning">
                <AlertTriangle size={13} style={{ verticalAlign: "middle", marginRight: 6 }} />
                {detail.panel_warning}
              </div>
            )}

            {readOnlyParams.length > 0 && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <BarChart3 size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />
                  Thông tin chi tiết
                </span>
                <div className="approval-params-grid">
                  {readOnlyParams.map(([k, v]) => (
                    <div className="approval-param-row" key={k}>
                      <span className="approval-param-key">{PARAM_LABELS[k] || k}</span>
                      <span className="approval-param-val">{formatParamValue(k, v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {editableFields.length > 0 && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <Settings size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />
                  Chỉnh sửa trước khi duyệt
                </span>
                <div className="approval-edit-grid">
                  {editableFields.map((f) => (
                    <label key={f.name} className="approval-field-label">
                      <span>
                        {PARAM_LABELS[f.name] || f.label}
                        {f.ai_suggested && <span className="ai-tag"> ✦ AI</span>}
                        {f.unit && <span style={{ color: "var(--text-secondary)" }}> ({f.unit})</span>}
                      </span>
                      <input
                        type={f.type === "date" ? "date" : "text"}
                        value={draft[f.name] ?? ""}
                        onChange={(e) => setDraft((p) => ({ ...p, [f.name]: coerce(e.target.value, f.type) }))}
                        className="approval-field-input"
                      />
                      {f.note && <span className="approval-field-note">{f.note}</span>}
                    </label>
                  ))}
                </div>
                <p className="ai-note">✦ = giá trị do AI đề xuất</p>
              </div>
            )}

            {rejectMode ? (
              <div className="reject-inline-form">
                <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 6 }}>
                  Lý do từ chối
                </label>
                <textarea
                  className="reject-reason-input"
                  placeholder="Nhập lý do (có thể để trống)..."
                  rows={2}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button className="btn btn-reject" disabled={busy} onClick={handleReject}>
                    {busy ? <Loader2 size={13} className="spin" /> : <XCircle size={13} />}
                    {" "}Xác nhận từ chối
                  </button>
                  <button className="btn btn-secondary" onClick={() => setRejectMode(false)}>Hủy</button>
                </div>
              </div>
            ) : (
              <div className="approval-actions">
                <button className="btn btn-approve" disabled={busy} onClick={handleApprove}>
                  {busy
                    ? <><Loader2 size={14} className="spin" /> Đang thực thi...</>
                    : <><CheckCircle2 size={14} /> Duyệt & Thực thi</>}
                </button>
                <button className="btn btn-reject" disabled={busy} onClick={() => setRejectMode(true)}>
                  <XCircle size={14} /> Từ chối
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Detail Modal ──────────────────────────────────────────────────────────────

function DetailModal({ anomaly, report, approvals, onClose, onApprovalDone }) {
  const cfg = getTypeConfig(anomaly.anomaly_type);
  const Icon = cfg.icon;
  const confPct = Math.round(Number(anomaly.confidence) * 100);
  const [activeApprovalId, setActiveApprovalId] = useState(null);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") {
        if (activeApprovalId) setActiveApprovalId(null);
        else onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, activeApprovalId]);

  const findApproval = (actionType) =>
    approvals.find((a) => a.event_id === anomaly.event_id && a.action_type === actionType);

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-box" onClick={(e) => e.stopPropagation()}>

          {/* Header */}
          <div className="modal-header">
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{
                width: 44, height: 44, borderRadius: "50%",
                background: cfg.color + "18",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <Icon size={22} color={cfg.color} />
              </span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 17 }}>{cfg.label}</div>
                <Badge type={anomaly.severity}>{SEVERITY_LABELS[anomaly.severity] || anomaly.severity}</Badge>
              </div>
            </div>
            <button className="modal-close" onClick={onClose} aria-label="Đóng">
              <X size={20} />
            </button>
          </div>

          {/* Quick stats */}
          <div className="detail-stats-row" style={{ margin: "16px 0" }}>
            {anomaly.product_name && (
              <div className="detail-stat">
                <span className="detail-stat-label">Sản phẩm</span>
                <span className="detail-stat-val">{anomaly.product_name}</span>
              </div>
            )}
            {anomaly.partner_name && (
              <div className="detail-stat">
                <span className="detail-stat-label">Khách hàng</span>
                <span className="detail-stat-val">{anomaly.partner_name}</span>
              </div>
            )}
            <div className="detail-stat">
              <span className="detail-stat-label">Chỉ số phát hiện</span>
              <span className="detail-stat-val" style={{ color: cfg.color, fontWeight: 700 }}>
                {getMetricDisplay(anomaly.metric, anomaly.metric_value)}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">Độ tin cậy AI</span>
              <span className="detail-stat-val">
                <span className="conf-pill" style={{
                  background: confPct >= 70 ? "#d4edda" : confPct >= 50 ? "#fff4d6" : "#fde8ea",
                  color: confPct >= 70 ? "#155724" : confPct >= 50 ? "#8a6d0b" : "#c0392b",
                }}>{confPct}%</span>
              </span>
            </div>
          </div>

          {/* AI report */}
          {report ? (
            <>
              {report.summary && (
                <div className="detail-section">
                  <h3>
                    <BarChart3 size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
                    Phân tích AI
                  </h3>
                  <p style={{ fontSize: 14, lineHeight: 1.6 }}>{report.summary}</p>
                </div>
              )}

              {report.evidence?.length > 0 && (
                <div className="detail-section">
                  <h3>
                    <CheckCircle size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
                    Bằng chứng & Số liệu
                  </h3>
                  <ul className="evidence-list">
                    {report.evidence.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              )}

              {report.root_cause && (
                <div className="detail-section">
                  <h3>
                    <AlertTriangle size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
                    Nguyên nhân
                  </h3>
                  <p style={{ fontSize: 14, lineHeight: 1.6 }}>{report.root_cause}</p>
                </div>
              )}

              {/* Interactive action items */}
              {report.recommended_actions?.length > 0 && (
                <div className="detail-section">
                  <h3>
                    <ChevronRight size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
                    Đề xuất xử lý
                  </h3>
                  <div className="action-items-list">
                    {report.recommended_actions.map((act, i) => {
                      const acfg = ACTION_CONFIG[act.action_type] || {
                        label: act.action_type, icon: Bell,
                        riskLevel: "low", requiresApproval: false, desc: "",
                      };
                      const AIcon = acfg.icon;
                      const approval = findApproval(act.action_type);
                      const isPending = approval?.status === "pending";
                      const isDone = approval?.status === "approved";
                      const isFailed = approval?.status === "failed";
                      const isRejected = approval?.status === "rejected";
                      const isAuto = !acfg.requiresApproval && !approval;

                      return (
                        <div className={`action-item${isPending ? " action-item--pending" : ""}`} key={i}>
                          <div className="action-item-left">
                            <span className="action-item-icon" data-risk={acfg.riskLevel}>
                              <AIcon size={15} />
                            </span>
                            <div className="action-item-info">
                              <div className="action-item-name">
                                {acfg.label}
                                <span className="action-tag-priority" style={{ marginLeft: 6 }}>P{act.priority}</span>
                              </div>
                              {acfg.desc && <div className="action-item-desc">{acfg.desc}</div>}
                            </div>
                          </div>
                          <div className="action-item-right">
                            {isPending && (
                              <button
                                className="btn-inline-approve"
                                onClick={() => setActiveApprovalId(approval.approval_id)}
                              >
                                <CheckCircle2 size={12} /> Phê duyệt
                              </button>
                            )}
                            {isDone && (
                              <span className="action-status-badge action-status-done">
                                <CheckCircle2 size={12} /> Đã thực thi
                              </span>
                            )}
                            {isRejected && (
                              <span className="action-status-badge action-status-rejected">
                                <XCircle size={12} /> Đã từ chối
                              </span>
                            )}
                            {isFailed && (
                              <span className="action-status-badge action-status-failed">
                                <AlertTriangle size={12} /> Lỗi
                              </span>
                            )}
                            {isAuto && (
                              <span className="action-status-badge action-status-auto">
                                <CheckCircle size={12} /> Tự động
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p style={{ color: "var(--text-secondary)", fontSize: 14, paddingTop: 12 }}>
              Chưa có báo cáo phân tích. Chạy pipeline để tạo báo cáo.
            </p>
          )}
        </div>
      </div>

      {/* Second-layer modal for inline action approval */}
      {activeApprovalId && (
        <ActionApprovalModal
          approvalId={activeApprovalId}
          onClose={() => setActiveApprovalId(null)}
          onDone={() => {
            setActiveApprovalId(null);
            onApprovalDone?.();
          }}
        />
      )}
    </>
  );
}

// ── Anomaly Card ──────────────────────────────────────────────────────────────

function AnomalyCard({ anomaly, pendingCount, onClick }) {
  const cfg = getTypeConfig(anomaly.anomaly_type);
  const Icon = cfg.icon;
  const subject = anomaly.product_name || anomaly.partner_name;

  return (
    <div className="anomaly-card" onClick={onClick} style={{ cursor: "pointer" }}>
      <div className="anomaly-card-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            width: 32, height: 32, borderRadius: "50%",
            background: cfg.color + "18",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <Icon size={16} color={cfg.color} />
          </span>
          <strong style={{ fontSize: 14 }}>{cfg.label}</strong>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {pendingCount > 0 && (
            <span className="pending-actions-badge">{pendingCount} chờ duyệt</span>
          )}
          <Badge type={anomaly.severity}>{SEVERITY_LABELS[anomaly.severity] || anomaly.severity}</Badge>
        </div>
      </div>
      <div className="anomaly-card-body">
        {subject && <p style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>{subject}</p>}
        <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          {getMetricDisplay(anomaly.metric, anomaly.metric_value)}
        </p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AnomaliesPage() {
  const [anomalies, setAnomalies] = useState([]);
  const [reports, setReports] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [selected, setSelected] = useState(null);

  const refresh = async () => {
    const [a, r, ap] = await Promise.all([getAnomalies(), getReports(), getApprovals()]);
    setAnomalies(a.data);
    setReports(r.data);
    setApprovals(ap.data);
  };

  useEffect(() => { refresh(); }, []);

  const selectedReport = selected
    ? reports.find((r) => r.event_id === selected.event_id)
    : null;

  // Show pending count badge on each anomaly card
  const pendingByEvent = {};
  approvals.forEach((a) => {
    if (a.status === "pending") {
      pendingByEvent[a.event_id] = (pendingByEvent[a.event_id] || 0) + 1;
    }
  });

  return (
    <>
      <Topbar title="Bất thường phát hiện được" />
      <div className="page-content">
        {anomalies.length === 0 ? (
          <div className="empty-state">
            <Activity size={48} color="var(--text-secondary)" style={{ marginBottom: 12 }} />
            <h3>Chưa có dữ liệu</h3>
            <p>Nhấn "Chạy phân tích" trên Dashboard để quét dữ liệu từ Odoo.</p>
          </div>
        ) : (
          <div className="anomaly-grid">
            {anomalies.map((a) => (
              <AnomalyCard
                key={a.event_id}
                anomaly={a}
                pendingCount={pendingByEvent[a.event_id] || 0}
                onClick={() => setSelected(a)}
              />
            ))}
          </div>
        )}
      </div>

      {selected && (
        <DetailModal
          anomaly={selected}
          report={selectedReport}
          approvals={approvals}
          onClose={() => setSelected(null)}
          onApprovalDone={refresh}
        />
      )}
    </>
  );
}

