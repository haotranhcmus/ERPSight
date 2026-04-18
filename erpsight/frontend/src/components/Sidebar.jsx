import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  AlertTriangle,
  CheckCheck,
  History,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", end: true, icon: LayoutDashboard, label: "Tổng quan" },
  { to: "/anomalies", end: false, icon: AlertTriangle, label: "Bất thường" },
  { to: "/approvals", end: false, icon: CheckCheck, label: "Phê duyệt" },
  { to: "/action-logs", end: false, icon: History, label: "Lịch sử" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        ERP<span>Sight</span>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, end, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={end}>
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
