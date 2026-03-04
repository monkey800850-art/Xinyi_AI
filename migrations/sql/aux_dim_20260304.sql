-- AUXDIM schema hardening (department/employee/bank_account/party)
-- safe pattern: add columns if not exists (MySQL 8 supports IF NOT EXISTS for ADD COLUMN)
-- If your MySQL version does not support it, apply manually.

-- 1) dim_departments
CREATE TABLE IF NOT EXISTS dim_departments (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  ledger_id BIGINT NOT NULL,
  dept_code VARCHAR(64) NOT NULL,
  dept_name VARCHAR(128) NOT NULL,
  parent_dept_code VARCHAR(64) NULL,
  dept_type VARCHAR(32) NOT NULL,
  cost_center_code VARCHAR(64) NOT NULL,
  profit_center_code VARCHAR(64) NULL,
  manager_employee_id BIGINT NOT NULL,
  established_on DATE NOT NULL,
  revoked_on DATE NULL,
  budget_control_policy VARCHAR(16) NOT NULL,
  company_id BIGINT NOT NULL,
  remark TEXT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_dim_departments_ledger_code (ledger_id, dept_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) hr_employees
CREATE TABLE IF NOT EXISTS hr_employees (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  ledger_id BIGINT NOT NULL,
  emp_no VARCHAR(64) NOT NULL,
  name VARCHAR(64) NOT NULL,
  id_card_no_enc VARBINARY(255) NOT NULL,
  dept_id BIGINT NOT NULL,
  job_title VARCHAR(64) NOT NULL,
  hire_date DATE NOT NULL,
  terminate_date DATE NULL,
  employment_type VARCHAR(16) NOT NULL,
  tax_residency VARCHAR(16) NOT NULL,
  bank_account_no_enc VARBINARY(255) NOT NULL,
  bank_cnaps VARCHAR(16) NOT NULL,
  social_security_city VARCHAR(64) NOT NULL,
  housing_fund_account VARCHAR(64) NULL,
  special_deductions_json JSON NOT NULL,
  credit_score DECIMAL(6,2) NULL,
  internal_ar_subject_code VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_hr_employees_ledger_empno (ledger_id, emp_no),
  KEY idx_hr_employees_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) fin_bank_accounts
CREATE TABLE IF NOT EXISTS fin_bank_accounts (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  ledger_id BIGINT NOT NULL,
  account_code VARCHAR(64) NOT NULL,
  account_name VARCHAR(128) NOT NULL,
  bank_account_no_enc VARBINARY(255) NOT NULL,
  bank_full_name VARCHAR(256) NOT NULL,
  cnaps_code VARCHAR(16) NOT NULL,
  account_type VARCHAR(16) NOT NULL,
  currency VARCHAR(8) NOT NULL,
  company_id BIGINT NOT NULL,
  cash_pool_flag TINYINT NOT NULL DEFAULT 0,
  ebank_config_id VARCHAR(128) NULL,
  status VARCHAR(16) NOT NULL,
  opened_on DATE NOT NULL,
  closed_on DATE NULL,
  balance_warn_threshold DECIMAL(18,2) NULL,
  reconciliation_mode VARCHAR(16) NOT NULL,
  last_reconciled_on DATE NULL,
  has_long_unreconciled TINYINT NULL DEFAULT 0,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_fin_bank_accounts_ledger_code (ledger_id, account_code),
  KEY idx_fin_bank_accounts_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4) dim_parties
CREATE TABLE IF NOT EXISTS dim_parties (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  ledger_id BIGINT NOT NULL,
  party_code VARCHAR(64) NOT NULL,
  party_name VARCHAR(256) NOT NULL,
  uscc VARCHAR(32) NOT NULL,
  taxpayer_type VARCHAR(16) NOT NULL,
  industry VARCHAR(64) NULL,
  reg_address VARCHAR(256) NOT NULL,
  reg_phone VARCHAR(64) NOT NULL,
  business_scope TEXT NULL,
  party_type VARCHAR(16) NOT NULL,
  settle_currency VARCHAR(8) NOT NULL,
  payment_terms VARCHAR(128) NOT NULL,
  credit_limit DECIMAL(18,2) NULL,
  credit_days INT NULL,
  ar_subject_code VARCHAR(64) NOT NULL,
  ap_subject_code VARCHAR(64) NOT NULL,
  tax_device_info VARCHAR(128) NULL,
  e_invoice_email VARCHAR(128) NOT NULL,
  contact_name VARCHAR(64) NOT NULL,
  contact_phone VARCHAR(64) NOT NULL,
  ship_invoice_address VARCHAR(256) NOT NULL,
  cooperation_status VARCHAR(16) NOT NULL,
  blacklist_flag TINYINT NOT NULL DEFAULT 0,
  last_trade_on DATE NULL,
  archive_ref_id VARCHAR(128) NULL,
  risk_level VARCHAR(16) NULL,
  business_status VARCHAR(16) NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  UNIQUE KEY uk_dim_parties_ledger_code (ledger_id, party_code),
  KEY idx_dim_parties_uscc (uscc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4.2) party_bank_accounts
CREATE TABLE IF NOT EXISTS party_bank_accounts (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  party_id BIGINT NOT NULL,
  bank_account_no_enc VARBINARY(255) NOT NULL,
  bank_name VARCHAR(256) NOT NULL,
  cnaps_code VARCHAR(16) NULL,
  is_default_pay TINYINT NOT NULL DEFAULT 0,
  is_default_recv TINYINT NOT NULL DEFAULT 0,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  KEY idx_party_bank_accounts_party (party_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
