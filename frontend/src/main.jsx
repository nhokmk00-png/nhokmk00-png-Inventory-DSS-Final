import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  chatGemini,
  createVoucher,
  generateInsight,
  getApprovals,
  getAllFlowTransactions,
  getDayDetail,
  getImports,
  getJourney,
  getNotifications,
  getProducts,
  getRecommendations,
  getSummary,
  processDecision,
  recommendationReportUrl,
  sendRecommendation,
  sendSummaryNotification,
  templateUrl,
  uploadExcel,
} from './services/api';
import './styles.css';

const tabs = [
  ['home', 'Trang chủ'],
  ['approval', 'Xử lý đề xuất'],
  ['stock', 'Nhập hàng / Xuất hàng'],
  ['products', 'Danh sách sản phẩm'],
  ['excel', 'Nhập file Excel'],
];
const statusClass = { 'Nguy cấp': 'critical', 'Cần nhập': 'high', 'Dư tồn': 'over', 'Bán chậm': 'slow', 'Theo dõi': 'medium', 'An toàn': 'low' };
const statusColor = { 'Nguy cấp': '#dc2626', 'Cần nhập': '#f97316', 'Dư tồn': '#2563eb', 'Bán chậm': '#7c3aed', 'Theo dõi': '#f59e0b', 'An toàn': '#16a34a' };
const voucherTypes = ['Phiếu nhập hàng', 'Phiếu xuất bán', 'Phiếu điều chỉnh kiểm kê', 'Phiếu hàng lỗi / hủy', 'Phiếu điều chuyển chi nhánh'];

function n(value) { return new Intl.NumberFormat('vi-VN').format(Math.round(Number(value || 0))); }
function Badge({ value }) { return <span className={`badge ${statusClass[value] || ''}`}>{value}</span>; }
function Card({ title, value, note, tone }) { return <section className={`card metric ${tone || ''}`}><span>{title}</span><strong>{value}</strong><small>{note}</small></section>; }
function Empty({ text = 'Chưa có dữ liệu.' }) { return <div className="empty">{text}</div>; }

function App() {
  const [active, setActive] = useState('home');
  const [summary, setSummary] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [products, setProducts] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [imports, setImports] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState('SP001');
  const [journey, setJourney] = useState(null);
  const [dayDetail, setDayDetail] = useState(null);
  const [productStatusFilter, setProductStatusFilter] = useState('Tất cả');
  const [approvalFilter, setApprovalFilter] = useState('Tất cả');
  const [question, setQuestion] = useState('Sản phẩm này cần nhập hay cần điều chuyển?');
  const [chatAnswer, setChatAnswer] = useState(null);
  const [homeFocus, setHomeFocus] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  async function refresh(currentSearch = search, currentProduct = selected) {
    setLoading(true);
    const [s, rec, prod, app, noti, imps] = await Promise.all([
      getSummary(), getRecommendations({ search: currentSearch }), getProducts(currentSearch), getApprovals(), getNotifications(), getImports(),
    ]);
    setSummary(s);
    setRecommendations(rec.items || []);
    setProducts(prod.items || []);
    setApprovals(app.items || []);
    setAlerts(noti.items || []);
    setImports(imps.items || []);
    const chosen = currentProduct || rec.items?.[0]?.product_id || prod.items?.[0]?.product_id || 'SP001';
    setSelected(chosen);
    setJourney(await getJourney(chosen));
    setLoading(false);
  }
  useEffect(() => { refresh(); }, []);

  async function searchAll(e) { e.preventDefault(); await refresh(search, selected); }
  async function chooseProduct(productId, tab = null) { setSelected(productId); setJourney(await getJourney(productId)); setChatAnswer(null); if (tab) setActive(tab); }
  async function askGemini() { const answer = await chatGemini({ question }); setChatAnswer(answer); setMessage('Đã nhận phản hồi Gemini cho câu hỏi quản lý.'); await refresh(search, selected); }
  async function createInsight(force = true) { await generateInsight(selected, force); setMessage('Đã tạo nhận xét quản trị mới cho sản phẩm.'); await refresh(search, selected); }
  async function sendSummary() { const result = await sendSummaryNotification(); setMessage(`Đã xử lý thông báo tổng hợp: ${result.send_status}.`); setAlerts((await getNotifications()).items || []); }
  async function clickDay(date) { const data = await getDayDetail(date); setDayDetail(data); }
  async function showAllDays() { const data = await getAllFlowTransactions(); setDayDetail(data); }
  function showStatusProducts(status) { setProductStatusFilter(status); setApprovalFilter('Tất cả'); setActive('products'); }
  async function refreshReport() { await refresh(search, selected); setMessage('Báo cáo đã được cập nhật theo dữ liệu mới nhất.'); }
  async function submitVoucher(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const result = await createVoucher({
      product_id: form.get('product_id'), voucher_type: form.get('voucher_type'), movement_direction: form.get('movement_direction'),
      quantity: Number(form.get('quantity')), unit_price: Number(form.get('unit_price') || 0), price_note: form.get('price_note') || '', reason: form.get('reason'), recorded_by: form.get('recorded_by') || 'Nhân viên kho',
    });
    setMessage(`${result.voucher_type}: ${result.product_name}, tồn kho ${result.stock_before} → ${result.stock_after}, giá trị phiếu ${n(result.total_amount)}đ.`);
    await refresh(search, result.product_id);
  }
  async function internalDecision(id, decision) {
    const qty = Number(prompt('Số lượng cuối cùng nếu điều chỉnh, để trống nếu duyệt/hủy:', ''));
    const reason = prompt('Nhập lý do xử lý:', decision === 'REJECT' ? 'Không thực hiện kỳ này' : 'Đã kiểm tra tình hình thực tế') || '';
    await processDecision(id, { decision, final_quantity: Number.isFinite(qty) && qty >= 0 ? qty : null, reason, processed_by: 'Quản lý kho' });
    setMessage('Đã cập nhật quyết định nội bộ.'); await refresh(search, selected);
  }
  async function sendToBoss(id) { const result = await sendRecommendation(id); setMessage(`Đã gửi/lưu thông báo chi tiết: ${result.send_status}.`); await refresh(search, selected); }
  async function submitExcel(e) {
    e.preventDefault();
    const file = e.currentTarget.elements.excel_file.files[0];
    const uploadedBy = e.currentTarget.elements.uploaded_by.value || 'Nhân viên kho';
    if (!file) { setMessage('Vui lòng chọn file Excel.'); return; }
    const result = await uploadExcel(file, uploadedBy);
    setMessage(`Đã nhập file ${result.file_name}: ${result.valid_rows} dòng hợp lệ, ${result.error_rows} dòng lỗi.`);
    await refresh(search, selected);
  }

  const flowChart = summary?.inventory_flow || [];
  const statusChart = Object.entries(summary?.status_counts || {}).map(([name, value]) => ({ name, value, color: statusColor[name] }));
  const dangerItems = recommendations.filter((r) => ['Nguy cấp', 'Cần nhập'].includes(r.business_status));
  const strategyItems = recommendations.filter((r) => ['Dư tồn', 'Bán chậm'].includes(r.business_status));
  const demandChart = (journey?.demand_history || []).slice(-14).map((row) => ({ date: row.demand_date.slice(5), 'Nhu cầu': row.net_demand }));
  const txChart = (journey?.transactions || []).slice().reverse().map((tx) => ({
    date: tx.transaction_date.slice(5, 10),
    Nhập: ['RECEIPT', 'ADJUSTMENT_IN'].includes(tx.transaction_type) ? tx.quantity : 0,
    Xuất: ['SALE_OUT', 'ADJUSTMENT_OUT', 'TRANSFER_OUT', 'DISPOSE'].includes(tx.transaction_type) ? tx.quantity : 0,
  }));
  const selectedRec = recommendations.find((item) => item.product_id === selected);

  if (loading && !summary) return <main className="loading">Đang tải hệ thống...</main>;
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><strong>Inventory DSS</strong><span>Quản lý tồn kho bán lẻ</span></div>
      <nav>{tabs.map(([key, label]) => <button key={key} className={active === key ? 'nav-active' : ''} onClick={() => setActive(key)}>{label}</button>)}</nav>
    </aside>
    <main className="content">
      <header className="hero">
        <div><p className="eyebrow">Dashboard quản lý</p><h1>Hệ thống hỗ trợ quản lý tồn kho</h1><p>Phát hiện thiếu hàng, dư tồn, bán chậm; hỗ trợ duyệt đề xuất, gửi thông báo và cập nhật phiếu kho.</p></div>
        <form className="search" onSubmit={searchAll}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nhập mã hoặc tên sản phẩm: SP001, áo thun, jeans..." /><button>Tìm kiếm</button></form>
      </header>
      {message && <div className="notice">{message}</div>}
      {active === 'home' && <Home summary={summary} statusChart={statusChart} flowChart={flowChart} dangerItems={dangerItems} strategyItems={strategyItems} alerts={alerts} dayDetail={dayDetail} clickDay={clickDay} showAllDays={showAllDays} showStatusProducts={showStatusProducts} chooseProduct={chooseProduct} sendSummary={sendSummary} question={question} setQuestion={setQuestion} chatAnswer={chatAnswer} askGemini={askGemini} refreshReport={refreshReport} homeFocus={homeFocus} setHomeFocus={setHomeFocus} />}
      {active === 'approval' && <ApprovalPage approvals={approvals} internalDecision={internalDecision} sendToBoss={sendToBoss} chooseProduct={chooseProduct} />}
      {active === 'stock' && <StockPage products={products} selected={selected} journey={journey} submitVoucher={submitVoucher} chooseProduct={chooseProduct} />}
      {active === 'products' && <ProductsPage products={products} selected={selected} journey={journey} recommendations={recommendations} demandChart={demandChart} txChart={txChart} chooseProduct={chooseProduct} productStatusFilter={productStatusFilter} setProductStatusFilter={setProductStatusFilter} approvalFilter={approvalFilter} setApprovalFilter={setApprovalFilter} />}
      {active === 'excel' && <ExcelPage imports={imports} submitExcel={submitExcel} />}
    </main>
  </div>;
}

function Home({ summary, statusChart, flowChart, dangerItems, strategyItems, alerts, dayDetail, clickDay, showAllDays, showStatusProducts, chooseProduct, sendSummary, question, setQuestion, chatAnswer, askGemini, refreshReport, homeFocus, setHomeFocus }) {
  const focus = homeFocus || dangerItems[0] || strategyItems[0];
  function pickItem(item) { setHomeFocus(item); }
  return <>
    <section className="grid metrics">
      <Card title="Sản phẩm cần nhập" value={summary?.restock_count ?? 0} note="Nguy cấp / cần nhập" tone="orange" />
      <Card title="Dư tồn / bán chậm" value={summary?.strategy_count ?? 0} note="Cần chiến lược xử lý" tone="blue" />
      <Card title="Chờ xử lý nội bộ" value={summary?.pending_approval_count ?? 0} note="Duyệt / điều chỉnh / hủy" tone="yellow" />
      <Card title="Giá trị vốn tồn kho" value={`${n((summary?.total_inventory_value_cost || 0) / 1000000)} tr`} note="Theo giá nhập" tone="green" />
    </section>
    <section className="grid two">
      <div className="card quick"><div className="section-title"><h2>Báo cáo nhanh cho quản lý</h2><button className="ghost" onClick={refreshReport}>Cập nhật lại báo cáo</button></div><p className="updated-time">Cập nhật lúc: {summary?.quick_report?.last_updated || summary?.last_updated}</p><p>{summary?.quick_report?.headline}</p><p>{summary?.quick_report?.risk_line}</p><p>{summary?.quick_report?.strategy_line}</p><p>{summary?.quick_report?.quantity_line}</p><p>{summary?.quick_report?.approval_line}</p><p>{summary?.quick_report?.priority_line}</p><a className="button-link" href={recommendationReportUrl}>Tải báo cáo xử lý tồn kho</a><button onClick={sendSummary}>Gửi báo cáo tổng hợp</button></div>
      <div className="card"><h2>Trạng thái tồn kho</h2><ResponsiveContainer width="100%" height={260}><BarChart data={statusChart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="value" name="Số sản phẩm" onClick={(entry) => showStatusProducts(entry?.name || entry?.payload?.name)}>{statusChart.map((entry) => <Cell key={entry.name} fill={entry.color} />)}</Bar></BarChart></ResponsiveContainer><p className="hint">Bấm vào từng cột để lọc danh sách sản phẩm theo trạng thái.</p></div>
    </section>
    <section className="grid two equal-cards">
      <div className="card"><div className="section-title"><h2>Top sản phẩm nguy cấp</h2><button className="link-button" onClick={() => showStatusProducts('Cần nhập')}>Xem tất cả</button></div><div className="mini-list">{dangerItems.slice(0, 6).map((r) => <button key={r.product_id} onClick={() => pickItem(r)} className={focus?.product_id === r.product_id ? 'selected-pill' : ''}><b>{r.product_id}</b> {r.product_name}<Badge value={r.business_status} /><span>{n(r.proposed_quantity)}</span></button>)}</div></div>
      <div className="card"><div className="section-title"><h2>Sản phẩm dư tồn / cần chiến lược</h2><button className="link-button" onClick={() => showStatusProducts('Dư tồn')}>Xem tất cả</button></div><div className="mini-list">{strategyItems.slice(0, 6).map((r) => <button key={r.product_id} onClick={() => pickItem(r)} className={focus?.product_id === r.product_id ? 'selected-pill' : ''}><b>{r.product_id}</b> {r.product_name}<Badge value={r.business_status} /><span>tồn {n(r.stock_on_hand)}</span></button>)}</div></div>
    </section>
    {focus && <section className={`card focus-card ${statusClass[focus.business_status] || ''}`}><div><h2>{focus.product_id} - {focus.product_name}</h2><p><b>Tình trạng:</b> {focus.business_status}. <b>Danh mục:</b> {focus.category}. <b>Giá bán:</b> {n(focus.unit_price)}đ. <b>Giá nhập:</b> {n(focus.purchase_price)}đ.</p><p><b>Đề xuất:</b> {focus.recommendation_type === 'RESTOCK' ? `Nhập ${n(focus.proposed_quantity)} sản phẩm` : focus.action_strategy}</p><p><b>Gợi ý quản trị:</b> {focus.ai_suggested_action || focus.action_strategy}</p></div><button onClick={() => chooseProduct(focus.product_id, 'products')}>Xem chi tiết sản phẩm</button></section>}
    <section className="grid two">
      <div className="card"><div className="section-title"><h2>Nhập / xuất hàng theo ngày</h2><button className="link-button" onClick={showAllDays}>Xem tất cả</button></div><ResponsiveContainer width="100%" height={260}><BarChart data={flowChart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis /><Tooltip /><Legend /><Bar dataKey="inbound" name="Nhập hàng" fill="#16a34a" /><Bar dataKey="outbound" name="Xuất / điều chuyển / hủy" fill="#ef4444" /></BarChart></ResponsiveContainer><div className="date-buttons">{flowChart.map((d) => <button key={d.date} className="ghost" onClick={() => clickDay(d.date)}>{d.date}</button>)}</div>{dayDetail && <div className="day-detail"><h3>{dayDetail.date === 'Tất cả' ? 'Tất cả giao dịch nhập / xuất' : `Chi tiết ngày ${dayDetail.date}`}</h3>{dayDetail.items.map((tx) => <div key={tx.transaction_id}><b>{tx.product_id}</b> {tx.product_name} · {tx.voucher_type} · {tx.quantity}<br /><small>{tx.recorded_by} · {tx.transaction_date} · Đơn giá {n(tx.unit_price)}đ · Thành tiền {n(tx.total_amount)}đ</small></div>)}</div>}</div>
      <div className="card ai-card"><h2>Hỏi Gemini về tình hình tồn kho</h2><p className="muted">Có thể hỏi một sản phẩm hoặc nhiều sản phẩm cùng lúc, ví dụ: “so sánh SP001 và SP004”, “mặt hàng nào đang giữ vốn nhiều?”.</p><textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows="4" /><button onClick={askGemini}>Gửi câu hỏi</button>{chatAnswer && <div className="ai-box"><b>Trả lời:</b><p>{chatAnswer.answer}</p></div>}</div>
    </section>
    <section className="card"><h2>Lịch sử thông báo</h2><div className="timeline small">{alerts.length ? alerts.map((a) => <div key={a.alert_id}><b>{a.send_status}</b> {a.product_id || 'Báo cáo tổng hợp'}<br /><small>{a.created_at}</small><p>{a.message}</p></div>) : <Empty />}</div></section>
  </>;
}

function ApprovalPage({ approvals, internalDecision, sendToBoss, chooseProduct }) {
  return <section className="card"><h2>Xử lý đề xuất</h2><p className="muted">Quy trình: hệ thống tạo đề xuất → quản lý duyệt/điều chỉnh/hủy → gửi thông báo chi tiết cho cấp trên qua Telegram.</p><div className="approval-list">{approvals.map((r) => <div key={r.recommendation_id} className={`approval-card ${statusClass[r.business_status]}`}><div><b>{r.product_id} - {r.product_name}</b><Badge value={r.business_status} /><p>{r.trigger_reason}</p><p><b>Phương án:</b> {r.action_strategy}</p><p><b>Đề xuất:</b> {r.proposed_quantity} · <b>Xử lý nội bộ:</b> {r.internal_status} · <b>Thông báo:</b> {r.telegram_status}</p>{r.internal_reason && <p><b>Lý do xử lý:</b> {r.internal_reason}</p>}</div><div className="actions"><button onClick={() => chooseProduct(r.product_id, 'products')}>Xem sản phẩm</button><button onClick={() => internalDecision(r.recommendation_id, 'APPROVE')}>Duyệt</button><button className="warn" onClick={() => internalDecision(r.recommendation_id, 'ADJUST')}>Điều chỉnh</button><button className="danger" onClick={() => internalDecision(r.recommendation_id, 'REJECT')}>Hủy</button><button className="telegram" onClick={() => sendToBoss(r.recommendation_id)}>Gửi thông báo</button></div></div>)}</div></section>;
}

function StockPage({ products, selected, journey, submitVoucher, chooseProduct }) {
  const currentProduct = products.find((p) => p.product_id === selected) || {};
  return <section className="grid two stock-grid"><div className="card"><h2>Nhập hàng / Xuất hàng</h2><p className="muted">Mỗi phiếu kho có đơn giá thực tế tại thời điểm phát sinh. Giá này có thể khác giá niêm yết do giá nhập thay đổi hoặc khách hàng lớn được ưu đãi.</p><form className="form" onSubmit={submitVoucher}><label>Sản phẩm<select name="product_id" value={selected} onChange={(e) => chooseProduct(e.target.value)}>{products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_id} - {p.product_name}</option>)}</select></label><div className="price-hint"><span>Giá nhập hiện hành: <b>{n(currentProduct.purchase_price)}đ</b></span><span>Giá bán niêm yết: <b>{n(currentProduct.unit_price)}đ</b></span></div><label>Loại phiếu<select name="voucher_type">{['Phiếu nhập hàng','Phiếu xuất bán','Phiếu điều chỉnh kiểm kê','Phiếu hàng lỗi / hủy','Phiếu điều chuyển chi nhánh'].map((v) => <option key={v}>{v}</option>)}</select></label><label>Hướng xử lý khi kiểm kê<select name="movement_direction"><option value="IN">Tăng tồn kho</option><option value="OUT">Giảm tồn kho</option></select></label><label>Số lượng<input type="number" name="quantity" min="1" defaultValue="5" /></label><label>Đơn giá thực tế trên mỗi sản phẩm<input type="number" name="unit_price" min="0" defaultValue={currentProduct.purchase_price || 0} /></label><label>Ghi chú về giá<input name="price_note" defaultValue="Theo giá thực tế tại thời điểm lập phiếu" /></label><label>Người ghi nhận<input name="recorded_by" defaultValue="Nhân viên kho" /></label><label>Lý do / ghi chú nghiệp vụ<input name="reason" defaultValue="Xử lý phiếu kho trong ngày" /></label><button>Lưu phiếu kho</button></form></div><div className="card"><h2>Giao dịch kho gần nhất</h2><div className="timeline">{journey?.transactions?.length ? journey.transactions.map((tx) => <div key={tx.transaction_id}><b>{tx.voucher_type}</b> · {tx.quantity} sản phẩm<br /><small>{tx.stock_before} → {tx.stock_after} · Đơn giá {n(tx.unit_price)}đ · Thành tiền {n(tx.total_amount)}đ</small><br /><small>{tx.recorded_by} · {tx.transaction_date}</small>{tx.price_note && <p><b>Giá:</b> {tx.price_note}</p>}<p>{tx.note}</p></div>) : <Empty />}</div></div></section>;
}

function ProductsPage({ products, selected, journey, recommendations, demandChart, txChart, chooseProduct, productStatusFilter, setProductStatusFilter, approvalFilter, setApprovalFilter }) {
  const rec = recommendations.find((r) => r.product_id === selected);
  const statusOptions = ['Tất cả', 'Nguy cấp', 'Cần nhập', 'Dư tồn', 'Bán chậm', 'Theo dõi', 'An toàn'];
  const approvalOptions = ['Tất cả', 'Chờ xử lý', 'Đã duyệt', 'Đã điều chỉnh', 'Đã hủy', 'Đã gửi'];
  const filteredProducts = products.filter((p) => {
    const statusOk = productStatusFilter === 'Tất cả' || p.business_status === productStatusFilter;
    const approvalOk = approvalFilter === 'Tất cả'
      || p.internal_status === approvalFilter
      || p.telegram_status === approvalFilter
      || p.boss_status === approvalFilter;
    return statusOk && approvalOk;
  });
  return <section className="grid two product-grid">
    <div className="card"><h2>Danh sách sản phẩm</h2>
      <div className="filters">
        <label>Trạng thái tồn kho<select value={productStatusFilter} onChange={(e) => setProductStatusFilter(e.target.value)}>{statusOptions.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>Trạng thái xử lý<select value={approvalFilter} onChange={(e) => setApprovalFilter(e.target.value)}>{approvalOptions.map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <div className="product-list">{filteredProducts.map((p) => <button key={p.product_id} onClick={() => chooseProduct(p.product_id)} className={`${selected === p.product_id ? 'selected-pill' : ''} ${statusClass[p.business_status] || ''}`}><b>{p.product_id}</b><span>{p.product_name}</span><small>{p.category} · tồn {n(p.stock_on_hand)} · {p.business_status} · {p.internal_status || 'Chưa có đề xuất'} · {p.boss_status || 'Chưa gửi'}</small></button>)}</div>
      {!filteredProducts.length && <Empty text="Không có sản phẩm phù hợp bộ lọc." />}
    </div>
    <div className="card"><h2>Chi tiết sản phẩm</h2>{journey?.product ? <><div className="product-title">{journey.product.product_id} - {journey.product.product_name}</div><div className="detail-grid"><span>Nhóm hàng</span><b>{journey.product.category}</b><span>Nhà cung cấp</span><b>{journey.product.supplier_name}</b><span>Giá bán</span><b>{n(journey.product.unit_price)}đ</b><span>Giá nhập</span><b>{n(journey.product.purchase_price)}đ</b><span>Lãi gộp/SP</span><b>{n((journey.product.unit_price || 0) - (journey.product.purchase_price || 0))}đ</b><span>Giá trị tồn kho</span><b>{n((journey.product.purchase_price || 0) * (rec?.stock_on_hand || 0))}đ</b><span>Doanh thu dự báo 7 ngày</span><b>{n(rec?.forecast_revenue_7_days)}đ</b><span>Lãi gộp dự kiến 7 ngày</span><b>{n(rec?.forecast_gross_profit_7_days)}đ</b><span>Đánh giá</span><Badge value={rec?.business_status} /><span>Đề xuất</span><b>{rec?.recommendation_type === 'RESTOCK' ? `${n(rec?.proposed_quantity)} sản phẩm` : rec?.action_strategy}</b><span>Nội bộ</span><b>{rec?.internal_status}</b></div><div className={`management-box ${statusClass[rec?.business_status] || ''}`}><h3>Đánh giá quản trị</h3><p>{rec?.trigger_reason}</p><p><b>Hướng xử lý:</b> {rec?.action_strategy}</p></div><h3>Nhu cầu 14 ngày gần nhất</h3><ResponsiveContainer width="100%" height={220}><LineChart data={demandChart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis /><Tooltip /><Line dataKey="Nhu cầu" stroke="#2563eb" strokeWidth={3} /></LineChart></ResponsiveContainer><h3>Nhập / xuất của sản phẩm</h3><ResponsiveContainer width="100%" height={220}><BarChart data={txChart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis /><Tooltip /><Legend /><Bar dataKey="Nhập" fill="#16a34a" /><Bar dataKey="Xuất" fill="#ef4444" /></BarChart></ResponsiveContainer></> : <Empty />}</div>
  </section>;
}

function ExcelPage({ imports, submitExcel }) { return <section className="grid two"><div className="card"><h2>Nhập file Excel</h2><p className="muted">Tải mẫu, nhập phiếu kho vào Excel rồi upload. Hệ thống kiểm tra dòng hợp lệ/lỗi và ghi lịch sử nhập file.</p><a className="button-link" href={templateUrl}>Tải mẫu Excel</a><form className="form" onSubmit={submitExcel}><label>Người nhập<input name="uploaded_by" defaultValue="Nhân viên kho" /></label><label>File Excel<input name="excel_file" type="file" accept=".xlsx" /></label><button>Upload và xử lý</button></form></div><div className="card"><h2>Lịch sử nhập file</h2><div className="table-wrap"><table><thead><tr><th>Ngày nhập</th><th>Tên file</th><th>Người nhập</th><th>Hợp lệ</th><th>Lỗi</th><th>Trạng thái</th></tr></thead><tbody>{imports.map((item) => <tr key={item.import_id}><td>{item.import_date}</td><td>{item.file_name}</td><td>{item.uploaded_by}</td><td>{item.valid_rows}</td><td>{item.error_rows}</td><td><span className="status">{item.status}</span></td></tr>)}</tbody></table></div></div></section>; }

createRoot(document.getElementById('root')).render(<App />);
