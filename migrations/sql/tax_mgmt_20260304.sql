-- tax management schema (field-complete per docx)
-- Note: *_enc / signature verify fields are metadata only; no keys/certs stored.

CREATE TABLE IF NOT EXISTS tax_taxpayers (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  company_id BIGINT NOT NULL,
  uscc VARCHAR(32) NOT NULL,
  taxpayer_name VARCHAR(256) NOT NULL,
  tax_authority VARCHAR(256) NOT NULL,          -- 主管税务机关 :contentReference[oaicite:17]{index=17}
  taxpayer_type VARCHAR(32) NOT NULL,           -- 一般/小规模/非居民 :contentReference[oaicite:18]{index=18}
  industry_code VARCHAR(32) NOT NULL,           -- 行业代码 :contentReference[oaicite:19]{index=19}
  vat_tax_recognition_json JSON NOT NULL,       -- 税种认定/期限 :contentReference[oaicite:20]{index=20}
  income_tax_collection_method VARCHAR(32) NOT NULL, -- 查账/核定 :contentReference[oaicite:21]{index=21}
  is_high_tech TINYINT NOT NULL DEFAULT 0,      -- 高新 :contentReference[oaicite:22]{index=22}
  is_small_profit TINYINT NOT NULL DEFAULT 0,   -- 小微 :contentReference[oaicite:23]{index=23}
  has_export_refund TINYINT NOT NULL DEFAULT 0, -- 出口退税 :contentReference[oaicite:24]{index=24}
  tax_digital_account_auth_status VARCHAR(16) NOT NULL, -- 已授权/未授权/过期 :contentReference[oaicite:25]{index=25}
  bank_tax_interaction_auth TINYINT NULL,       -- 银税互动授权 :contentReference[oaicite:26]{index=26}
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_tax_taxpayers_company (company_id),
  UNIQUE KEY uk_tax_taxpayers_uscc (uscc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 进项税发票
CREATE TABLE IF NOT EXISTS tax_vat_input_invoices (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  company_id BIGINT NOT NULL,
  invoice_uid VARCHAR(64) NOT NULL,             -- 发票唯一标识20位 :contentReference[oaicite:27]{index=27}
  invoice_code_no VARCHAR(64) NOT NULL,         -- 发票代码/号码 :contentReference[oaicite:28]{index=28}
  issue_date DATE NOT NULL,                     -- 开票日期 :contentReference[oaicite:29]{index=29}
  seller_name VARCHAR(256) NOT NULL,            -- 销售方信息 :contentReference[oaicite:30]{index=30}
  seller_tax_no VARCHAR(64) NOT NULL,
  amount_total DECIMAL(18,2) NOT NULL,          -- 价税合计 :contentReference[oaicite:31]{index=31}
  amount_excl_tax DECIMAL(18,2) NOT NULL,       -- 不含税
  tax_amount DECIMAL(18,2) NOT NULL,            -- 税额
  tax_rate DECIMAL(9,6) NOT NULL,               -- 税率/征收率 :contentReference[oaicite:32]{index=32}
  invoice_status VARCHAR(16) NOT NULL,          -- 正常/红冲/作废/失控/异常 :contentReference[oaicite:33]{index=33}
  certify_status VARCHAR(16) NOT NULL,          -- 勾选认证状态 :contentReference[oaicite:34]{index=34}
  certify_period VARCHAR(16) NULL,              -- 勾选确认所属期(YYYYMM) 系统算 :contentReference[oaicite:35]{index=35}
  usage_confirm VARCHAR(32) NOT NULL,           -- 用途确认 :contentReference[oaicite:36]{index=36}
  input_tax_transfer_reason VARCHAR(32) NULL,   -- 进项转出原因 条件必填 :contentReference[oaicite:37]{index=37}
  input_tax_transfer_amount DECIMAL(18,2) NULL, -- 进项转出金额 条件必填 :contentReference[oaicite:38]{index=38}
  xml_path VARCHAR(512) NOT NULL,               -- XML路径 :contentReference[oaicite:39]{index=39}
  risk_scan_result TEXT NULL,                   -- 风险扫描结果 系统算 :contentReference[oaicite:40]{index=40}
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_tax_vat_input_uid (company_id, invoice_uid),
  KEY idx_tax_vat_input_issue_date (company_id, issue_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 销项税发票/开票记录
CREATE TABLE IF NOT EXISTS tax_vat_output_invoices (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  company_id BIGINT NOT NULL,
  apply_no VARCHAR(64) NOT NULL,                -- 开票申请单号 :contentReference[oaicite:41]{index=41}
  buyer_name VARCHAR(256) NOT NULL,             -- 购买方信息对象 :contentReference[oaicite:42]{index=42}
  buyer_tax_no VARCHAR(64) NOT NULL,
  buyer_contact VARCHAR(64) NULL,
  tax_class_code VARCHAR(64) NOT NULL,          -- 税收分类编码 :contentReference[oaicite:43]{index=43}
  goods_name VARCHAR(256) NOT NULL,             -- 货物劳务名称 :contentReference[oaicite:44]{index=44}
  spec_model VARCHAR(128) NULL,
  uom VARCHAR(32) NULL,
  qty DECIMAL(18,6) NULL,
  unit_price DECIMAL(18,6) NULL,
  amount_excl_tax DECIMAL(18,2) NOT NULL,
  tax_rate DECIMAL(9,6) NOT NULL,
  tax_amount DECIMAL(18,2) NOT NULL,
  amount_total DECIMAL(18,2) NOT NULL,
  discount_json JSON NULL,                      -- 折扣信息 :contentReference[oaicite:45]{index=45}
  remark VARCHAR(512) NULL,                     -- 备注栏 条件必填 :contentReference[oaicite:46]{index=46}
  invoice_status VARCHAR(16) NOT NULL,          -- 待开票/成功/失败/交付/红冲 :contentReference[oaicite:47]{index=47}
  delivery_mode VARCHAR(16) NOT NULL,           -- 交付方式 :contentReference[oaicite:48]{index=48}
  delivered_at DATETIME NULL,                   -- 交付时间 系统算 :contentReference[oaicite:49]{index=49}
  receiver VARCHAR(64) NULL,                    -- 接收人 系统算 :contentReference[oaicite:50]{index=50}
  red_info_no VARCHAR(64) NULL,                 -- 红字信息表编号 条件必填 :contentReference[oaicite:51]{index=51}
  origin_blue_invoice_uid VARCHAR(64) NULL,     -- 原蓝字发票ID 条件必填 :contentReference[oaicite:52]{index=52}
  tax_obligation_date DATE NOT NULL,            -- 纳税义务发生时间 :contentReference[oaicite:53]{index=53}
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  KEY idx_tax_vat_output_obligation (company_id, tax_obligation_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 税金计算/申报主表
CREATE TABLE IF NOT EXISTS tax_returns (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  company_id BIGINT NOT NULL,
  period VARCHAR(16) NOT NULL,                  -- 税款所属期 YYYYMM :contentReference[oaicite:54]{index=54}
  tax_type VARCHAR(32) NOT NULL,                -- 税种 :contentReference[oaicite:55]{index=55}
  form_version VARCHAR(64) NOT NULL,            -- 申报表版本号 :contentReference[oaicite:56]{index=56}
  status VARCHAR(16) NOT NULL,                  -- 未申报/申报中/成功/失败/已扣款 :contentReference[oaicite:57]{index=57}
  receipt_no VARCHAR(128) NULL,                 -- 回执号/流水号 回写 :contentReference[oaicite:58]{index=58}
  debit_status VARCHAR(16) NULL,                -- 扣款状态 回写 :contentReference[oaicite:59]{index=59}
  debited_at DATETIME NULL,                     -- 扣款时间 回写 :contentReference[oaicite:60]{index=60}
  tax_paid_cert_path VARCHAR(512) NULL,         -- 完税证明路径 回写 :contentReference[oaicite:61]{index=61}
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_tax_returns (company_id, period, tax_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 计税明细行（税基/税率/减免/应纳/预缴/应补退）
CREATE TABLE IF NOT EXISTS tax_calculation_lines (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tax_return_id BIGINT NOT NULL,
  tax_base DECIMAL(18,2) NOT NULL,              -- 计税依据 税基 系统算 :contentReference[oaicite:62]{index=62}
  tax_rate DECIMAL(9,6) NOT NULL,               -- 适用税率/征收率 系统算 :contentReference[oaicite:63]{index=63}
  quick_deduction DECIMAL(18,2) NULL,           -- 速算扣除数（个税/所得税）
  relief_code VARCHAR(64) NULL,                 -- 减免税代码 :contentReference[oaicite:64]{index=64}
  relief_amount DECIMAL(18,2) NULL,             -- 减免税金额 :contentReference[oaicite:65]{index=65}
  tax_payable DECIMAL(18,2) NOT NULL,           -- 应纳税额 系统算 :contentReference[oaicite:66]{index=66}
  prepaid_tax DECIMAL(18,2) NULL,               -- 已预缴 :contentReference[oaicite:67]{index=67}
  tax_due_refund DECIMAL(18,2) NOT NULL,        -- 应补(退) 系统算 :contentReference[oaicite:68]{index=68}
  calc_json JSON NULL,                          -- 公式穿透（可审计）
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  KEY idx_tax_calc_return (tax_return_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 风险指标
CREATE TABLE IF NOT EXISTS tax_risk_metrics (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  company_id BIGINT NOT NULL,
  period VARCHAR(16) NOT NULL,
  vat_burden_rate DECIMAL(9,6) NULL,            -- 税负率 :contentReference[oaicite:69]{index=69}
  income_burden_rate DECIMAL(9,6) NULL,
  burden_deviation_flag TINYINT NULL,           -- 偏差预警 :contentReference[oaicite:70]{index=70}
  inout_name_match_rate DECIMAL(9,6) NULL,      -- 进销项品名匹配 :contentReference[oaicite:71]{index=71}
  cancel_red_ratio DECIMAL(9,6) NULL,           -- 红冲/作废率 :contentReference[oaicite:72]{index=72}
  inv_diff_amount DECIMAL(18,2) NULL,           -- 库存账实差异 :contentReference[oaicite:73]{index=73}
  long_zero_filing_flag TINYINT NULL,           -- 长期零申报 :contentReference[oaicite:74]{index=74}
  related_party_ratio DECIMAL(9,6) NULL,        -- 关联交易占比 :contentReference[oaicite:75]{index=75}
  tax_credit_level VARCHAR(8) NULL,             -- 纳税信用等级 :contentReference[oaicite:76]{index=76}
  risk_score DECIMAL(10,2) NULL,                -- 风险指标得分 :contentReference[oaicite:77]{index=77}
  response_notes TEXT NULL,                     -- 风险应对记录 :contentReference[oaicite:78]{index=78}
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_tax_risk (company_id, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 电子档案（合规元数据）
CREATE TABLE IF NOT EXISTS tax_archives (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  company_id BIGINT NOT NULL,
  metadata_pack_id VARCHAR(128) NOT NULL,       -- 元数据包ID :contentReference[oaicite:79]{index=79}
  original_format VARCHAR(16) NOT NULL,         -- XML/OFD/PDF/JSON :contentReference[oaicite:80]{index=80}
  signature_verify_status VARCHAR(16) NOT NULL, -- 验签通过/失败 :contentReference[oaicite:81]{index=81}
  archive_dir_path VARCHAR(512) NOT NULL,       -- 归档目录路径 :contentReference[oaicite:82]{index=82}
  retention_years INT NOT NULL,                 -- 保管期限 :contentReference[oaicite:83]{index=83}
  regulator_report_status VARCHAR(16) NOT NULL, -- 监管报送状态 :contentReference[oaicite:84]{index=84}
  source_table VARCHAR(64) NULL,
  source_id BIGINT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_tax_archives_pack (company_id, metadata_pack_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 借阅权限记录（系统算）
CREATE TABLE IF NOT EXISTS tax_archive_access_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  archive_id BIGINT NOT NULL,
  accessed_by BIGINT NOT NULL,
  accessed_at DATETIME NOT NULL,
  purpose VARCHAR(256) NULL,
  created_at DATETIME NULL,
  KEY idx_tax_arch_access (archive_id, accessed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
