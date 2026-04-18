import { useEffect, useState } from "react";
import {
  Bell,
  TrendingDown,
  UserX,
  ClipboardList,
  Phone,
  Tag,
  ShoppingCart,
  DollarSign,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Loader2,
  BarChart3,
  Info,
  MessageSquare,
  Settings,
  AlertTriangle,
  ArrowRight,
  Lightbulb,
} from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import {
  getApprovals,
  getApproval,
  approveAction,
  rejectAction,
  updateApprovalParams,
} from "../services/api";

// ── Mappings ──────────────────────────────────────────────────────────────────

const ACTION_CONFIG = {
  send_internal_alert: {
    label: "Gửi cảnh báo nội bộ",
    icon: Bell,
    desc: "Đăng thông báo vào chatter của record trong Odoo",
  },
  send_margin_alert: {
    label: "Gửi cảnh báo lợi nhuận",
    icon: TrendingDown,
    desc: "Đăng bảng phân tích margin vào chatter sản phẩm",
  },
  send_churn_risk_alert: {
    label: "Cảnh báo khách hàng có thể rời",
    icon: UserX,
    desc: "Đăng thông tin churn vào chatter đối tác trong Odoo",
  },
  create_activity_task: {
    label: "Tạo nhắc nhở nội bộ",
    icon: ClipboardList,
    desc: "Tạo hoạt động nhắc nhở (mail.activity) trong Odoo",
  },
  create_reengagement_activity: {
    label: "Tạo lịch gọi điện",
    icon: Phone,
    desc: "Tạo hoạt động 'Phone Call' trên profile khách hàng",
  },
  flag_product_for_price_review: {
    label: "Đánh dấu xem xét lại giá",
    icon: Tag,
    desc: "Ghi chú nội bộ trên sản phẩm trong Odoo",
  },
  create_purchase_order: {
    label: "Tạo đơn đặt hàng nhà cung cấp",
    icon: ShoppingCart,
    desc: "Tạo đơn mua hàng (draft) trong Odoo để nhà kho xác nhận",
  },
  update_sale_price: {
    label: "Cập nhật giá bán",
    icon: DollarSign,
    desc: "Thay đổi giá bán trực tiếp trong Odoo và ghi audit log",
  },
};

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
  suggested_new_sale_price: "Giá bán đề xuất",
  target_margin_pct: "Biên lợi nhuận mục tiêu",
  subject: "Tiêu đề",
  summary: "Nội dung hoạt động",
  date_deadline: "Thời hạn",
  assigned_to_login: "Phân công cho",
};

// Params that are purely technical (never shown to user)
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
  // shown via chatter preview block instead:
  "message_body",
  "note",
  "subject",
]);

const CURRENCY_PARAMS = new Set([
  "old_purchase_price",
  "new_purchase_price",
  "current_sale_price",
  "projected_daily_loss",
  "price_unit",
  "new_sale_price",
  "suggested_new_sale_price",
]);

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

// ── Detail Body (read-only params + optional edit form) ───────────────────────

function ApprovalDetail({ item, busy, onApprove, onReject }) {
  const [draft, setDraft] = useState({ ...item.params });
  const editableFields = item.editable_fields || [];

  const readOnlyParams = Object.entries(item.params || {}).filter(
    ([k]) => !HIDDEN_PARAMS.has(k) && !editableFields.some((f) => f.name === k),
  );

  const coerce = (value, type) => {
    if (type === "int") return parseInt(value, 10) || 0;
    if (type === "float") return parseFloat(value) || 0;
    return value;
  };

  const handleApprove = () => {
    if (editableFields.length > 0) onApprove(draft);
    else onApprove(null);
  };

  return (
    <div className="approval-detail">
      {/* Reason */}
      {item.reason && (
        <div className="approval-detail-section">
          <span className="approval-detail-label">
            <Lightbulb
              size={12}
              style={{ verticalAlign: "middle", marginRight: 4 }}
            />
            Lý do AI đề xuất
          </span>
          <p className="approval-detail-text">{item.reason}</p>
        </div>
      )}

      {/* What will happen */}
      {ACTION_CONFIG[item.action_type] && (
        <div className="approval-detail-section">
          <span className="approval-detail-label">
            <Info
              size={12}
              style={{ verticalAlign: "middle", marginRight: 4 }}
            />
            Hành động trong Odoo
          </span>
          <p className="approval-detail-text">
            {ACTION_CONFIG[item.action_type].desc}
          </p>
        </div>
      )}

      {/* Chatter / Task content preview */}
      {(item.params?.message_body || item.params?.note) && (
        <div className="approval-detail-section">
          <span className="approval-detail-label">
            <MessageSquare
              size={12}
              style={{ verticalAlign: "middle", marginRight: 4 }}
            />
            Nội dung sẽ đăng trong Odoo
          </span>
          {item.params.subject && (
            <div className="approval-preview-subject">
              <span
                style={{
                  fontWeight: 600,
                  color: "var(--text-secondary)",
                  fontSize: 12,
                }}
              >
                Tiêu đề:
              </span>{" "}
              {item.params.subject}
            </div>
          )}
          <div className="approval-preview-body">
            {item.params.message_body || item.params.note}
          </div>
        </div>
      )}

      {/* Warning */}
      {item.panel_warning && (
        <div className="approval-warning">⚠ {item.panel_warning}</div>
      )}

      {/* Read-only params */}
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

      {/* Editable form */}
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
                  {f.ai_suggested && <span className="ai-tag"> ✦ AI</span>}
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

      {/* Action buttons */}
      <div className="approval-actions">
        <button
          className="btn btn-approve"
          disabled={busy}
          onClick={handleApprove}
        >
          {busy ? (
            <>
              <Loader2 size={15} className="spin" /> Đang xử lý...
            </>
          ) : (
            <>
              <CheckCircle2 size={15} /> Duyệt
              {editableFields.length > 0 ? " & Thực thi" : ""}
            </>
          )}
        </button>
        <button className="btn btn-reject" disabled={busy} onClick={onReject}>
          <XCircle size={15} /> Từ chối
        </button>
      </div>
    </div>
  );
}

// ── Result Banner ─────────────────────────────────────────────────────────────

const ODOO_PATHS = {
  send_margin_alert: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  send_internal_alert: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  send_churn_risk_alert: "Liên hệ → [khách hàng] → tab Chatter",
  create_activity_task: "Thảo luận → Hoạt động của tôi",
  create_reengagement_activity: "Liên hệ → [khách hàng] → tab Hoạt động",
  flag_product_for_price_review: "Kho → Sản phẩm → [sản phẩm] → tab Chatter",
  create_purchase_order: "Mua hàng → Đơn mua → lọc trạng thái Nháp",
  update_sale_price: "Kho → Sản phẩm → [sản phẩm] → Giá bán",
};

function ResultBanner({ success, rejected, actionType }) {
  const cfg = ACTION_CONFIG[actionType] || {};
  const odooPath = ODOO_PATHS[actionType];

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
            Có lỗi khi gửi lệnh xuống Odoo. Kiểm tra action logs.
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
        {odooPath && (
          <div className="result-banner-path">
            <ArrowRight size={12} />
            <span>
              Xem trong Odoo: <strong>{odooPath}</strong>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Approval Card ─────────────────────────────────────────────────────────────

function ApprovalCard({ item, busy, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(false);
  const [enriched, setEnriched] = useState(null);
  const [result, setResult] = useState(null);
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const cfg = ACTION_CONFIG[item.action_type] || {
    label: item.action_type,
    icon: Bell,
  };
  const Icon = cfg.icon;
  const subject =
    item.params?.product_sku ||
    item.params?.partner_name ||
    item.params?.supplier_name ||
    "—";
  const confPct = Math.round(Number(item.confidence) * 100);

  const toggle = async () => {
    if (!expanded && !enriched) {
      const resp = await getApproval(item.approval_id);
      setEnriched(resp.data);
    }
    setExpanded((e) => !e);
  };

  const handleApprove = async () => {
    const res = await onApprove();
    setResult({ success: res?.success ?? true, rejected: false });
    setRejectMode(false);
  };

  const handleReject = async () => {
    await onReject(rejectReason);
    setResult({ success: false, rejected: true });
    setRejectMode(false);
  };

  return (
    <div
      className={`approval-card ${expanded ? "approval-card--expanded" : ""}`}
    >
      {/* Collapsed header */}
      <div className="approval-card-header" onClick={toggle}>
        <div className="approval-card-left">
          <span className="approval-icon">
            <Icon size={18} />
          </span>
          <div>
            <div className="approval-card-title">{cfg.label}</div>
            <div className="approval-card-subject">{subject}</div>
          </div>
        </div>
        <div className="approval-card-right">
          <Badge type={item.risk_level}>
            {item.risk_level === "low"
              ? "Thấp"
              : item.risk_level === "medium"
                ? "Trung bình"
                : item.risk_level}
          </Badge>
          <span className="conf-pill">{confPct}%</span>
          {expanded ? (
            <ChevronUp size={16} color="var(--text-secondary)" />
          ) : (
            <ChevronDown size={16} color="var(--text-secondary)" />
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded &&
        (result ? (
          <div style={{ padding: "16px 18px" }}>
            <ResultBanner
              success={result.success}
              rejected={result.rejected}
              actionType={item.action_type}
            />
          </div>
        ) : enriched ? (
          <>
            <ApprovalDetail
              item={enriched}
              busy={busy}
              onApprove={handleApprove}
              onReject={() => setRejectMode(true)}
            />
            {rejectMode && (
              <div
                className="reject-inline-form"
                style={{ margin: "0 18px 18px" }}
              >
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
            )}
          </>
        ) : (
          <div
            style={{
              padding: "16px 20px",
              color: "var(--text-secondary)",
              fontSize: 13,
            }}
          >
            <Loader2 size={14} className="spin" style={{ marginRight: 6 }} />
            Đang tải chi tiết...
          </div>
        ))}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ApprovalsPage() {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState({});

  const refresh = () => getApprovals().then((r) => setItems(r.data));
  useEffect(() => {
    refresh();
  }, []);

  const handleApprove = async (id, draftParams) => {
    setBusy((b) => ({ ...b, [id]: true }));
    let result = { success: true };
    try {
      if (draftParams) await updateApprovalParams(id, draftParams);
      const res = await approveAction(id);
      result = { success: res.data?.success ?? true };
    } catch {
      result = { success: false };
    }
    await refresh();
    setBusy((b) => ({ ...b, [id]: false }));
    return result;
  };

  const handleReject = async (id, reason = "") => {
    setBusy((b) => ({ ...b, [id]: true }));
    await rejectAction(id, "admin", reason);
    await refresh();
    setBusy((b) => ({ ...b, [id]: false }));
  };

  const pending = items.filter((i) => i.status === "pending");
  const resolved = items.filter((i) => i.status !== "pending");

  return (
    <>
      <Topbar title="Hàng chờ phê duyệt" />
      <div className="page-content">
        {/* Pending */}
        <div
          style={{
            marginBottom: 8,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span style={{ fontWeight: 700, fontSize: 16 }}>Chờ xử lý</span>
          <span className="count-badge">{pending.length}</span>
        </div>

        {pending.length === 0 ? (
          <div className="card empty-state" style={{ marginBottom: 24 }}>
            <CheckCircle2
              size={36}
              color="var(--success)"
              style={{ marginBottom: 8 }}
            />
            <p>Không có hành động nào đang chờ duyệt.</p>
          </div>
        ) : (
          <div className="approval-list" style={{ marginBottom: 32 }}>
            {pending.map((item) => (
              <ApprovalCard
                key={item.approval_id}
                item={item}
                busy={!!busy[item.approval_id]}
                onApprove={(draft) => handleApprove(item.approval_id, draft)}
                onReject={(reason) => handleReject(item.approval_id, reason)}
              />
            ))}
          </div>
        )}

        {/* Resolved */}
        {resolved.length > 0 && (
          <div className="card">
            <div className="card-header" style={{ marginBottom: 12 }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>
                Đã xử lý ({resolved.length})
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Hành động</th>
                    <th>Trạng thái</th>
                    <th>Người duyệt</th>
                    <th>Lý do từ chối</th>
                  </tr>
                </thead>
                <tbody>
                  {resolved.map((item) => {
                    const cfg = ACTION_CONFIG[item.action_type] || {
                      label: item.action_type,
                      icon: Bell,
                    };
                    const Icon = cfg.icon;
                    return (
                      <tr key={item.approval_id}>
                        <td>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                            }}
                          >
                            <Icon size={14} color="var(--text-secondary)" />
                            <span>{cfg.label}</span>
                          </div>
                          <div
                            style={{
                              fontSize: 12,
                              color: "var(--text-secondary)",
                              marginTop: 2,
                            }}
                          >
                            {item.params?.product_sku ||
                              item.params?.partner_name ||
                              ""}
                          </div>
                        </td>
                        <td>
                          <Badge type={item.status}>
                            {{
                              approved: "Đã duyệt",
                              rejected: "Đã từ chối",
                              failed: "Lỗi thực thi",
                              pending: "Chờ",
                            }[item.status] || item.status}
                          </Badge>
                        </td>
                        <td style={{ fontSize: 13 }}>
                          {item.reviewed_by || "—"}
                        </td>
                        <td
                          style={{
                            fontSize: 12,
                            color: "var(--text-secondary)",
                          }}
                        >
                          {item.reject_reason || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
