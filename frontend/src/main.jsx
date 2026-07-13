import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  chatAI,
  createVoucher,
  deleteProduct,
  getConfigStatus,
  getImportDetail,
  getImports,
  getNotifications,
  getProduct,
  getProducts,
  getRecommendations,
  getSummary,
  login,
  processDecision,
  recommendationReportUrl,
  sendRecommendation,
  sendSummaryNotification,
  templateUrl,
  updateProduct,
  uploadExcel,
} from './services/api.js';
import './styles.css';

const tabs = [
  ['home', 'Trang chủ'],
  ['approval', 'Xử lý đề xuất'],
  ['stock', 'Nhập hàng / Xuất hàng'],
  ['products', 'Danh sách sản phẩm'],
  ['excel', 'Nhập file Excel'],
];

const statuses = ['Tất cả', 'Nguy cấp', 'Cần nhập', 'Dư tồn', 'Bán chậm', 'Theo dõi', 'An toàn'];
const internalStatuses = ['Tất cả', 'Chờ xử lý', 'Đã duyệt', 'Đã điều chỉnh', 'Đã hủy'];
const statusClass = {
  'Nguy cấp': 'critical',
  'Cần nhập': 'high',
  'Dư tồn': 'over',
  'Bán chậm': 'slow',
  'Theo dõi': 'medium',
  'An toàn': 'low',
};
const voucherTypes = ['Phiếu nhập hàng', 'Phiếu xuất bán', 'Phiếu điều chỉnh kiểm kê', 'Phiếu hàng lỗi / hủy', 'Phiếu điều chuyển chi nhánh'];

function n(value) {
  return new Intl.NumberFormat('vi-VN').format(Math.round(Number(value || 0)));
}

function formatSendStatus(status) {
  if (status === 'SENT') return 'Đã gửi Telegram';
  if (status === 'SAVED') return 'Đã lưu trong hệ thống';
  if (status === 'PARTIAL') return 'Đã gửi tin, thiếu file Excel';
  if (status === 'FAILED') return 'Gửi thất bại';
  return status || 'Chưa rõ';
}

function noticeForSendStatus(status, target = 'thông báo') {
  if (status === 'SENT') return `Đã gửi ${target} tới Telegram thành công.`;
  if (status === 'SAVED') return `Đã lưu ${target} vào lịch sử thông báo. Vui lòng kiểm tra lại cấu hình Telegram nếu muốn gửi ra ngoài.`;
  if (status === 'PARTIAL') return `Đã gửi ${target} tới Telegram nhưng file Excel chưa gửi được. Vui lòng kiểm tra kết nối hoặc quyền của bot.`;
  if (status === 'FAILED') return `Hệ thống đã tạo ${target} nhưng chưa gửi được Telegram. Vui lòng kiểm tra bot token, chat ID hoặc kết nối mạng.`;
  return `Đã xử lý ${target}.`;
}

function splitMessageLines(message) {
  return String(message || '').split('\n').map((x) => x.trim()).filter(Boolean);
}

function Badge({ value }) {
  return <span className={`badge ${statusClass[value] || ''}`}>{value || 'Chưa có'}</span>;
}

function Empty({ text = 'Chưa có dữ liệu.' }) {
  return <div className="empty">{text}</div>;
}

function Pager({ page, totalPages, onPage }) {
  if (!totalPages || totalPages <= 1) return null;
  return (
    <div className="pager">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)}>‹ Trước</button>
      <span>Trang {page}/{totalPages}</span>
      <button disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Sau ›</button>
    </div>
  );
}

function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function submit(e) {
    e.preventDefault();
    try {
      const result = await login({ username, password });
      localStorage.setItem('inventory_token', result.access_token);
      localStorage.setItem('inventory_user', result.username || username);
      onLoggedIn(result.username || username);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <h1>Inventory DSS</h1>
        <p>Đăng nhập để truy cập hệ thống quản lý tồn kho.</p>
        <label>Tài khoản<input placeholder="Nhập tài khoản" value={username} onChange={(e) => setUsername(e.target.value)} /></label>
        <label>Mật khẩu<input type="password" placeholder="Nhập mật khẩu" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <div className="error">{error}</div>}
        <button>Đăng nhập</button>
      </form>
    </main>
  );
}

function App() {
  const [isLogged, setLogged] = useState(Boolean(localStorage.getItem('inventory_token')));
  const [currentUser, setCurrentUser] = useState(localStorage.getItem('inventory_user') || '');
  const [active, setActive] = useState('home');
  const [summary, setSummary] = useState(null);
  const [recs, setRecs] = useState({ items: [], page: 1, total_pages: 1, total: 0 });
  const [products, setProducts] = useState({ items: [], page: 1, total_pages: 1, total: 0 });
  const [imports, setImports] = useState({ items: [], page: 1, total_pages: 1, total: 0 });
  const [notifications, setNotifications] = useState([]);
  const [selected, setSelected] = useState('SP001');
  const [journey, setJourney] = useState(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('Tất cả');
  const [internalStatus, setInternalStatus] = useState('Tất cả');
  const [message, setMessage] = useState('');
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);

  async function refresh(page = 1) {
    setLoading(true);
    try {
      const [s, r, p, im, nfs, cfg] = await Promise.all([
        getSummary(),
        getRecommendations({ search, status, internal_status: internalStatus, page, page_size: 6 }),
        getProducts({ search, status, page: 1, page_size: 100 }),
        getImports({ page: 1, page_size: 6 }),
        getNotifications(),
        getConfigStatus(),
      ]);
      setSummary(s);
      setRecs(r);
      setProducts(p);
      setImports(im);
      setNotifications(nfs.items || []);
      setConfig(cfg);
      const chosen = selected || p.items?.[0]?.product_id || 'SP001';
      setSelected(chosen);
      setJourney(await getProduct(chosen));
    } catch (err) {
      setMessage(err.message);
    }
    setLoading(false);
  }

  useEffect(() => { if (isLogged) refresh(); }, [isLogged]);
  useEffect(() => { if (isLogged) refresh(1); }, [status, internalStatus]);

  async function chooseProduct(id, tab) {
    setSelected(id);
    setJourney(await getProduct(id));
    if (tab) setActive(tab);
  }

  function logout() {
    localStorage.removeItem('inventory_token');
    localStorage.removeItem('inventory_user');
    setCurrentUser('');
    setLogged(false);
  }

  if (!isLogged) return <LoginPage onLoggedIn={(username) => { setCurrentUser(username || ''); setLogged(true); }} />;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h2>Inventory DSS</h2>
          <span>SQL quản lý tồn kho bán lẻ</span>
        </div>
        <div className="user-chip">
          <div className="user-avatar">{(currentUser || 'A').slice(0, 1).toUpperCase()}</div>
          <div>
            <strong>{currentUser || config?.admin_username || 'Quản trị'}</strong>
            <small>Đang đăng nhập</small>
          </div>
        </div>
        {tabs.map(([key, label]) => (
          <button key={key} className={active === key ? 'active' : ''} onClick={() => setActive(key)}>{label}</button>
        ))}
        <button className="logout" onClick={logout}>Đăng xuất</button>
      </aside>

      <main className="app-main">
        <header className="hero">
          <div className="hero-text">
            <b>DASHBOARD QUẢN LÝ</b>
            <h1>Hệ thống hỗ trợ quản lý tồn kho</h1>
            <p>Đọc dữ liệu từ SQL, xử lý đề xuất, nhập/xuất hàng, upload Excel, hỏi AI và gửi Telegram.</p>
            <small>Database: {config?.database_mode || 'SQL'} · Người dùng: {currentUser || config?.admin_username || 'Quản trị'}</small>
          </div>
          {active !== 'excel' && (
            <form className="search" onSubmit={(e) => { e.preventDefault(); refresh(1); }}>
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tìm mã/tên SP: SP001, áo, jeans..." />
              <button>Tìm kiếm</button>
            </form>
          )}
        </header>

        {message && <div className="notice">{message}</div>}
        {loading && <div className="loading">Đang tải dữ liệu...</div>}

        {active === 'home' && <Home summary={summary} recs={recs.items} notifications={notifications} setActive={setActive} setStatus={setStatus} chooseProduct={chooseProduct} setMessage={setMessage} />}
        {active === 'approval' && <Approval recs={recs} status={status} setStatus={setStatus} internalStatus={internalStatus} setInternalStatus={setInternalStatus} refresh={refresh} chooseProduct={chooseProduct} setMessage={setMessage} />}
        {active === 'stock' && <Stock products={products.items.filter((p) => p.is_active !== 0)} selected={selected} chooseProduct={chooseProduct} journey={journey} refresh={refresh} setMessage={setMessage} />}
        {active === 'products' && <Products products={products.items} selected={selected} chooseProduct={chooseProduct} journey={journey} status={status} setStatus={setStatus} refresh={refresh} setMessage={setMessage} />}
        {active === 'excel' && <Excel imports={imports} setImports={setImports} refresh={refresh} setMessage={setMessage} />}
      </main>
    </div>
  );
}

function Card({ title, value, tone = '' }) {
  return <div className={`card metric ${tone}`}><span>{title}</span><strong>{n(value)}</strong></div>;
}

function Home({ summary, recs, notifications, setActive, setStatus, chooseProduct, setMessage }) {
  const topNeed = recs.filter((r) => ['Nguy cấp', 'Cần nhập'].includes(r.business_status)).slice(0, 6);
  const topOver = recs.filter((r) => ['Dư tồn', 'Bán chậm'].includes(r.business_status)).slice(0, 6);

  async function sendSummary() {
    const result = await sendSummaryNotification();
    setMessage(noticeForSendStatus(result.send_status, 'báo cáo tổng hợp'));
  }

  return (
    <>
      <section className="metrics">
        <Card title="Sản phẩm" value={summary?.total_products} />
        <Card title="Cần nhập" value={summary?.need_restock} tone="high" />
        <Card title="Dư tồn/bán chậm" value={summary?.overstock_slow} tone="over" />
        <Card title="Chờ xử lý" value={summary?.waiting_internal} tone="medium" />
        <Card title="Giá trị vốn tồn" value={summary?.total_purchase_value} />
        <Card title="Giá trị bán tồn" value={summary?.total_sell_value} />
      </section>

      <section className="grid two">
        <div className="card">
          <h2>Báo cáo nhanh cho quản lý</h2>
          <p>{summary?.quick_report?.headline}</p>
          <p>{summary?.quick_report?.risk_line}</p>
          <p>{summary?.quick_report?.quantity_line}</p>
          <p>{summary?.quick_report?.approval_line}</p>
          <p><b>{summary?.quick_report?.priority_line}</b></p>
          <div className="actions">
            <a className="button-link" href={recommendationReportUrl}>Tải báo cáo Excel</a>
            <button onClick={sendSummary}>Gửi báo cáo tổng hợp</button>
          </div>
        </div>

        <div className="card">
          <h2>Trạng thái tồn kho</h2>
          {Object.entries(summary?.status_counts || {}).map(([k, v]) => (
            <button className={`status-row ${statusClass[k] || ''}`} key={k} onClick={() => { setStatus(k); setActive('approval'); }}>
              <span className="row-label">{k}</span><span className="count-pill">{n(v)}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="grid two">
        <div className="card">
          <h2>Sản phẩm cần ưu tiên</h2>
          {topNeed.length ? topNeed.map((r) => (
            <button className="list-item" key={r.recommendation_id} onClick={() => chooseProduct(r.product_id, 'products')}>
              <b>{r.product_id} - {r.product_name}</b>
              <span><Badge value={r.business_status} /> Đề xuất nhập {n(r.proposed_quantity)} · điều chuyển {n(r.transfer_quantity)}</span>
            </button>
          )) : <Empty />}
        </div>
        <div className="card">
          <h2>Dư tồn / bán chậm</h2>
          {topOver.length ? topOver.map((r) => (
            <button className="list-item" key={r.recommendation_id} onClick={() => chooseProduct(r.product_id, 'products')}>
              <b>{r.product_id} - {r.product_name}</b>
              <span><Badge value={r.business_status} /> tồn {n(r.stock_on_hand)} · điều chuyển {n(r.transfer_quantity)}</span>
            </button>
          )) : <Empty />}
        </div>
      </section>

      <section className="grid two">
        <InventoryFlow data={summary?.inventory_flow || []} />
        <AIBlock setMessage={setMessage} />
      </section>

      <section className="card">
        <h2>Lịch sử thông báo</h2>
        <div className="notification-list">
          {notifications.length ? notifications.slice(0, 6).map((x) => (
            <NotificationCard key={x.alert_id} item={x} />
          )) : <Empty />}
        </div>
      </section>
    </>
  );
}

function AIBlock({ setMessage }) {
  const [question, setQuestion] = useState('Sản phẩm nào cần nhập và sản phẩm nào nên điều chuyển?');
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  async function ask(e) {
    e.preventDefault();
    setAsking(true);
    try {
      const a = await chatAI(question);
      setAnswer(a);
      setMessage(a.generation_status === 'LIVE'
        ? `Gemini đã trả lời dựa trên dữ liệu của hệ thống (${a.model_name}).`
        : 'Gemini chưa khả dụng nên hệ thống đã dùng phản hồi dự phòng từ dữ liệu SQL.');
    } catch (err) {
      setMessage(err.message);
    }
    setAsking(false);
  }

  return (
    <div className="card ai-card">
      <div className="section-title">
        <div>
          <h2>Hỏi AI / Gemini</h2>
          <p className="muted">Nhập câu hỏi quản trị tồn kho. Phản hồi sẽ được chia theo nhóm cần nhập, dư tồn/bán chậm và hành động đề xuất.</p>
        </div>
      </div>
      <form className="ai-form" onSubmit={ask}>
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows="4" />
        <button disabled={asking}>{asking ? 'Đang xử lý...' : 'Gửi câu hỏi'}</button>
      </form>
      {answer && <AiAnswer answer={answer} />}
    </div>
  );
}

function InventoryFlow({ data }) {
  const [activePoint, setActivePoint] = useState(data?.[data.length - 1] || null);
  const max = Math.max(1, ...data.flatMap((x) => [x['Nhập'] || 0, x['Xuất'] || 0]));

  useEffect(() => {
    setActivePoint(data?.[data.length - 1] || null);
  }, [data]);

  return (
    <div className="card">
      <h2>Nhập / xuất hàng theo ngày</h2>
      {data.length ? (
        <>
          <div className="flow-chart">
            {data.map((d) => (
              <button
                type="button"
                className={`flow-day ${activePoint?.date === d.date ? 'active' : ''}`}
                key={d.date}
                onMouseEnter={() => setActivePoint(d)}
                onFocus={() => setActivePoint(d)}
                onClick={() => setActivePoint(d)}
                title={`${d.date} | Nhập: ${n(d['Nhập'] || 0)} | Xuất: ${n(d['Xuất'] || 0)}`}
              >
                <div className="bars">
                  <span className="in" style={{ height: `${Math.max(8, ((d['Nhập'] || 0) / max) * 150)}px` }}></span>
                  <span className="out" style={{ height: `${Math.max(8, ((d['Xuất'] || 0) / max) * 150)}px` }}></span>
                </div>
                <small>{d.date.slice(5)}</small>
              </button>
            ))}
          </div>
          {activePoint && (
            <div className="chart-info">
              <b>Ngày {activePoint.date}</b>
              <span>Nhập: {n(activePoint['Nhập'] || 0)} sản phẩm</span>
              <span>Xuất/điều chuyển/hủy: {n(activePoint['Xuất'] || 0)} sản phẩm</span>
            </div>
          )}
        </>
      ) : <Empty text="Chưa có dữ liệu nhập/xuất." />}
      <div className="legend"><span className="dot in"></span>Nhập hàng <span className="dot out"></span>Xuất/điều chuyển/hủy</div>
    </div>
  );
}

function AiAnswer({ answer }) {
  return (
    <div className="ai-answer">
      <div className="ai-summary">
        <h3>Tóm tắt</h3>
        <p>{answer.summary}</p>
        <p><b>Hành động đề xuất:</b> {answer.suggested_action}</p>
      </div>
      <div className="ai-sections">
        <AIList title="Nhóm cần nhập" items={answer.need_restock} empty="Không có sản phẩm cần nhập trong phạm vi hỏi." mode="need" />
        <AIList title="Dư tồn / bán chậm" items={answer.transfer_or_promotion} empty="Không có nhóm dư tồn/bán chậm trong phạm vi hỏi." mode="transfer" />
        <AIList title="Giá trị tồn kho cao" items={answer.high_inventory_value} empty="Chưa có dữ liệu giá trị tồn kho cao." mode="value" />
      </div>
      <small>{answer.management_note}</small>
      <div className={`ai-source ${answer.generation_status === 'LIVE' ? 'live' : 'fallback'}`}>
        Nguồn phản hồi: {answer.generation_status === 'LIVE' ? `Gemini · ${answer.model_name}` : 'Dữ liệu SQL · phản hồi dự phòng'}
      </div>
    </div>
  );
}

function AIList({ title, items = [], empty, mode }) {
  return (
    <div className="ai-section">
      <h3>{title}</h3>
      {items.length ? items.map((x) => (
        <div className="ai-row" key={`${mode}-${x.product_id}`}>
          <b>{x.product_id} - {x.product_name}</b>
          <span><Badge value={x.status} /> Tồn {n(x.stock_on_hand)} · ROP {n(x.reorder_point)} · Dự báo 7 ngày {n(x.forecast_7_days)}</span>
          <span>Đề xuất nhập {n(x.proposed_quantity)} · Điều chuyển {n(x.transfer_quantity)}</span>
        </div>
      )) : <p className="muted">{empty}</p>}
    </div>
  );
}


function NotificationCard({ item }) {
  const lines = splitMessageLines(item.message);
  return (
    <div className="notification-card timeline">
      <div className="notification-head">
        <div>
          <b>{item.notification_type === 'SUMMARY' ? 'Báo cáo tổng hợp' : `Thông báo sản phẩm ${item.product_id || ''}`}</b>
          <div className="muted small-line">{item.created_at}</div>
        </div>
        <span className={`status-pill ${String(item.send_status || '').toLowerCase()}`}>{formatSendStatus(item.send_status)}</span>
      </div>
      <div className="notification-body">
        {lines.slice(0, 6).map((line, index) => <p key={index}>{line}</p>)}
      </div>
    </div>
  );
}

function DemandChart({ items = [] }) {
  const [active, setActive] = useState(items?.[items.length - 1] || null);

  useEffect(() => {
    setActive(items?.[items.length - 1] || null);
  }, [items]);

  if (!items.length) return <Empty text="Chưa có dữ liệu nhu cầu gần đây." />;

  const max = Math.max(1, ...items.map((d) => d.net_demand || 0));

  return (
    <>
      <div className="mini-chart demand-chart">
        {items.map((d) => (
          <button
            type="button"
            key={d.demand_date}
            className={`demand-bar ${active?.demand_date === d.demand_date ? 'active' : ''}`}
            onMouseEnter={() => setActive(d)}
            onFocus={() => setActive(d)}
            onClick={() => setActive(d)}
            title={`${d.demand_date}: ${n(d.net_demand)} sản phẩm`}
          >
            <span style={{ height: `${Math.max(8, ((d.net_demand || 0) / max) * 120)}px` }}></span>
            <small>{String(d.demand_date).slice(5)}</small>
          </button>
        ))}
      </div>
      {active && <div className="chart-info"><b>{active.demand_date}</b><span>Nhu cầu ròng: {n(active.net_demand)} sản phẩm</span></div>}
    </>
  );
}

function Approval({ recs, status, setStatus, internalStatus, setInternalStatus, refresh, chooseProduct, setMessage }) {
  async function decide(id, decision) {
    const finalRaw = prompt('Số lượng duyệt/điều chỉnh. Để trống nếu dùng số lượng hệ thống:', '');
    const reason = prompt('Lý do xử lý:', decision === 'REJECT' ? 'Không thực hiện kỳ này' : 'Đã kiểm tra tình hình thực tế') || '';
    await processDecision(id, { decision, final_quantity: finalRaw === '' ? null : Number(finalRaw), reason, processed_by: 'Quản lý kho' });
    setMessage('Đã cập nhật quyết định xử lý và lưu lại số lượng cuối cùng.');
    refresh(recs.page);
  }

  async function send(id) {
    const result = await sendRecommendation(id);
    setMessage(noticeForSendStatus(result.send_status, 'thông báo chi tiết'));
    refresh(recs.page);
  }

  return (
    <section className="card">
      <h2>Xử lý đề xuất</h2>
      <p className="muted">Có bộ lọc, phân trang và hiển thị rõ số lượng nhập/điều chuyển trước khi gửi thông báo.</p>
      <div className="filters">
        <label>Tình trạng<select value={status} onChange={(e) => setStatus(e.target.value)}>{statuses.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>Xử lý nội bộ<select value={internalStatus} onChange={(e) => setInternalStatus(e.target.value)}>{internalStatuses.map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <div className="approval-list">
        {recs.items.map((r) => (
          <div className={`approval-card ${statusClass[r.business_status] || ''}`} key={r.recommendation_id}>
            <div>
              <b>{r.product_id} - {r.product_name}</b> <Badge value={r.business_status} />
              <p>{r.trigger_reason}</p>
              <p><b>Phương án:</b> {r.action_strategy}</p>
              <p><b>Gợi ý ban đầu:</b> nhập {n(r.proposed_quantity)} · điều chuyển {n(r.transfer_quantity)}</p>
              <p><b>Số lượng quản lý chốt:</b> {n(r.final_quantity)}</p>
              <p><b>Nội bộ:</b> {r.internal_status} · <b>Thông báo:</b> {r.telegram_status}</p>
              {r.internal_reason && <p><b>Lý do:</b> {r.internal_reason}</p>}
            </div>
            <div className="actions action-column">
              <button onClick={() => chooseProduct(r.product_id, 'products')}>Xem sản phẩm</button>
              <button onClick={() => decide(r.recommendation_id, 'APPROVE')}>Duyệt</button>
              <button className="warn" onClick={() => decide(r.recommendation_id, 'ADJUST')}>Điều chỉnh</button>
              <button className="danger" onClick={() => decide(r.recommendation_id, 'REJECT')}>Hủy</button>
              <button className="telegram" onClick={() => send(r.recommendation_id)}>Gửi thông báo</button>
            </div>
          </div>
        ))}
      </div>
      {!recs.items.length && <Empty text="Không có đề xuất phù hợp bộ lọc." />}
      <Pager page={recs.page} totalPages={recs.total_pages} onPage={refresh} />
    </section>
  );
}

function Stock({ products, selected, chooseProduct, journey, refresh, setMessage }) {
  const current = products.find((p) => p.product_id === selected) || {};

  async function submit(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const result = await createVoucher({
      product_id: form.get('product_id'),
      voucher_type: form.get('voucher_type'),
      movement_direction: form.get('movement_direction'),
      quantity: Number(form.get('quantity')),
      unit_price: Number(form.get('unit_price') || 0),
      price_note: form.get('price_note') || '',
      reason: form.get('reason') || '',
      recorded_by: form.get('recorded_by') || 'Nhân viên kho',
    });
    setMessage(`${result.voucher_type}: ${result.product_name}, số lượng ${result.quantity}, tồn ${result.stock_before} → ${result.stock_after}.`);
    await refresh();
    await chooseProduct(result.product_id);
  }

  return (
    <section className="grid two">
      <div className="card">
        <h2>Nhập hàng / Xuất hàng</h2>
        <form className="form" onSubmit={submit}>
          <label>Sản phẩm<select name="product_id" value={selected} onChange={(e) => chooseProduct(e.target.value)}>{products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_id} - {p.product_name}</option>)}</select></label>
          <div className="hint">Giá nhập {n(current.purchase_price)}đ · Giá bán {n(current.unit_price)}đ</div>
          <label>Loại phiếu<select name="voucher_type">{voucherTypes.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>Hướng xử lý<select name="movement_direction"><option value="IN">Tăng tồn kho</option><option value="OUT">Giảm/điều chuyển khỏi kho</option></select></label>
          <label>Số lượng<input name="quantity" type="number" min="1" defaultValue="5" /></label>
          <label>Đơn giá thực tế<input name="unit_price" type="number" min="0" defaultValue={current.purchase_price || 0} /></label>
          <label>Ghi chú giá<input name="price_note" defaultValue="Theo giá thực tế tại thời điểm lập phiếu" /></label>
          <label>Người ghi nhận<input name="recorded_by" defaultValue="Nhân viên kho" /></label>
          <label>Lý do<input name="reason" defaultValue="Cập nhật phiếu kho" /></label>
          <button>Lưu phiếu kho</button>
        </form>
      </div>
      <div className="card">
        <h2>Giao dịch gần nhất</h2>
        {journey?.transactions?.length ? journey.transactions.map((tx) => (
          <div className="timeline" key={tx.transaction_id}>
            <b>{tx.voucher_type}</b> · {tx.quantity} SP
            <p>{tx.stock_before} → {tx.stock_after} · đơn giá {n(tx.unit_price)}đ · thành tiền {n(tx.total_amount)}đ</p>
            <small>{tx.recorded_by} · {tx.transaction_date}</small>
          </div>
        )) : <Empty />}
      </div>
    </section>
  );
}

function Products({ products, selected, chooseProduct, journey, status, setStatus, refresh, setMessage }) {
  const [category, setCategory] = useState('Tất cả');
  const [supplier, setSupplier] = useState('Tất cả');
  const [activeState, setActiveState] = useState('Tất cả');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const pageSize = 8;
  const categories = ['Tất cả', ...Array.from(new Set(products.map((p) => p.category))).sort()];
  const suppliers = ['Tất cả', ...Array.from(new Set(products.map((p) => p.supplier_name))).sort()];
  const filtered = products.filter((p) => (
    (status === 'Tất cả' || p.business_status === status) &&
    (category === 'Tất cả' || p.category === category) &&
    (supplier === 'Tất cả' || p.supplier_name === supplier) &&
    (activeState === 'Tất cả' || (activeState === 'Đang kinh doanh' ? p.is_active !== 0 : p.is_active === 0))
  ));
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visible = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const rec = journey?.recommendation;
  const product = journey?.product;

  useEffect(() => { setEditing(false); }, [product?.product_id]);

  async function submitEdit(e) {
    e.preventDefault();
    if (!product) return;
    const form = new FormData(e.currentTarget);
    setSaving(true);
    try {
      await updateProduct(product.product_id, {
        product_name: String(form.get('product_name') || '').trim(),
        category: String(form.get('category') || '').trim(),
        supplier_name: String(form.get('supplier_name') || '').trim(),
        unit: String(form.get('unit') || '').trim(),
        purchase_price: Number(form.get('purchase_price') || 0),
        unit_price: Number(form.get('unit_price') || 0),
        lead_time_days: Number(form.get('lead_time_days') || 0),
        safety_stock: Number(form.get('safety_stock') || 0),
        minimum_stock: Number(form.get('minimum_stock') || 0),
        reorder_point: Number(form.get('reorder_point') || 0),
        branch_name: String(form.get('branch_name') || '').trim(),
        is_active: Number(form.get('is_active')),
      });
      setMessage(`Đã cập nhật sản phẩm ${product.product_id}.`);
      setEditing(false);
      await refresh();
      await chooseProduct(product.product_id);
    } catch (err) {
      setMessage(err.message);
    }
    setSaving(false);
  }

  async function removeProduct() {
    if (!product) return;
    const accepted = window.confirm(
      `Xóa sản phẩm ${product.product_id} - ${product.product_name}?\n\n` +
      'Sản phẩm sẽ chuyển sang trạng thái ngừng kinh doanh để bảo toàn lịch sử giao dịch.'
    );
    if (!accepted) return;

    setSaving(true);
    try {
      const result = await deleteProduct(product.product_id);
      const next = products.find((p) => p.product_id !== product.product_id && p.is_active !== 0);
      setMessage(result.message);
      setEditing(false);
      setActiveState('Đang kinh doanh');
      setPage(1);
      await refresh();
      if (next) await chooseProduct(next.product_id);
    } catch (err) {
      setMessage(err.message);
    }
    setSaving(false);
  }

  return (
    <section className="grid two">
      <div className="card">
        <h2>Danh sách sản phẩm</h2>
        <div className="filters product-filters">
          <label>Trạng thái<select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>{statuses.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>Danh mục<select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>{categories.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>Nhà cung cấp<select value={supplier} onChange={(e) => { setSupplier(e.target.value); setPage(1); }}>{suppliers.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>Kinh doanh<select value={activeState} onChange={(e) => { setActiveState(e.target.value); setPage(1); }}><option>Tất cả</option><option>Đang kinh doanh</option><option>Ngừng kinh doanh</option></select></label>
        </div>
        {visible.map((p) => (
          <button className={`product-row ${selected === p.product_id ? 'selected' : ''} ${statusClass[p.business_status] || ''} ${p.is_active === 0 ? 'inactive' : ''}`} key={p.product_id} onClick={() => chooseProduct(p.product_id)}>
            <b>{p.product_id}</b><span>{p.product_name}</span><small>{p.category} · {p.supplier_name} · tồn {n(p.stock_on_hand)} · <Badge value={p.business_status} /> {p.is_active === 0 && <em>Ngừng kinh doanh</em>}</small>
          </button>
        ))}
        {!filtered.length && <Empty text="Không có sản phẩm phù hợp." />}
        <Pager page={currentPage} totalPages={totalPages} onPage={setPage} />
      </div>

      <div className="card">
        <div className="product-detail-heading">
          <h2>Chi tiết sản phẩm</h2>
          {product && (
            <div className="product-detail-actions">
              <button type="button" onClick={() => setEditing((value) => !value)} disabled={saving}>{editing ? 'Đóng sửa' : 'Sửa'}</button>
              <button type="button" className="danger" onClick={removeProduct} disabled={saving || product.is_active === 0}>Xóa</button>
            </div>
          )}
        </div>
        {product ? (
          <>
            <div className="product-title">{product.product_id} - {product.product_name}</div>
            {product.is_active === 0 && <div className="inactive-notice">Sản phẩm đã ngừng kinh doanh. Lịch sử giao dịch vẫn được giữ lại.</div>}

            {editing && (
              <form className="product-edit-form" onSubmit={submitEdit}>
                <div className="edit-grid">
                  <label>Tên sản phẩm<input name="product_name" defaultValue={product.product_name} required /></label>
                  <label>Danh mục<input name="category" defaultValue={product.category} /></label>
                  <label>Nhà cung cấp<input name="supplier_name" defaultValue={product.supplier_name} /></label>
                  <label>Đơn vị tính<input name="unit" defaultValue={product.unit || 'SP'} /></label>
                  <label>Giá nhập<input name="purchase_price" type="number" min="0" step="1" defaultValue={product.purchase_price} /></label>
                  <label>Giá bán<input name="unit_price" type="number" min="0" step="1" defaultValue={product.unit_price} /></label>
                  <label>Thời gian chờ (ngày)<input name="lead_time_days" type="number" min="0" defaultValue={product.lead_time_days} /></label>
                  <label>Tồn kho an toàn<input name="safety_stock" type="number" min="0" defaultValue={product.safety_stock} /></label>
                  <label>Tồn kho tối thiểu<input name="minimum_stock" type="number" min="0" defaultValue={product.minimum_stock} /></label>
                  <label>Điểm đặt hàng lại<input name="reorder_point" type="number" min="0" defaultValue={product.reorder_point} /></label>
                  <label>Chi nhánh/kho<input name="branch_name" defaultValue={product.branch_name || ''} /></label>
                  <label>Trạng thái kinh doanh<select name="is_active" defaultValue={String(product.is_active)}><option value="1">Đang kinh doanh</option><option value="0">Ngừng kinh doanh</option></select></label>
                </div>
                <div className="actions">
                  <button type="submit" disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu thay đổi'}</button>
                  <button type="button" className="secondary" onClick={() => setEditing(false)} disabled={saving}>Hủy</button>
                </div>
              </form>
            )}

            <div className="detail-grid">
              <span>Danh mục</span><b>{product.category}</b>
              <span>Nhà cung cấp</span><b>{product.supplier_name}</b>
              <span>Tồn kho</span><b>{n(product.stock_on_hand)}</b>
              <span>Vị thế tồn kho</span><b>{n(product.inventory_position)}</b>
              <span>Điểm đặt hàng lại</span><b>{n(product.reorder_point)}</b>
              <span>Dự báo 7 ngày</span><b>{n(product.forecast_7_days)}</b>
              <span>Giá nhập</span><b>{n(product.purchase_price)}đ</b>
              <span>Giá bán</span><b>{n(product.unit_price)}đ</b>
              <span>Lãi gộp/SP</span><b>{n(product.gross_margin)}đ</b>
              <span>Trạng thái</span><Badge value={product.business_status} />
            </div>
            {rec && <div className="management-box"><h3>Đề xuất xử lý</h3><p>{rec.trigger_reason}</p><p><b>Phương án hiện hành:</b> {rec.effective_action_strategy || rec.action_strategy}</p><p><b>Gợi ý ban đầu:</b> nhập {n(rec.proposed_quantity)} · điều chuyển {n(rec.transfer_quantity)}</p><p><b>Số lượng quản lý chốt:</b> {n(rec.final_quantity)}</p></div>}
            <h3>Nhu cầu gần đây</h3>
            <DemandChart items={journey.demand_history} />
            <h3>Lịch sử nhập/xuất gần nhất</h3>
            {journey.transactions?.length ? journey.transactions.slice(0, 8).map((tx) => (
              <div className="timeline" key={tx.transaction_id}>
                <b>{tx.voucher_type}</b> · {tx.quantity} SP
                <p>{tx.stock_before} → {tx.stock_after} · đơn giá {n(tx.unit_price)}đ · thành tiền {n(tx.total_amount)}đ</p>
                <small>{tx.recorded_by} · {tx.transaction_date}</small>
              </div>
            )) : <Empty text="Chưa có lịch sử nhập/xuất." />}
          </>
        ) : <Empty />}
      </div>
    </section>
  );
}

function Excel({ imports, setImports, refresh, setMessage }) {
  const [fileSearch, setFileSearch] = useState('');
  const [selectedImport, setSelectedImport] = useState(null);

  async function loadImports(page = 1) {
    setImports(await getImports({ search: fileSearch, page, page_size: 6 }));
  }

  async function submit(e) {
    e.preventDefault();
    const file = e.currentTarget.elements.excel_file.files[0];
    const uploadedBy = e.currentTarget.elements.uploaded_by.value || 'Nhân viên kho';
    if (!file) {
      setMessage('Vui lòng chọn file Excel.');
      return;
    }
    const result = await uploadExcel(file, uploadedBy);
    setMessage(`Đã nhập ${result.file_name}: ${result.valid_rows} dòng hợp lệ, ${result.error_rows} dòng lỗi.`);
    setSelectedImport(result);
    await loadImports();
    await refresh();
  }

  async function detail(id) {
    setSelectedImport(await getImportDetail(id));
  }

  return (
    <section className="excel-page">
      <div className="card excel-upload-card">
        <div>
          <h2>Nhập file Excel</h2>
          <p className="muted">Upload phiếu kho theo mẫu. Hệ thống kiểm tra dòng hợp lệ/lỗi và lưu lịch sử nhập file.</p>
        </div>
        <a className="button-link" href={templateUrl}>Tải mẫu Excel</a>
        <form className="form excel-form" onSubmit={submit}>
          <label>Người nhập<input name="uploaded_by" defaultValue="Nhân viên kho" /></label>
          <label>File Excel<input name="excel_file" type="file" accept=".xlsx" /></label>
          <button>Upload và xử lý</button>
        </form>
      </div>

      <div className="card">
        <div className="section-title compact-title">
          <div>
            <h2>Lịch sử nhập file</h2>
            <p className="muted">Bấm vào từng file để xem chi tiết các dòng đã nhập.</p>
          </div>
          <form className="inline-search" onSubmit={(e) => { e.preventDefault(); loadImports(1); }}>
            <input value={fileSearch} onChange={(e) => setFileSearch(e.target.value)} placeholder="Tìm tên file, người nhập, trạng thái..." />
            <button>Tìm</button>
          </form>
        </div>
        <div className="file-list">
          {imports.items.map((item) => (
            <button className={`file-card ${selectedImport?.import_id === item.import_id ? 'selected' : ''}`} key={item.import_id} onClick={() => detail(item.import_id)}>
              <div>
                <b>{item.file_name}</b>
                <span>{item.import_date} · {item.uploaded_by}</span>
              </div>
              <div className="file-stats">
                <span>Hợp lệ <b>{item.valid_rows}</b></span>
                <span>Lỗi <b>{item.error_rows}</b></span>
                <span className="status-pill">{item.status}</span>
              </div>
            </button>
          ))}
        </div>
        {!imports.items.length && <Empty text="Chưa có lịch sử nhập file phù hợp." />}
        <Pager page={imports.page} totalPages={imports.total_pages} onPage={loadImports} />
      </div>

      {selectedImport && <div className="card"><ImportDetail data={selectedImport} /></div>}
    </section>
  );
}

function ImportDetail({ data }) {
  return (
    <div className="import-detail">
      <h2>Chi tiết file: {data.file_name}</h2>
      <p className="muted">Người nhập: {data.uploaded_by} · Hợp lệ: {data.valid_rows} · Lỗi: {data.error_rows}</p>
      {data.rows?.length ? (
        <div className="table-wrap small-table">
          <table>
            <thead>
              <tr><th>Dòng</th><th>Ngày chứng từ</th><th>Mã SP</th><th>Tên sản phẩm</th><th>Loại phiếu</th><th>SL</th><th>Đơn giá</th><th>Trạng thái</th><th>Lỗi/Ghi chú</th></tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.row_id}>
                  <td>{r.row_number}</td><td>{r.document_date}</td><td>{r.product_id}</td><td>{r.product_name}</td><td>{r.voucher_type}</td><td>{r.quantity}</td><td>{n(r.unit_price)}</td><td>{r.row_status}</td><td>{r.error_message || r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty text="File này chưa có dòng chi tiết." />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
