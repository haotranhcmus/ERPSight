import { useEffect, useState } from "react";
import {
  TrendingDown,
  UserX,
  Zap,
  Package,
  Activity,
  ShoppingCart,
  Bell,
  Phone,
  Tag,
  ClipboardList,
  DollarSign,
  CheckCircle,
  CheckCircle2,
  AlertTriangle,
  BarChart3,
  X,
  Loader2,
  XCircle,
  MessageSquare,
  ChevronRight,
  Info,
  ArrowRight,
  Settings,
  Ticket,
} from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import {
  getAnomalies,
  getReports,
  getApprovals,
  getApproval,
  approveAction,
  rejectAction,
  updateApprovalParams,
} from "../services/api";

// ── Type Config ───────────────────────────────────────────────────────────────

const TYPE_CONFIG = {
  demand_spike: { label: "Nhu cầu tăng đột biến", icon: Zap, color: "#e67e22" },
  stockout_risk: { label: "Nguy cơ hết hàng", icon: Package, color: "#e74c3c" },
  margin_erosion: {
    label: "Lợi nhuận đang giảm mạnh",
    icon: TrendingDown,
    color: "#c0392b",
  },
  vip_churn: {
    label: "Khách VIP có thể rời bỏ",
    icon: UserX,
    color: "#8e44ad",
  },
  isolation_forest: {
    label: "Nhiều chỉ số bất thường",
    icon: Activity,
    color: "#2980b9",
  },
};

const SEVERITY_LABELS = {
  high: "Khẩn cấp",
  medium: "Cần chú ý",
  low: "Theo dõi",
};

// ── Action Config (desc + riskLevel + requiresApproval + odooPath) ────────────

const ACTION_CONFIG = {
  send_internal_alert: {
    label: "Gửi cảnh báo nội bộ",
    icon: Bell,
    desc: "Đăng thông báo cảnh báo vào chatter sản phẩm trong Odoo.",
    riskLevel: "low",
    requiresApproval: false,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  },
  send_margin_alert: {
    label: "Gửi cảnh báo lợi nhuận",
    icon: TrendingDown,
    desc: "Đăng bảng phân tích margin chi tiết vào chatter sản phẩm trong Odoo.",
    riskLevel: "low",
    requiresApproval: false,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  },
  send_churn_risk_alert: {
    label: "Gửi cảnh báo rủi ro churn",
    icon: UserX,
    desc: "Đăng thông tin phân tích churn vào chatter hồ sơ khách hàng trong Odoo.",
    riskLevel: "low",
    requiresApproval: false,
    odooPath: "Liên hệ → [khách hàng] → tab Chatter",
  },
  create_activity_task: {
    label: "Tạo nhắc nhở nội bộ",
    icon: ClipboardList,
    desc: "Tạo hoạt động nhắc nhở (mail.activity) gắn vào record trong Odoo.",
    riskLevel: "low",
    requiresApproval: false,
    odooPath: "Thảo luận → Hoạt động của tôi",
  },
  create_reengagement_activity: {
    label: "Tạo lịch gọi điện chăm sóc",
    icon: Phone,
    desc: "Tạo hoạt động 'Phone Call' trên hồ sơ khách hàng để nhắc nhở tái chăm sóc.",
    riskLevel: "low",
    requiresApproval: false,
    odooPath: "Liên hệ → [khách hàng] → tab Hoạt động",
  },
  flag_product_for_price_review: {
    label: "Gắn cờ xem xét lại giá",
    icon: Tag,
    desc: "Ghi chú nội bộ trên sản phẩm, đánh dấu cần điều chỉnh giá bán.",
    riskLevel: "low",
    requiresApproval: false,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  },
  create_purchase_order: {
    label: "Tạo đơn đặt hàng nhà cung cấp",
    icon: ShoppingCart,
    desc: "Tạo đơn mua hàng (draft PO) trong Odoo từ nhà cung cấp. Cần xác nhận thêm trước khi gửi đi.",
    riskLevel: "medium",
    requiresApproval: true,
    odooPath: "Mua hàng → Đơn mua → lọc trạng thái Nháp",
  },
  update_sale_price: {
    label: "Cập nhật giá bán",
    icon: DollarSign,
    desc: "Thay đổi trực tiếp giá bán của sản phẩm trong Odoo và ghi audit log.",
    riskLevel: "medium",
    requiresApproval: true,
    odooPath: "Kho → Sản phẩm → [sản phẩm] → Giá bán",
  },
  create_helpdesk_ticket: {
    label: "Tạo ticket theo dõi churn",
    icon: Ticket,
    desc: "Tạo helpdesk ticket nội bộ để team Sales theo dõi và xử lý rủi ro mất khách VIP.",
    riskLevel: "low",
    requiresApproval: true,
    odooPath: "Helpdesk → Tickets → [ticket vừa tạo]",
  },
};

// ── Param display helpers ─────────────────────────────────────────────────────

const PARAM_LABELS = {
  product_sku: "Mã sản phẩm",
  partner_name: "Khách hàng",
  supplier_name: "Nhà cung cấp",
  old_purchase_price: "Giá nhập cũ",
  new_purchase_price: "Giá nhập mới",
  price_change_pct: "Giá nhập tăng",
  current_sale_price: "Giá bán hiện tại",
  current_margin_pct: "Biên lợi nhuận",
  projected_daily_loss: "Tổn thất ước tính/ngày",
  last_order_date: "Đơn hàng cuối",
  silent_days: "Số ngày im lặng",
  avg_order_cycle: "Chu kỳ đặt hàng TB",
  overdue_factor: "Mức độ quá hạn",
  qty: "Số lượng đặt",
  price_unit: "Đơn giá mua",
  date_planned: "Ngày nhận hàng dự kiến",
  new_sale_price: "Giá bán mới",
  suggested_new_sale_price: "Giá đề xuất",
  target_margin_pct: "Biên lợi nhuận mục tiêu",
  date_deadline: "Thời hạn",
  last_price_unit: "Giá PO gần nhất",
  suggested_qty: "Số lượng đề xuất",
  assigned_to_login: "Phân công cho",
};

const HIDDEN_PARAMS = new Set([
  "res_model",
  "res_id_lookup",
  "notify_user_logins",
  "activity_type_name",
  "attachment_context",
  "has_recent_complaint",
  "suggested_offer",
  "_odoo_product_id",
  "_odoo_partner_id",
  "message_body",
  "note",
  "subject",
  "reason",
  "description",
  "ticket_name",
]);

const CURRENCY_PARAMS = new Set([
  "old_purchase_price",
  "new_purchase_price",
  "current_sale_price",
  "projected_daily_loss",
  "price_unit",
  "new_sale_price",
  "suggested_new_sale_price",
  "last_price_unit",
]);

function getActionSummary(actionType, params) {
  if (!params) return null;
  const fmt = (v) => Number(v).toLocaleString("vi-VN") + "đ";
  if (actionType === "update_sale_price") {
    const old = params.current_sale_price;
    const neo = params.new_sale_price;
    if (old && neo) return `Giá bán: ${fmt(old)} → ${fmt(neo)}`;
  }
  if (actionType === "create_draft_po") {
    const qty = params.qty || params.suggested_qty;
    const price = params.price_unit;
    const sku = params.product_sku || "";
    if (qty && price)
      return `Đặt ${qty} sản phẩm${sku ? " (" + sku + ")" : ""} @ ${fmt(price)}/đơn vị`;
    if (qty) return `Đặt ${qty} sản phẩm${sku ? " (" + sku + ")" : ""}`;
  }
  if (actionType === "create_helpdesk_ticket")
    return "Ticket hỗ trợ đã được tạo trong Odoo";
  if (actionType === "send_internal_alert")
    return "Cảnh báo nội bộ đã được gửi";
  if (actionType === "create_reengagement_activity") {
    const partner = params.partner_name || "";
    return partner
      ? `Hoạt động tái kết nối — ${partner}`
      : "Hoạt động tái kết nối đã được tạo";
  }
  return null;
}

function formatParamValue(key, value) {
  if (CURRENCY_PARAMS.has(key))
    return `${Number(value).toLocaleString("vi-VN")}đ`;
  if (key === "current_margin_pct" || key === "target_margin_pct")
    return `${Number(value).toFixed(2)}%`;
  if (key === "price_change_pct") return `+${Number(value).toFixed(1)}%`;
  if (key === "overdue_factor") return `${Number(value).toFixed(2)}×`;
  if (key === "silent_days") return `${value} ngày`;
  if (key === "avg_order_cycle") return `${Number(value).toFixed(0)} ngày`;
  return String(value);
}

const METRIC_LABELS = {
  margin_pct: (v) => `Biên lợi nhuận: ${Number(v).toFixed(2)}%`,
  overdue_factor: (v) => `Im lặng: ${Number(v).toFixed(2)}× chu kỳ bình thường`,
  isolation_forest_score: (v) => `Chỉ số bất thường: ${Number(v).toFixed(3)}`,
  z_score: (v) => `Z-Score: ${Number(v).toFixed(2)}`,
  days_without_order: (v) => `${v} ngày không đặt hàng`,
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
          <div className="result-banner-desc">
            Hành động không được thực thi. Phản hồi đã được ghi lại.
          </div>
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
          <div className="result-banner-desc">
            Có lỗi khi gửi lệnh xuống Odoo. Kiểm tra logs để biết thêm.
          </div>
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
            <span>
              Xem trong Odoo: <strong>{cfg.odooPath}</strong>
            </span>
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
    const handler = (e) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, busy]);

  const handleApprove = async () => {
    setBusy(true);
    try {
      if (!detail.advisory_only && detail.editable_fields?.length > 0)
        await updateApprovalParams(approvalId, draft);
      const res = await approveAction(approvalId);
      setResult({
        success: res.data?.success ?? true,
        rejected: false,
        advisory: !!detail.advisory_only,
      });
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

  const isAdvisory = detail?.advisory_only;
  const cfg = ACTION_CONFIG[detail?.action_type] || {};
  const AIcon = cfg.icon || Bell;
  const editableFields = (!isAdvisory && detail?.editable_fields) || [];
  const readOnlyParams =
    !isAdvisory && detail
      ? Object.entries(detail.params || {}).filter(
          ([k]) =>
            !HIDDEN_PARAMS.has(k) && !editableFields.some((f) => f.name === k),
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
      <div
        className="modal-box"
        style={{ maxWidth: 560 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {detail && (
              <span
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 8,
                  flexShrink: 0,
                  background: isAdvisory
                    ? "#eef3fc"
                    : cfg.riskLevel === "medium"
                      ? "#fff4cc"
                      : "#eef3fc",
                  color: isAdvisory
                    ? "var(--primary)"
                    : cfg.riskLevel === "medium"
                      ? "#b07d00"
                      : "var(--primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <AIcon size={20} />
              </span>
            )}
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>
                {isAdvisory
                  ? "Đề xuất hướng xử lý"
                  : cfg.label || "Phê duyệt hành động"}
              </div>
              {isAdvisory ? (
                <Badge type="info">Độ tin cậy thấp — chỉ tư vấn</Badge>
              ) : (
                cfg.riskLevel && (
                  <Badge type={cfg.riskLevel === "medium" ? "medium" : "low"}>
                    Rủi ro {cfg.riskLevel === "medium" ? "Trung bình" : "Thấp"}
                  </Badge>
                )
              )}
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Loading */}
        {!detail && (
          <div
            style={{
              textAlign: "center",
              padding: "32px 0",
              color: "var(--text-secondary)",
            }}
          >
            <Loader2 size={22} className="spin" />
            <p style={{ marginTop: 8, fontSize: 13 }}>Đang tải...</p>
          </div>
        )}

        {/* Result state */}
        {detail && result && (
          <div style={{ paddingTop: 16 }}>
            {result.advisory ? (
              <div className="result-banner result-banner--advisory">
                <CheckCircle2 size={18} />
                <div>
                  <div className="result-banner-title">Đã ghi nhận đề xuất</div>
                  <div className="result-banner-desc">
                    Bất thường này đã được đánh dấu là đã xem xét.
                  </div>
                </div>
              </div>
            ) : (
              <ResultBanner
                success={result.success}
                rejected={result.rejected}
                actionType={detail.action_type}
              />
            )}
            <div style={{ textAlign: "center", marginTop: 20 }}>
              <button className="btn btn-secondary" onClick={onClose}>
                Đóng
              </button>
            </div>
          </div>
        )}

        {/* Advisory-only form */}
        {detail && !result && isAdvisory && (
          <>
            <div className="approval-detail-section">
              <span className="approval-detail-label">
                <BarChart3
                  size={12}
                  style={{ verticalAlign: "middle", marginRight: 4 }}
                />
                Độ tin cậy AI
              </span>
              <span
                className="conf-pill"
                style={{
                  background: "#fde8ea",
                  color: "#c0392b",
                }}
              >
                {confPct}%
              </span>
            </div>

            <div className="approval-detail-section">
              <span className="approval-detail-label">
                <Info
                  size={12}
                  style={{ verticalAlign: "middle", marginRight: 4 }}
                />
                Đề xuất của AI
              </span>
              <div className="advisory-summary-box">
                {detail.summary ||
                  detail.reason ||
                  "AI đề xuất xem xét thủ công tình huống này."}
              </div>
            </div>

            <div className="advisory-note">
              <AlertTriangle
                size={13}
                style={{ marginRight: 6, flexShrink: 0 }}
              />
              <span>
                Độ tin cậy thấp — AI không thực thi hành động tự động. Vui lòng
                xem xét và quyết định thủ công.
              </span>
            </div>

            {rejectMode ? (
              <div className="reject-inline-form">
                <label
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    display: "block",
                    marginBottom: 6,
                  }}
                >
                  Lý do bỏ qua (tuỳ chọn)
                </label>
                <textarea
                  className="reject-reason-input"
                  placeholder="Nhập lý do..."
                  rows={2}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button
                    className="btn btn-reject"
                    disabled={busy}
                    onClick={handleReject}
                  >
                    {busy ? (
                      <Loader2 size={13} className="spin" />
                    ) : (
                      <XCircle size={13} />
                    )}{" "}
                    Xác nhận bỏ qua
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setRejectMode(false)}
                  >
                    Hủy
                  </button>
                </div>
              </div>
            ) : (
              <div className="approval-actions">
                <button
                  className="btn btn-approve"
                  disabled={busy}
                  onClick={handleApprove}
                >
                  {busy ? (
                    <>
                      <Loader2 size={14} className="spin" /> Đang ghi nhận...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={14} /> Xác nhận đã xem xét
                    </>
                  )}
                </button>
                <button
                  className="btn btn-reject"
                  disabled={busy}
                  onClick={() => setRejectMode(true)}
                >
                  <XCircle size={14} /> Bỏ qua
                </button>
              </div>
            )}
          </>
        )}

        {/* Normal approval form */}
        {detail && !result && !isAdvisory && (
          <>
            {cfg.desc && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <Info
                    size={12}
                    style={{ verticalAlign: "middle", marginRight: 4 }}
                  />
                  Hành động trong Odoo
                </span>
                <p className="approval-detail-text">{cfg.desc}</p>
              </div>
            )}

            <div className="approval-detail-section">
              <span className="approval-detail-label">
                <BarChart3
                  size={12}
                  style={{ verticalAlign: "middle", marginRight: 4 }}
                />
                Độ tin cậy AI
              </span>
              <span
                className="conf-pill"
                style={{
                  background:
                    confPct >= 70
                      ? "#d4edda"
                      : confPct >= 50
                        ? "#fff4d6"
                        : "#fde8ea",
                  color:
                    confPct >= 70
                      ? "#155724"
                      : confPct >= 50
                        ? "#8a6d0b"
                        : "#c0392b",
                }}
              >
                {confPct}%
              </span>
            </div>

            {(detail.params?.message_body || detail.params?.note) && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <MessageSquare
                    size={12}
                    style={{ verticalAlign: "middle", marginRight: 4 }}
                  />
                  Nội dung sẽ đăng trong Odoo
                </span>
                {detail.params.subject && (
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-secondary)",
                      marginBottom: 6,
                    }}
                  >
                    <strong>Tiêu đề:</strong> {detail.params.subject}
                  </div>
                )}
                <div className="approval-preview-body">
                  {detail.params.message_body || detail.params.note}
                </div>
              </div>
            )}

            {detail.panel_warning && (
              <div className="approval-warning">
                <AlertTriangle
                  size={13}
                  style={{ verticalAlign: "middle", marginRight: 6 }}
                />
                {detail.panel_warning}
              </div>
            )}

            {readOnlyParams.length > 0 && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <BarChart3
                    size={12}
                    style={{ verticalAlign: "middle", marginRight: 4 }}
                  />
                  Thông tin chi tiết
                </span>
                <div className="approval-params-grid">
                  {readOnlyParams.map(([k, v]) => (
                    <div className="approval-param-row" key={k}>
                      <span className="approval-param-key">
                        {PARAM_LABELS[k] || k}
                      </span>
                      <span className="approval-param-val">
                        {formatParamValue(k, v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {editableFields.length > 0 && (
              <div className="approval-detail-section">
                <span className="approval-detail-label">
                  <Settings
                    size={12}
                    style={{ verticalAlign: "middle", marginRight: 4 }}
                  />
                  Chỉnh sửa trước khi duyệt
                </span>
                <div className="approval-edit-grid">
                  {editableFields.map((f) => (
                    <label key={f.name} className="approval-field-label">
                      <span>
                        {PARAM_LABELS[f.name] || f.label}
                        {f.ai_suggested && (
                          <span className="ai-tag"> ✦ AI</span>
                        )}
                        {f.unit && (
                          <span style={{ color: "var(--text-secondary)" }}>
                            {" "}
                            ({f.unit})
                          </span>
                        )}
                      </span>
                      <input
                        type={f.type === "date" ? "date" : "text"}
                        value={draft[f.name] ?? ""}
                        onChange={(e) =>
                          setDraft((p) => ({
                            ...p,
                            [f.name]: coerce(e.target.value, f.type),
                          }))
                        }
                        className="approval-field-input"
                      />
                      {f.note && (
                        <span className="approval-field-note">{f.note}</span>
                      )}
                    </label>
                  ))}
                </div>
                <p className="ai-note">✦ = giá trị do AI đề xuất</p>
              </div>
            )}

            {rejectMode ? (
              <div className="reject-inline-form">
                <label
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    display: "block",
                    marginBottom: 6,
                  }}
                >
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
                  <button
                    className="btn btn-reject"
                    disabled={busy}
                    onClick={handleReject}
                  >
                    {busy ? (
                      <Loader2 size={13} className="spin" />
                    ) : (
                      <XCircle size={13} />
                    )}{" "}
                    Xác nhận từ chối
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setRejectMode(false)}
                  >
                    Hủy
                  </button>
                </div>
              </div>
            ) : (
              <div className="approval-actions">
                <button
                  className="btn btn-approve"
                  disabled={busy}
                  onClick={handleApprove}
                >
                  {busy ? (
                    <>
                      <Loader2 size={14} className="spin" /> Đang thực thi...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={14} /> Duyệt & Thực thi
                    </>
                  )}
                </button>
                <button
                  className="btn btn-reject"
                  disabled={busy}
                  onClick={() => setRejectMode(true)}
                >
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

// ── Resolution Banner ─────────────────────────────────────────────────────────

const RESOLUTION_CONFIG = {
  auto_executed: {
    label: "AI tự động thực thi",
    icon: CheckCircle,
    cls: "resolution-auto",
  },
  user_approved: {
    label: "Người dùng duyệt & thực thi",
    icon: CheckCircle2,
    cls: "resolution-approved",
  },
  user_rejected: {
    label: "Người dùng từ chối đề xuất",
    icon: XCircle,
    cls: "resolution-rejected",
  },
  advisory_acknowledged: {
    label: "Đã xem xét đề xuất tư vấn",
    icon: Info,
    cls: "resolution-advisory",
  },
};

function ResolutionBanner({ resolutionType, resolvedAt }) {
  const cfg = RESOLUTION_CONFIG[resolutionType] || {
    label: "Đã xử lý",
    icon: CheckCircle2,
    cls: "resolution-approved",
  };
  const Icon = cfg.icon;
  return (
    <div className={`resolution-banner ${cfg.cls}`}>
      <Icon size={16} style={{ flexShrink: 0 }} />
      <div>
        <div style={{ fontWeight: 700, fontSize: 13 }}>{cfg.label}</div>
        {resolvedAt && (
          <div style={{ fontSize: 11, opacity: 0.8, marginTop: 2 }}>
            {resolvedAt.slice(0, 16).replace("T", " ")}
          </div>
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
    approvals.find(
      (a) => a.event_id === anomaly.event_id && a.action_type === actionType,
    );

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-box" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="modal-header">
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: cfg.color + "18",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Icon size={22} color={cfg.color} />
              </span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 17 }}>{cfg.label}</div>
                <Badge type={anomaly.severity}>
                  {SEVERITY_LABELS[anomaly.severity] || anomaly.severity}
                </Badge>
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
              <span
                className="detail-stat-val"
                style={{ color: cfg.color, fontWeight: 700 }}
              >
                {getMetricDisplay(anomaly.metric, anomaly.metric_value)}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">Độ tin cậy AI</span>
              <span className="detail-stat-val">
                <span
                  className="conf-pill"
                  style={{
                    background:
                      confPct >= 70
                        ? "#d4edda"
                        : confPct >= 50
                          ? "#fff4d6"
                          : "#fde8ea",
                    color:
                      confPct >= 70
                        ? "#155724"
                        : confPct >= 50
                          ? "#8a6d0b"
                          : "#c0392b",
                  }}
                >
                  {confPct}%
                </span>
              </span>
            </div>
          </div>

          {/* Resolution banner (shown when anomaly is resolved) */}
          {anomaly.status === "resolved" && (
            <ResolutionBanner
              resolutionType={anomaly.resolution_type}
              resolvedAt={anomaly.resolved_at}
            />
          )}

          {/* AI report */}
          {report ? (
            <>
              {report.summary && (
                <div className="detail-section">
                  <h3>
                    <BarChart3
                      size={14}
                      style={{ verticalAlign: "middle", marginRight: 6 }}
                    />
                    Phân tích AI
                  </h3>
                  <p style={{ fontSize: 14, lineHeight: 1.6 }}>
                    {report.summary}
                  </p>
                </div>
              )}

              {report.evidence?.length > 0 && (
                <div className="detail-section">
                  <h3>
                    <CheckCircle
                      size={14}
                      style={{ verticalAlign: "middle", marginRight: 6 }}
                    />
                    Bằng chứng & Số liệu
                  </h3>
                  <ul className="evidence-list">
                    {report.evidence.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}

              {report.root_cause && (
                <div className="detail-section">
                  <h3>
                    <AlertTriangle
                      size={14}
                      style={{ verticalAlign: "middle", marginRight: 6 }}
                    />
                    Nguyên nhân
                  </h3>
                  <p style={{ fontSize: 14, lineHeight: 1.6 }}>
                    {report.root_cause}
                  </p>
                </div>
              )}

              {/* Single primary action (highest priority) */}
              {report.recommended_actions?.length > 0 &&
                (() => {
                  const act = [...report.recommended_actions].sort(
                    (a, b) => a.priority - b.priority,
                  )[0];
                  const acfg = ACTION_CONFIG[act.action_type] || {
                    label: act.action_type,
                    icon: Bell,
                    riskLevel: "low",
                    requiresApproval: false,
                    desc: "",
                  };
                  const AIcon = acfg.icon;
                  const approval = findApproval(act.action_type);
                  const isPending = approval?.status === "pending";
                  const isDone = approval?.status === "approved";
                  const isFailed = approval?.status === "failed";
                  const isRejected = approval?.status === "rejected";
                  const isAdvisoryPending =
                    isPending && approval?.advisory_only;
                  const isAuto =
                    anomaly.status === "resolved" &&
                    anomaly.resolution_type === "auto_executed";

                  return (
                    <div className="detail-section">
                      <h3>
                        <ChevronRight
                          size={14}
                          style={{ verticalAlign: "middle", marginRight: 6 }}
                        />
                        {anomaly.status === "resolved"
                          ? "Hành động đã thực hiện"
                          : "Đề xuất xử lý"}
                      </h3>
                      <div
                        className={`action-item${isPending ? " action-item--pending" : ""}`}
                      >
                        <div className="action-item-left">
                          <span
                            className="action-item-icon"
                            data-risk={acfg.riskLevel}
                          >
                            <AIcon size={15} />
                          </span>
                          <div className="action-item-info">
                            <div className="action-item-name">{acfg.label}</div>
                            {acfg.desc && (
                              <div className="action-item-desc">
                                {acfg.desc}
                              </div>
                            )}
                            {isAdvisoryPending && (
                              <div className="action-item-advisory-hint">
                                Độ tin cậy thấp — AI chỉ đề xuất hướng xử lý,
                                không thực thi Odoo
                              </div>
                            )}
                            {(isDone || isAuto) &&
                              (() => {
                                const summary = getActionSummary(
                                  act.action_type,
                                  approval?.params,
                                );
                                return summary ? (
                                  <div className="action-item-result-summary">
                                    {summary}
                                  </div>
                                ) : null;
                              })()}
                            {isRejected && approval?.reject_reason && (
                              <div className="action-item-reject-reason">
                                Lý do từ chối: {approval.reject_reason}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="action-item-right">
                          {isPending && (
                            <button
                              className="btn-inline-approve"
                              onClick={() =>
                                setActiveApprovalId(approval.approval_id)
                              }
                            >
                              {isAdvisoryPending ? (
                                <>
                                  <Info size={12} /> Xem xét
                                </>
                              ) : (
                                <>
                                  <CheckCircle2 size={12} /> Xem xét
                                </>
                              )}
                            </button>
                          )}
                          {isDone && !isAdvisoryPending && (
                            <span className="action-status-badge action-status-done">
                              <CheckCircle2 size={12} /> Đã thực thi
                            </span>
                          )}
                          {isDone && approval?.advisory_only && (
                            <span className="action-status-badge action-status-advisory">
                              <Info size={12} /> Đã xem xét
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
                              <CheckCircle size={12} /> AI tự động
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })()}
            </>
          ) : (
            <p
              style={{
                color: "var(--text-secondary)",
                fontSize: 14,
                paddingTop: 12,
              }}
            >
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
  const status = anomaly.status || "active";

  return (
    <div
      className="anomaly-card"
      onClick={onClick}
      style={{ cursor: "pointer" }}
    >
      <div className="anomaly-card-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: cfg.color + "18",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Icon size={16} color={cfg.color} />
          </span>
          <strong style={{ fontSize: 14 }}>{cfg.label}</strong>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {pendingCount > 0 && (
            <span className="pending-actions-badge">
              {pendingCount} chờ duyệt
            </span>
          )}
          <AnomalyStatusBadge
            status={status}
            resolutionType={anomaly.resolution_type}
          />
          <Badge type={anomaly.severity}>
            {SEVERITY_LABELS[anomaly.severity] || anomaly.severity}
          </Badge>
        </div>
      </div>
      <div className="anomaly-card-body">
        {subject && (
          <p style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>
            {subject}
          </p>
        )}
        <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          {getMetricDisplay(anomaly.metric, anomaly.metric_value)}
        </p>
        {status === "resolved" && anomaly.resolved_at && (
          <p
            style={{
              fontSize: 11,
              color: "var(--text-secondary)",
              marginTop: 4,
            }}
          >
            {anomaly.resolved_at.slice(0, 16).replace("T", " ")}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Status Badge for anomaly cards ────────────────────────────────────────────

function AnomalyStatusBadge({ status, resolutionType }) {
  if (!status || status === "active") return null;
  if (status === "resolved") {
    if (resolutionType === "user_rejected") {
      return (
        <span className="anomaly-status-badge anomaly-status-dismissed">
          <XCircle
            size={11}
            style={{ verticalAlign: "middle", marginRight: 3 }}
          />
          Đã từ chối
        </span>
      );
    }
    if (resolutionType === "auto_executed") {
      return (
        <span className="anomaly-status-badge anomaly-status-auto">
          <CheckCircle
            size={11}
            style={{ verticalAlign: "middle", marginRight: 3 }}
          />
          AI tự động
        </span>
      );
    }
    if (resolutionType === "advisory_acknowledged") {
      return (
        <span className="anomaly-status-badge anomaly-status-advisory">
          <Info size={11} style={{ verticalAlign: "middle", marginRight: 3 }} />
          Đã xem xét
        </span>
      );
    }
    return (
      <span className="anomaly-status-badge anomaly-status-resolved">
        <CheckCircle2
          size={11}
          style={{ verticalAlign: "middle", marginRight: 3 }}
        />
        Đã xử lý
      </span>
    );
  }
  return null;
}

// ── Page ──────────────────────────────────────────────────────────────────────

const FILTER_TABS = [
  { key: "active", label: "Đang theo dõi" },
  { key: "resolved", label: "Đã xử lý" },
];

export default function AnomaliesPage() {
  const [anomalies, setAnomalies] = useState([]);
  const [reports, setReports] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("active");
  const refresh = async () => {
    const [a, r, ap] = await Promise.all([
      getAnomalies(),
      getReports(),
      getApprovals(),
    ]);
    setAnomalies(a.data);
    setReports(r.data);
    setApprovals(ap.data);
  };

  useEffect(() => {
    refresh();
  }, []);

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

  const filtered = anomalies.filter((a) => {
    // Ẩn Isolation Forest — quá nhiều, không có action cụ thể cho người dùng
    if (a.anomaly_type === "isolation_forest") return false;
    const st = a.status || "active"; // backwards-compat: no status field → treat as active
    return st === filter;
  });

  const countsByStatus = { active: 0, resolved: 0 };
  anomalies.forEach((a) => {
    if (a.anomaly_type === "isolation_forest") return;
    const st = a.status || "active";
    if (st in countsByStatus) countsByStatus[st]++;
  });

  const EMPTY_MESSAGES = {
    active:
      "Không có bất thường đang hoạt động. Chạy phân tích để quét dữ liệu mới.",
    resolved: "Chưa có bất thường nào được xử lý.",
  };

  return (
    <>
      <Topbar title="Bất thường phát hiện được" />
      <div className="page-content">
        {/* Filter tabs */}
        <div
          className="anomaly-filter-tabs"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              className={`anomaly-filter-tab${filter === tab.key ? " active" : ""}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
              {countsByStatus[tab.key] > 0 && (
                <span className="tab-count">{countsByStatus[tab.key]}</span>
              )}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">
            <Activity
              size={48}
              color="var(--text-secondary)"
              style={{ marginBottom: 12 }}
            />
            <h3>Không có dữ liệu</h3>
            <p>{EMPTY_MESSAGES[filter]}</p>
          </div>
        ) : (
          <div className="anomaly-grid">
            {filtered.map((a) => (
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
