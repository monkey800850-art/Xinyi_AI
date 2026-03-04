# 辅助核算主数据字段规范（部门/员工/银行账户/往来单位）

本规范用于“心易智能”财务系统的辅助核算维度主数据建设，确保：
- 结构化（可用于自动凭证、自动对账、电子发票/数电票处理）
- 可审计（字段、规则固定；迁移可追溯）
- 可扩展（后续供销存/多店可复用维度桥表）

---

## 1. 部门管理（组织架构与成本中心）

建议表：`dim_departments`

| 字段 | 类型 | 必填 | 规则/说明 |
|---|---|---:|---|
| ledger_id | BIGINT | 是 | 账套分区键 |
| dept_code | VARCHAR(64) | 是 | 唯一编码；支持树形：01.02.03 |
| dept_name | VARCHAR(128) | 是 | 标准全称 |
| parent_dept_code | VARCHAR(64) | 否 | 根节点为空；建议也保留 parent_id（如已存在） |
| dept_type | ENUM | 是 | 职能/业务/生产/研发/销售… |
| cost_center_code | VARCHAR(64) | 是 | 成本中心ID/编码（归集与考核） |
| profit_center_code | VARCHAR(64) | 否 | 独立核算部门可填 |
| manager_employee_id | BIGINT | 是 | 关联员工主数据（hr_employees.id） |
| established_on | DATE | 是 | 成立日期 |
| revoked_on | DATE | 否 | 撤销日期；撤销后禁止新增业务单据 |
| budget_control_policy | ENUM | 是 | rigid/flexible/none |
| company_id | BIGINT | 是 | 所属法人实体（多组织必备） |
| remark | TEXT | 否 | 备注 |

索引/约束建议：
- uniq(ledger_id, dept_code)
- 可选：parent_dept_code 外键/一致性校验（可用触发器或应用层校验）

---

## 2. 员工管理（薪酬与往来主体）

建议表：`hr_employees`

| 字段 | 类型 | 必填 | 规则/说明 |
|---|---|---:|---|
| ledger_id | BIGINT | 是 | 账套分区键 |
| emp_no | VARCHAR(64) | 是 | 全局唯一工号（建议 uniq(ledger_id, emp_no) 或全局 uniq） |
| name | VARCHAR(64) | 是 | 真实姓名 |
| id_card_no_enc | VARBINARY / VARCHAR | 是 | 身份证号加密存储（仅密文） |
| dept_id | BIGINT | 是 | 关联 dim_departments.id |
| job_title | VARCHAR(64) | 是 | 岗位/职务 |
| hire_date | DATE | 是 | 入职日期 |
| terminate_date | DATE | 否 | 离职日期 |
| employment_type | ENUM | 是 | formal/probation/intern/labor/rehire |
| tax_residency | ENUM | 是 | resident/non_resident |
| bank_account_no_enc | VARBINARY / VARCHAR | 是 | 默认工资卡号（密文） |
| bank_cnaps | VARCHAR(16) | 是 | 联行号 |
| social_security_city | VARCHAR(64) | 是 | 社保缴纳地 |
| housing_fund_account | VARCHAR(64) | 否 | 公积金账号 |
| special_deductions_json | JSON | 是 | 专项附加扣除信息（定期同步） |
| credit_score | DECIMAL(6,2) | 否 | 系统计算（可空） |
| internal_ar_subject_code | VARCHAR(64) | 是 | 其他应收款-员工借款等映射 |
| status | ENUM | 是 | active/leave/terminated/suspended |

---

## 3. 银行账户管理（资金与银企直连）

建议表：`fin_bank_accounts`

| 字段 | 类型 | 必填 | 规则/说明 |
|---|---|---:|---|
| ledger_id | BIGINT | 是 | 账套分区键 |
| account_code | VARCHAR(64) | 是 | 账户内部编码（系统唯一） |
| account_name | VARCHAR(128) | 是 | 与开户信息一致 |
| bank_account_no_enc | VARBINARY / VARCHAR | 是 | 加密存储 |
| bank_full_name | VARCHAR(256) | 是 | 精确到支行 |
| cnaps_code | VARCHAR(16) | 是 | 12位联行号（允许 12~16 兼容） |
| account_type | ENUM | 是 | basic/general/special/temp/fc/guarantee |
| currency | VARCHAR(8) | 是 | CNY/USD/EUR… |
| company_id | BIGINT | 是 | 所属法人实体（严禁混用） |
| cash_pool_flag | TINYINT | 是 | 是否参与资金归集 |
| ebank_config_id | VARCHAR(128) | 否 | 银企直连配置引用（不存证书/私钥） |
| status | ENUM | 是 | normal/frozen/closed/dormant |
| opened_on | DATE | 是 | 启用日期 |
| closed_on | DATE | 否 | 注销日期 |
| balance_warn_threshold | DECIMAL(18,2) | 否 | 余额预警 |
| reconciliation_mode | ENUM | 是 | auto/import/manual |
| last_reconciled_on | DATE | 否 | 系统计算 |
| has_long_unreconciled | TINYINT | 否 | 系统计算 |

---

## 4. 往来单位（客户/供应商）

建议主表：`dim_parties`（统一客户/供应商底座）  
建议子表：`party_bank_accounts`（多账户）

### 4.1 dim_parties

| 字段 | 类型 | 必填 | 规则/说明 |
|---|---|---:|---|
| ledger_id | BIGINT | 是 | 账套分区键 |
| party_code | VARCHAR(64) | 是 | 单位编码（可分段区分客户/供应商） |
| party_name | VARCHAR(256) | 是 | 与执照/税务一致 |
| uscc | VARCHAR(32) | 是 | 统一社会信用代码（核心索引） |
| taxpayer_type | ENUM | 是 | general/small |
| industry | VARCHAR(64) | 否 | 行业 |
| reg_address | VARCHAR(256) | 是 | 注册地址（发票字段） |
| reg_phone | VARCHAR(64) | 是 | 注册电话（发票字段） |
| business_scope | TEXT | 否 | 经营范围（风控） |
| party_type | ENUM | 是 | customer/vendor/both/other |
| settle_currency | VARCHAR(8) | 是 | 结算币种 |
| payment_terms | VARCHAR(128) | 是 | 月结/预付等 |
| credit_limit | DECIMAL(18,2) | 否 | 信用额度（客户） |
| credit_days | INT | 否 | 信用期限天数 |
| ar_subject_code | VARCHAR(64) | 是 | 应收科目代码 |
| ap_subject_code | VARCHAR(64) | 是 | 应付科目代码 |
| tax_device_info | VARCHAR(128) | 否 | 税控盘/UKey信息（可选） |
| e_invoice_email | VARCHAR(128) | 是 | 数电票接收邮箱（关键） |
| contact_name | VARCHAR(64) | 是 | 主要联系人 |
| contact_phone | VARCHAR(64) | 是 | 电话/手机 |
| ship_invoice_address | VARCHAR(256) | 是 | 收货/开票地址 |
| cooperation_status | ENUM | 是 | potential/active/frozen/terminated |
| blacklist_flag | TINYINT | 是 | 黑名单（真则阻断业务） |
| last_trade_on | DATE | 否 | 系统计算 |
| archive_ref_id | VARCHAR(128) | 否 | 电子档案引用 |
| risk_level | ENUM | 否 | system_calc：normal/watch/high |
| business_status | ENUM | 否 | system_calc：active/revoked/cancelled/abnormal |

### 4.2 party_bank_accounts（多账户）

| 字段 | 类型 | 必填 | 规则/说明 |
|---|---|---:|---|
| party_id | BIGINT | 是 | FK dim_parties.id |
| bank_account_no_enc | VARBINARY / VARCHAR | 是 | 加密存储 |
| bank_name | VARCHAR(256) | 是 | 开户行全称 |
| cnaps_code | VARCHAR(16) | 否 | 联行号（可选） |
| is_default_pay | TINYINT | 是 | 默认付款账户 |
| is_default_recv | TINYINT | 是 | 默认收款账户 |

