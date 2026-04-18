import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 60000,
});

export const triggerPipeline = () => api.post("/trigger");
export const getPipelineStatus = () => api.get("/trigger/status");

export const getAnomalies = () => api.get("/anomalies");
export const getAnomaly = (id) => api.get(`/anomalies/${id}`);

export const getReports = () => api.get("/reports");
export const getReport = (id) => api.get(`/reports/${id}`);

export const getApprovals = () => api.get("/approvals");
export const getApproval = (id) => api.get(`/approvals/${id}`);
export const approveAction = (id, reviewer = "admin") =>
  api.post(`/approvals/${id}/approve`, { reviewer });
export const rejectAction = (id, reviewer = "admin", reason = "") =>
  api.post(`/approvals/${id}/reject`, { reviewer, reason });
export const updateApprovalParams = (id, params) =>
  api.patch(`/approvals/${id}/params`, { params });

export const getActionLogs = () => api.get("/action-logs");

export default api;
