import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import AnomaliesPage from "./pages/AnomaliesPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import ActionLogsPage from "./pages/ActionLogsPage";

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/anomalies" element={<AnomaliesPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/action-logs" element={<ActionLogsPage />} />
        </Routes>
      </main>
    </div>
  );
}
