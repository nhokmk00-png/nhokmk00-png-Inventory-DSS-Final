import axios from 'axios';

export const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
export const api = axios.create({ baseURL });

export async function getSummary() { return (await api.get('/api/summary')).data; }
export async function getRecommendations(params = {}) { return (await api.get('/api/recommendations', { params })).data; }
export async function getProducts(search = '') { return (await api.get('/api/products', { params: { search } })).data; }
export async function getInventory(search = '') { return (await api.get('/api/inventory', { params: { search } })).data; }
export async function getJourney(productId) { return (await api.get(`/api/products/${productId}/journey`)).data; }
export async function getDayDetail(date) { return (await api.get(`/api/flow/days/${date}`)).data; }
export async function getAllFlowTransactions() { return (await api.get('/api/flow/transactions')).data; }
export async function createVoucher(payload) { return (await api.post('/api/inventory/vouchers', payload)).data; }
export async function processDecision(id, payload) { return (await api.post(`/api/approval/${id}/internal`, payload)).data; }
export async function sendRecommendation(id) { return (await api.post(`/api/approval/${id}/send-telegram`)).data; }
export async function getApprovals() { return (await api.get('/api/approval/all')).data; }
export async function generateInsight(productId, force = false) { return (await api.post(`/api/gemini/insight/${productId}`, null, { params: { force } })).data; }
export async function chatGemini(payload) { return (await api.post('/api/gemini/chat', payload)).data; }
export async function sendSummaryNotification() { return (await api.post('/api/notifications/summary')).data; }
export async function getNotifications() { return (await api.get('/api/notifications')).data; }
export async function getImports() { return (await api.get('/api/imports')).data; }
export async function uploadExcel(file, uploadedBy = 'Nhân viên kho') {
  const form = new FormData();
  form.append('file', file);
  form.append('uploaded_by', uploadedBy);
  return (await api.post('/api/imports/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
}
export const templateUrl = `${baseURL}/api/imports/template`;
export const recommendationReportUrl = `${baseURL}/api/reports/recommendations.xlsx`;
