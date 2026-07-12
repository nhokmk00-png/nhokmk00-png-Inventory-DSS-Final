CREATE DATABASE IF NOT EXISTS inventory_dss CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE inventory_dss;
CREATE TABLE products (
  product_id VARCHAR(20) NOT NULL,
  product_name VARCHAR(255) NOT NULL,
  category VARCHAR(100) NOT NULL,
  supplier_name VARCHAR(255) NOT NULL,
  unit VARCHAR(30) NOT NULL,
  purchase_price DECIMAL(18, 2) NOT NULL,
  unit_price DECIMAL(18, 2) NOT NULL,
  lead_time_days INT NOT NULL,
  safety_stock INT NOT NULL,
  minimum_stock INT NOT NULL,
  reorder_point INT NOT NULL,
  branch_name VARCHAR(255) NOT NULL,
  is_active INT NOT NULL,
  stock_on_hand INT NOT NULL,
  reserved_quantity INT NOT NULL,
  inbound_quantity INT NOT NULL,
  avg_daily_demand FLOAT NOT NULL,
  forecast_7_days FLOAT NOT NULL,
  business_status VARCHAR(50) NOT NULL,
  created_at VARCHAR(30) NOT NULL,
  updated_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_products_product_name ON products (product_name);
CREATE INDEX ix_products_category ON products (category);
CREATE INDEX ix_products_supplier_name ON products (supplier_name);
CREATE INDEX ix_products_is_active ON products (is_active);
CREATE INDEX ix_products_business_status ON products (business_status);
CREATE TABLE users (
  user_id INT NOT NULL AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL,
  password_hash VARCHAR(128) NOT NULL,
  role VARCHAR(50) NOT NULL,
  created_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (user_id),
  CONSTRAINT uq_users_username UNIQUE (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE TABLE inventory (
  product_id VARCHAR(20) NOT NULL,
  stock_on_hand INT NOT NULL,
  reserved_quantity INT NOT NULL,
  confirmed_inbound_quantity INT NOT NULL,
  updated_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (product_id),
  CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE TABLE inventory_transactions (
  transaction_id INT NOT NULL AUTO_INCREMENT,
  product_id VARCHAR(20) NOT NULL,
  transaction_date VARCHAR(30) NOT NULL,
  voucher_type VARCHAR(100) NOT NULL,
  transaction_type VARCHAR(50) NOT NULL,
  movement_direction VARCHAR(10) NOT NULL,
  quantity INT NOT NULL,
  unit_price DECIMAL(18, 2) NOT NULL,
  total_amount DECIMAL(18, 2) NOT NULL,
  stock_before INT NOT NULL,
  stock_after INT NOT NULL,
  recorded_by VARCHAR(120) NOT NULL,
  price_note TEXT NOT NULL,
  note TEXT NOT NULL,
  PRIMARY KEY (transaction_id),
  CONSTRAINT fk_inventory_transactions_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_inventory_transactions_product_id ON inventory_transactions (product_id);
CREATE INDEX ix_inventory_transactions_transaction_date ON inventory_transactions (transaction_date);
CREATE TABLE daily_demand (
  demand_id INT NOT NULL AUTO_INCREMENT,
  demand_date VARCHAR(20) NOT NULL,
  product_id VARCHAR(20) NOT NULL,
  net_demand INT NOT NULL,
  promotion_flag INT NOT NULL,
  PRIMARY KEY (demand_id),
  CONSTRAINT uq_daily_demand_date_product UNIQUE (demand_date, product_id),
  CONSTRAINT fk_daily_demand_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_daily_demand_demand_date ON daily_demand (demand_date);
CREATE INDEX ix_daily_demand_product_id ON daily_demand (product_id);
CREATE TABLE forecasts (
  forecast_id INT NOT NULL AUTO_INCREMENT,
  batch_id VARCHAR(100) NOT NULL,
  forecast_date VARCHAR(20) NOT NULL,
  product_id VARCHAR(20) NOT NULL,
  forecast_quantity_7_days FLOAT NOT NULL,
  average_daily_demand FLOAT NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  mae FLOAT NULL,
  wape FLOAT NULL,
  created_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (forecast_id),
  CONSTRAINT uq_forecast_batch_product UNIQUE (batch_id, product_id),
  CONSTRAINT fk_forecasts_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_forecasts_product_id ON forecasts (product_id);
CREATE TABLE recommendations (
  recommendation_id INT NOT NULL AUTO_INCREMENT,
  forecast_id INT NULL,
  product_id VARCHAR(20) NOT NULL,
  business_status VARCHAR(50) NOT NULL,
  recommendation_type VARCHAR(50) NOT NULL,
  priority_rank INT NOT NULL,
  available_stock FLOAT NOT NULL,
  inventory_position FLOAT NOT NULL,
  reorder_point FLOAT NOT NULL,
  target_stock FLOAT NOT NULL,
  trigger_reason TEXT NOT NULL,
  action_strategy TEXT NOT NULL,
  proposed_quantity INT NOT NULL,
  transfer_quantity INT NOT NULL,
  final_quantity INT NOT NULL,
  internal_status VARCHAR(50) NOT NULL,
  telegram_status VARCHAR(50) NOT NULL,
  processed_by VARCHAR(120) NOT NULL,
  internal_reason TEXT NOT NULL,
  created_at VARCHAR(30) NOT NULL,
  updated_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (recommendation_id),
  CONSTRAINT fk_recommendations_forecast FOREIGN KEY (forecast_id) REFERENCES forecasts (forecast_id),
  CONSTRAINT fk_recommendations_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_recommendations_forecast_id ON recommendations (forecast_id);
CREATE INDEX ix_recommendations_product_id ON recommendations (product_id);
CREATE INDEX ix_recommendations_business_status ON recommendations (business_status);
CREATE INDEX ix_recommendations_internal_status ON recommendations (internal_status);
CREATE INDEX ix_recommendations_telegram_status ON recommendations (telegram_status);
CREATE TABLE ai_insights (
  insight_id INT NOT NULL AUTO_INCREMENT,
  recommendation_id INT NOT NULL,
  summary TEXT NOT NULL,
  reason TEXT NOT NULL,
  suggested_action TEXT NOT NULL,
  management_note TEXT NOT NULL,
  generation_status VARCHAR(30) NOT NULL,
  error_message TEXT NOT NULL,
  created_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (insight_id),
  CONSTRAINT fk_ai_insights_recommendation FOREIGN KEY (recommendation_id) REFERENCES recommendations (recommendation_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_ai_insights_recommendation_id ON ai_insights (recommendation_id);
CREATE TABLE ai_messages (
  ai_log_id INT NOT NULL AUTO_INCREMENT,
  product_id VARCHAR(20) NULL,
  question TEXT NOT NULL,
  answer_json TEXT NOT NULL,
  generation_status VARCHAR(30) NOT NULL,
  created_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (ai_log_id),
  CONSTRAINT fk_ai_messages_product FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_ai_messages_product_id ON ai_messages (product_id);
CREATE TABLE alerts (
  alert_id INT NOT NULL AUTO_INCREMENT,
  product_id VARCHAR(20) NOT NULL,
  recommendation_id INT NOT NULL,
  notification_type VARCHAR(50) NOT NULL,
  product_name_snapshot VARCHAR(255) NOT NULL,
  business_status_snapshot VARCHAR(50) NOT NULL,
  message TEXT NOT NULL,
  send_status VARCHAR(50) NOT NULL,
  sent_at VARCHAR(30) NOT NULL,
  error_message TEXT NOT NULL,
  created_at VARCHAR(30) NOT NULL,
  PRIMARY KEY (alert_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_alerts_product_id ON alerts (product_id);
CREATE INDEX ix_alerts_recommendation_id ON alerts (recommendation_id);
CREATE TABLE excel_imports (
  import_id INT NOT NULL AUTO_INCREMENT,
  import_date VARCHAR(30) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  uploaded_by VARCHAR(120) NOT NULL,
  valid_rows INT NOT NULL,
  error_rows INT NOT NULL,
  status VARCHAR(50) NOT NULL,
  note TEXT NOT NULL,
  PRIMARY KEY (import_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_excel_imports_import_date ON excel_imports (import_date);
CREATE TABLE excel_import_rows (
  row_id INT NOT NULL AUTO_INCREMENT,
  import_id INT NOT NULL,
  row_number INT NOT NULL,
  document_date VARCHAR(30) NOT NULL,
  voucher_type VARCHAR(100) NOT NULL,
  product_id VARCHAR(20) NOT NULL,
  product_name VARCHAR(255) NOT NULL,
  quantity INT NOT NULL,
  unit_price FLOAT NOT NULL,
  uploaded_by VARCHAR(120) NOT NULL,
  note TEXT NOT NULL,
  row_status VARCHAR(50) NOT NULL,
  error_message TEXT NOT NULL,
  PRIMARY KEY (row_id),
  CONSTRAINT fk_excel_import_rows_import FOREIGN KEY (import_id) REFERENCES excel_imports (import_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
CREATE INDEX ix_excel_import_rows_import_id ON excel_import_rows (import_id);