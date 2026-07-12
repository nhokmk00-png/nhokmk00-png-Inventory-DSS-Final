const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request(path, options = {}) {
  const token = localStorage.getItem('inventory_token');
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = 'Có lỗi khi gọi API';
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export const apiBase = API;
export const templateUrl = `${API}/api/excel/template`;
export const recommendationReportUrl = `${API}/api/reports/recommendations.xlsx`;
export const login = (payload) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) });
export const getSummary = () => request('/api/dashboard/summary');
export const getProducts = (params = {}) => request(`/api/products?${new URLSearchParams(params)}`);
export const getProduct = (id) => request(`/api/products/${id}`);
export const updateProduct = (id, payload) => request(`/api/products/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteProduct = (id) => request(`/api/products/${id}`, { method: 'DELETE' });
export const getRecommendations = (params = {}) => request(`/api/recommendations?${new URLSearchParams(params)}`);
export const processDecision = (id, payload) => request(`/api/recommendations/${id}/decision`, { method: 'POST', body: JSON.stringify(payload) });
export const sendRecommendation = (id) => request(`/api/recommendations/${id}/send`, { method: 'POST' });
export const createVoucher = (payload) => request('/api/inventory/vouchers', { method: 'POST', body: JSON.stringify(payload) });
export const getImports = (params = {}) => request(`/api/excel/imports?${new URLSearchParams(params)}`);
export const getImportDetail = (id) => request(`/api/excel/imports/${id}`);
export const uploadExcel = (file, uploadedBy) => {
  const form = new FormData();
  form.append('excel_file', file);
  form.append('uploaded_by', uploadedBy);
  return request('/api/excel/upload', { method: 'POST', body: form });
};
export const chatAI = (question) => request('/api/ai/chat', { method: 'POST', body: JSON.stringify({ question }) });
export const getNotifications = () => request('/api/notifications');
export const sendSummaryNotification = () => request('/api/notifications/summary/send', { method: 'POST' });
export const getConfigStatus = () => request('/api/config/status');
