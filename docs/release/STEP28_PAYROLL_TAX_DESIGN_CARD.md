# STEP28 Payroll/Tax 设计卡（精简版）

## 1. Payroll MVP 范围（第一批）
- 工资期间：按月（`YYYY-MM`），保留关账状态。
- 工资单最小字段：员工、期间、应发、扣减、个税、实发、状态。
- 个税规则：居民工资薪金累计预扣法（规则计算，可回放）。
- 税务台账：按员工+期间沉淀税额快照，用于申报前核对。
- 凭证衔接：仅输出凭证建议草稿（不自动入账），复用 STEP28-B `preview/suggest` 形态。

## 2. 数据模型草案（核心）
- `payroll_periods(id, book_id, period, status, locked_by, locked_at)`
- `payroll_slips(id, book_id, employee_id, period, gross_amount, deduction_amount, taxable_base, tax_amount, net_amount, status)`
- `payroll_tax_ledger(id, book_id, employee_id, period, tax_type, taxable_base, tax_amount, calc_version, snapshot_json)`
- `payroll_voucher_links(id, payroll_slip_id, suggestion_ref, adopted_voucher_id, adopted_at)`

## 3. 税务台账衔接
- 计算服务输出结构化结果，落税务台账快照。
- 汇总口径对接现有税务模块查询视图（不改申报主流程）。
- 审计沿用现有 `audit_logs`：记录计算模式、期间、成功/失败。

## 4. 与 STEP28-B 复用关系
- 复用 B1-T1 的规则优先模式：税务仅给“计算结果+解释”。
- 复用凭证模板建议入口，不直写正式凭证。
- 复用权限与审计头风格（`X-User`、`X-Role`）。

## 5. 范围边界（本批不做）
- 不做 AI/OCR/语音识别。
- 不做复杂考勤、非居民复杂税制、汇缴差异自动摊销。
- 不做完整工资模块重构与全量 UI。

## 6. 本轮优先项（已实现）
- 年终奖计税切换：`POST /api/tax/calc/year-end-bonus`
- 劳务报酬个税：`POST /api/tax/calc/labor-service`

## 7. 计算口径与简化假设（本轮）
- 年终奖 `separate`：`bonus/12` 选月度档，`tax=bonus*rate-quick_deduction`。
- 年终奖 `merge`（简化）：仅将 `bonus_amount` 作为“并入后应税基数示例”，未并入全年工资累计流水。
- 劳务报酬（简化预扣）：
  - `gross<=4000`：`taxable_base=gross-800`
  - `gross>4000`：`taxable_base=gross*80%`
  - 按 20%/30%-2000/40%-7000 分档，`tax=taxable_base*rate-quick_deduction`
