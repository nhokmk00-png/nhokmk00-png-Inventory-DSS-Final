PRAGMA foreign_keys = ON;
PRAGMA user_version = 6;

DROP TABLE IF EXISTS excel_import_rows;
DROP TABLE IF EXISTS excel_imports;
DROP TABLE IF EXISTS telegram_responses;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS ai_messages;
DROP TABLE IF EXISTS ai_insights;
DROP TABLE IF EXISTS inventory_transactions;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS forecasts;
DROP TABLE IF EXISTS daily_demand;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS products;

CREATE TABLE products (
  product_id TEXT PRIMARY KEY,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL,
  supplier_name TEXT NOT NULL,
  unit TEXT NOT NULL DEFAULT 'cái',
  unit_price REAL NOT NULL CHECK(unit_price >= 0),
  purchase_price REAL NOT NULL DEFAULT 0 CHECK(purchase_price >= 0),
  lead_time_days INTEGER NOT NULL CHECK(lead_time_days >= 1),
  safety_stock INTEGER NOT NULL CHECK(safety_stock >= 0),
  minimum_stock INTEGER NOT NULL CHECK(minimum_stock >= 0),
  branch_name TEXT NOT NULL DEFAULT 'Chi nhánh trung tâm',
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE inventory (
  product_id TEXT PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
  stock_on_hand INTEGER NOT NULL CHECK(stock_on_hand >= 0),
  reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK(reserved_quantity >= 0),
  confirmed_inbound_quantity INTEGER NOT NULL DEFAULT 0 CHECK(confirmed_inbound_quantity >= 0),
  updated_at TEXT NOT NULL,
  CHECK(reserved_quantity <= stock_on_hand)
);

CREATE TABLE inventory_transactions (
  transaction_id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  transaction_type TEXT NOT NULL CHECK(transaction_type IN ('RECEIPT','SALE_OUT','ADJUSTMENT_IN','ADJUSTMENT_OUT','TRANSFER_OUT','DISPOSE')),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  stock_before INTEGER NOT NULL,
  stock_after INTEGER NOT NULL,
  voucher_type TEXT NOT NULL,
  unit_price REAL NOT NULL DEFAULT 0 CHECK(unit_price >= 0),
  total_amount REAL NOT NULL DEFAULT 0 CHECK(total_amount >= 0),
  price_note TEXT,
  note TEXT,
  recorded_by TEXT NOT NULL,
  transaction_date TEXT NOT NULL
);

CREATE TABLE daily_demand (
  demand_id TEXT PRIMARY KEY,
  demand_date TEXT NOT NULL,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  net_demand INTEGER NOT NULL CHECK(net_demand >= 0),
  promotion_flag INTEGER NOT NULL DEFAULT 0,
  UNIQUE(demand_date, product_id)
);

CREATE TABLE forecasts (
  forecast_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL,
  forecast_date TEXT NOT NULL,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  forecast_quantity_7_days REAL NOT NULL CHECK(forecast_quantity_7_days >= 0),
  average_daily_demand REAL NOT NULL CHECK(average_daily_demand >= 0),
  model_name TEXT NOT NULL,
  mae REAL,
  wape REAL,
  created_at TEXT NOT NULL,
  UNIQUE(batch_id, product_id)
);

CREATE TABLE recommendations (
  recommendation_id TEXT PRIMARY KEY,
  forecast_id TEXT NOT NULL UNIQUE REFERENCES forecasts(forecast_id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  recommendation_type TEXT NOT NULL CHECK(recommendation_type IN ('RESTOCK','OVERSTOCK','SLOW_MOVING','MONITOR','NORMAL')),
  business_status TEXT NOT NULL CHECK(business_status IN ('Nguy cấp','Cần nhập','Dư tồn','Bán chậm','Theo dõi','An toàn')),
  priority_rank INTEGER NOT NULL,
  available_stock REAL NOT NULL,
  inventory_position REAL NOT NULL,
  reorder_point REAL NOT NULL,
  target_stock REAL NOT NULL,
  proposed_quantity INTEGER NOT NULL DEFAULT 0 CHECK(proposed_quantity >= 0),
  final_quantity INTEGER,
  action_strategy TEXT NOT NULL,
  trigger_reason TEXT NOT NULL,
  internal_status TEXT NOT NULL DEFAULT 'Chờ xử lý' CHECK(internal_status IN ('Chờ xử lý','Đã duyệt','Đã điều chỉnh','Đã hủy')),
  internal_reason TEXT,
  processed_by TEXT,
  processed_at TEXT,
  telegram_status TEXT NOT NULL DEFAULT 'Chưa gửi' CHECK(telegram_status IN ('Chưa gửi','Đã gửi','Bỏ qua','Lỗi')),
  boss_status TEXT NOT NULL DEFAULT 'Không áp dụng' CHECK(boss_status IN ('Không áp dụng','Không gửi')),
  boss_final_quantity INTEGER,
  boss_reason TEXT,
  boss_responded_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE ai_insights (
  insight_id TEXT PRIMARY KEY,
  recommendation_id TEXT NOT NULL REFERENCES recommendations(recommendation_id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  reason TEXT NOT NULL,
  suggested_action TEXT NOT NULL,
  management_note TEXT NOT NULL,
  generation_status TEXT NOT NULL CHECK(generation_status IN ('SUCCESS','FALLBACK','FAILED')),
  error_message TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE ai_messages (
  message_id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(product_id),
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  generation_status TEXT NOT NULL CHECK(generation_status IN ('SUCCESS','FALLBACK','FAILED')),
  created_at TEXT NOT NULL
);

CREATE TABLE alerts (
  alert_id TEXT PRIMARY KEY,
  alert_type TEXT NOT NULL CHECK(alert_type IN ('APPROVAL','SUMMARY','MANUAL')),
  recommendation_id TEXT REFERENCES recommendations(recommendation_id),
  product_id TEXT REFERENCES products(product_id),
  product_name_snapshot TEXT,
  business_status_snapshot TEXT,
  message TEXT NOT NULL,
  send_status TEXT NOT NULL CHECK(send_status IN ('SENT','SKIPPED','FAILED')),
  sent_at TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE telegram_responses (
  response_id TEXT PRIMARY KEY,
  recommendation_id TEXT NOT NULL REFERENCES recommendations(recommendation_id) ON DELETE CASCADE,
  action TEXT NOT NULL CHECK(action IN ('APPROVE','ADJUST','REJECT')),
  final_quantity INTEGER,
  reason TEXT,
  responded_by TEXT NOT NULL,
  responded_at TEXT NOT NULL
);

CREATE TABLE excel_imports (
  import_id TEXT PRIMARY KEY,
  import_date TEXT NOT NULL,
  file_name TEXT NOT NULL,
  uploaded_by TEXT NOT NULL,
  valid_rows INTEGER NOT NULL DEFAULT 0 CHECK(valid_rows >= 0),
  error_rows INTEGER NOT NULL DEFAULT 0 CHECK(error_rows >= 0),
  status TEXT NOT NULL CHECK(status IN ('Đã nhập','Có lỗi','Chờ kiểm tra')),
  note TEXT
);

CREATE TABLE excel_import_rows (
  row_id TEXT PRIMARY KEY,
  import_id TEXT NOT NULL REFERENCES excel_imports(import_id) ON DELETE CASCADE,
  product_id TEXT,
  product_name TEXT,
  voucher_type TEXT,
  quantity INTEGER,
  row_status TEXT NOT NULL CHECK(row_status IN ('Hợp lệ','Lỗi')),
  error_message TEXT
);

CREATE INDEX idx_products_search ON products(product_id, product_name, category);
CREATE INDEX idx_recommendations_priority ON recommendations(priority_rank, proposed_quantity DESC);
CREATE INDEX idx_transactions_day ON inventory_transactions(transaction_date DESC);
CREATE INDEX idx_transactions_product ON inventory_transactions(product_id, transaction_date DESC);
CREATE INDEX idx_alerts_created ON alerts(created_at DESC);
