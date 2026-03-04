# AUXDIM-FIELD-01 补充完善计划（Patch Plan）

## aux_parties  <- 单位(客户/供应商) (source=doc)
- missing_in_db: 28
- missing_in_model: 28
### 缺失字段（DB，抽样）
- `ar_ap_subject_code`
- `archive_file_id`
- `bank_accounts`
- `blacklist_flag`
- `business_scope`
- `business_status`
- `contact_email`
- `contact_phone`
- `contract_ids`
- `cooperation_status`
- `credit_code`
- `credit_days`
- `credit_limit`
- `einvoice_credit_quota`
- `industry`
- `last_trade_date`
- `party_code`
- `party_full_name`
- `party_type`
- `payment_terms`
- `primary_contact`
- `registered_address`
- `registered_phone`
- `risk_level`
- `settlement_currency`

## aux_persons  <- 个人(员工/往来主体) (source=doc)
- missing_in_db: 16
- missing_in_model: 17
### 缺失字段（DB，抽样）
- `bank_account_no`
- `cnaps_code`
- `department_code`
- `employee_credit_score`
- `employee_no`
- `employment_type`
- `hire_date`
- `housing_fund_account`
- `id_card_no`
- `internal_arap_subject`
- `job_title`
- `name`
- `social_security_city`
- `special_additional_deduction`
- `tax_residency`
- `termination_date`

## aux_bank_accounts  <- 银行账户 (source=doc)
- missing_in_db: 16
- missing_in_model: 17
### 缺失字段（DB，抽样）
- `account_internal_code`
- `account_name`
- `account_status`
- `account_type`
- `balance_alert_threshold`
- `bank_account_no`
- `bank_connect_config_id`
- `bank_full_name`
- `cash_pool_flag`
- `close_date`
- `cnaps_code`
- `last_reconciliation_date`
- `legal_entity_id`
- `open_date`
- `reconciliation_method`
- `unreconciled_flag`

## aux_projects  <- 项目 (source=assumption)
- missing_in_db: 15
- missing_in_model: 15
### 缺失字段（DB，抽样）
- `budget_control_policy`
- `budget_total`
- `contract_ids`
- `cost_center_code`
- `customer_party_code`
- `department_code`
- `end_date`
- `legal_entity_id`
- `project_code`
- `project_manager`
- `project_name`
- `project_status`
- `remarks`
- `revenue_center_code`
- `start_date`

## Notes
- 本卡仅生成补充完善计划，不做迁移/建模落库。下一卡 AUXDIM-FIELD-02 执行落地（新表+模型+最小CRUD）。
- 项目维度字段为 assumption，可用你的项目字段规范替换后再落地。