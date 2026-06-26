-- SQL Server schema draft for Inventory DSS V4.
-- Dùng khi triển khai lên SQL Server thật. Bản demo local dùng SQLite để chạy nhanh và ổn định.
CREATE TABLE products (
  product_id NVARCHAR(20) PRIMARY KEY,
  product_name NVARCHAR(255) NOT NULL,
  category NVARCHAR(100) NOT NULL,
  supplier_name NVARCHAR(255) NOT NULL,
  unit NVARCHAR(30) NOT NULL DEFAULT N'cái',
  unit_price DECIMAL(18,2) NOT NULL CHECK(unit_price >= 0),
  purchase_price DECIMAL(18,2) NOT NULL DEFAULT 0 CHECK(purchase_price >= 0),
  lead_time_days INT NOT NULL CHECK(lead_time_days >= 1),
  safety_stock INT NOT NULL CHECK(safety_stock >= 0),
  minimum_stock INT NOT NULL CHECK(minimum_stock >= 0),
  branch_name NVARCHAR(255) NOT NULL DEFAULT N'Chi nhánh trung tâm',
  is_active BIT NOT NULL DEFAULT 1
);

CREATE TABLE inventory (
  product_id NVARCHAR(20) PRIMARY KEY FOREIGN KEY REFERENCES products(product_id),
  stock_on_hand INT NOT NULL CHECK(stock_on_hand >= 0),
  reserved_quantity INT NOT NULL DEFAULT 0 CHECK(reserved_quantity >= 0),
  confirmed_inbound_quantity INT NOT NULL DEFAULT 0 CHECK(confirmed_inbound_quantity >= 0),
  updated_at DATETIME2 NOT NULL,
  CHECK(reserved_quantity <= stock_on_hand)
);

CREATE TABLE inventory_transactions (
  transaction_id NVARCHAR(40) PRIMARY KEY,
  product_id NVARCHAR(20) NOT NULL FOREIGN KEY REFERENCES products(product_id),
  transaction_type NVARCHAR(30) NOT NULL,
  quantity INT NOT NULL CHECK(quantity > 0),
  stock_before INT NOT NULL,
  stock_after INT NOT NULL,
  voucher_type NVARCHAR(100) NOT NULL,
  unit_price DECIMAL(18,2) NOT NULL DEFAULT 0,
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  price_note NVARCHAR(1000),
  note NVARCHAR(1000),
  recorded_by NVARCHAR(255) NOT NULL,
  transaction_date DATETIME2 NOT NULL
);

CREATE TABLE daily_demand (
  demand_id NVARCHAR(80) PRIMARY KEY,
  demand_date DATE NOT NULL,
  product_id NVARCHAR(20) NOT NULL FOREIGN KEY REFERENCES products(product_id),
  net_demand INT NOT NULL CHECK(net_demand >= 0),
  promotion_flag BIT NOT NULL DEFAULT 0,
  CONSTRAINT uq_daily_demand UNIQUE(demand_date, product_id)
);

CREATE TABLE forecasts (
  forecast_id NVARCHAR(100) PRIMARY KEY,
  batch_id NVARCHAR(100) NOT NULL,
  forecast_date DATE NOT NULL,
  product_id NVARCHAR(20) NOT NULL FOREIGN KEY REFERENCES products(product_id),
  forecast_quantity_7_days DECIMAL(18,2) NOT NULL,
  average_daily_demand DECIMAL(18,2) NOT NULL,
  model_name NVARCHAR(100) NOT NULL,
  mae DECIMAL(18,4),
  wape DECIMAL(18,4),
  created_at DATETIME2 NOT NULL,
  CONSTRAINT uq_forecasts_batch_product UNIQUE(batch_id, product_id)
);

CREATE TABLE recommendations (
  recommendation_id NVARCHAR(100) PRIMARY KEY,
  forecast_id NVARCHAR(100) NOT NULL UNIQUE FOREIGN KEY REFERENCES forecasts(forecast_id),
  product_id NVARCHAR(20) NOT NULL FOREIGN KEY REFERENCES products(product_id),
  recommendation_type NVARCHAR(30) NOT NULL,
  business_status NVARCHAR(30) NOT NULL,
  priority_rank INT NOT NULL,
  available_stock DECIMAL(18,2) NOT NULL,
  inventory_position DECIMAL(18,2) NOT NULL,
  reorder_point DECIMAL(18,2) NOT NULL,
  target_stock DECIMAL(18,2) NOT NULL,
  proposed_quantity INT NOT NULL DEFAULT 0,
  final_quantity INT,
  action_strategy NVARCHAR(2000) NOT NULL,
  trigger_reason NVARCHAR(2000) NOT NULL,
  internal_status NVARCHAR(50) NOT NULL DEFAULT N'Chờ xử lý',
  internal_reason NVARCHAR(2000),
  processed_by NVARCHAR(255),
  processed_at DATETIME2,
  telegram_status NVARCHAR(50) NOT NULL DEFAULT N'Chưa gửi',
  boss_status NVARCHAR(50) NOT NULL DEFAULT N'Chờ phản hồi',
  boss_final_quantity INT,
  boss_reason NVARCHAR(2000),
  boss_responded_at DATETIME2,
  created_at DATETIME2 NOT NULL
);

CREATE TABLE ai_insights (
  insight_id NVARCHAR(100) PRIMARY KEY,
  recommendation_id NVARCHAR(100) NOT NULL FOREIGN KEY REFERENCES recommendations(recommendation_id),
  summary NVARCHAR(1000) NOT NULL,
  reason NVARCHAR(2000) NOT NULL,
  suggested_action NVARCHAR(2000) NOT NULL,
  management_note NVARCHAR(2000) NOT NULL,
  generation_status NVARCHAR(30) NOT NULL,
  error_message NVARCHAR(1000),
  created_at DATETIME2 NOT NULL
);

CREATE TABLE alerts (
  alert_id NVARCHAR(100) PRIMARY KEY,
  alert_type NVARCHAR(30) NOT NULL,
  recommendation_id NVARCHAR(100) NULL FOREIGN KEY REFERENCES recommendations(recommendation_id),
  product_id NVARCHAR(20) NULL FOREIGN KEY REFERENCES products(product_id),
  product_name_snapshot NVARCHAR(255),
  business_status_snapshot NVARCHAR(30),
  message NVARCHAR(MAX) NOT NULL,
  send_status NVARCHAR(30) NOT NULL,
  sent_at DATETIME2,
  error_message NVARCHAR(1000),
  created_at DATETIME2 NOT NULL
);
