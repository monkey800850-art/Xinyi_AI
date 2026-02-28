# STEP29 P1 方案设计：会计分录批量导入 + 账套导入

## A. 会计分录批量导入（P1）

### A1. 目标与范围
- 目标：提供“先预检、后导入”的批量分录能力，先 API 后 UI。
- 输入格式：优先 `CSV`，兼容 `JSON`（后续）。
- 范围：草稿导入与结果回执，不绕过现有凭证校验链。

### A2. 入口设计（建议 API）
- `POST /api/vouchers/import/preview`
  - 作用：文件/数据预检，不落库。
- `POST /api/vouchers/import/commit`
  - 作用：执行导入（按校验通过的记录），输出批次结果。
- `GET /api/vouchers/import/batches/<batch_id>`
  - 作用：查询批次明细与失败原因。

### A3. 模板/字段定义（最小）
- 头部字段：`book_id`, `voucher_date`, `voucher_word`, `voucher_no`, `maker`, `status(draft/posted)`
- 行字段：`line_no`, `summary`, `subject_code`, `debit`, `credit`, `aux_code(可选)`, `note(可选)`
- 分组规则：同一 `voucher_no + voucher_date` 归并为一张凭证。

### A4. 预检与校验
- 借贷平衡：每张凭证分组后借贷合计一致。
- 科目合法：`subjects` 中存在且启用。
- 期间合法：凭证日期所在期间为开放状态。
- 重复导入策略：
  - 默认拒绝重复（同 `book_id + voucher_date + voucher_word + voucher_no`）。
  - 返回可读冲突明细。

### A5. 导入结果反馈格式（建议）
```json
{
  "batch_id": "IMP20260303_001",
  "total_vouchers": 20,
  "success_vouchers": 18,
  "failed_vouchers": 2,
  "errors": [
    {"voucher_no":"0008","row":42,"field":"subject_code","message":"subject_not_found:999999"},
    {"voucher_no":"0011","row":67,"field":"debit_credit","message":"not_balanced"}
  ]
}
```

### A6. 审计与留痕（最小）
- 审计记录：模块 `voucher_import`，动作 `preview/commit`，记录 `operator/role/book_id/batch_id/success_count/fail_count`。
- 证据：导入批次回执文件路径（`/tmp` 或业务表字段）。

### A7. 风险边界
- 不允许导入链绕过现有凭证校验与权限体系。
- 不直接写已过账凭证（默认先草稿导入）。
- 不在本阶段实现复杂映射 DSL。

---

## B. 账套导入（P1）

### B1. 目标与范围
- 目标：提供业务级账套快照导入能力，先“新账套导入”安全落地。
- 范围：账套基础信息、科目、期间、基础配置（最小版）。
- 策略：先校验后执行，失败整体回滚。

### B2. 入口设计（建议 API）
- `POST /api/books/import/preview`
  - 作用：快照结构与冲突预检。
- `POST /api/books/import/commit`
  - 作用：执行导入，返回新 `book_id` 与统计。
- `GET /api/books/import/tasks/<task_id>`
  - 作用：查询导入任务状态与错误明细。

### B3. 导入对象范围（最小）
- `book`：名称、会计准则、启用状态。
- `subjects`：编码、名称、类别、方向、层级、父级、启用状态。
- `accounting_periods`：期间状态（open/closed）。
- 可选 `basic_config`：最小参数集（存在则校验，不存在则按默认）。

### B4. 结构校验与冲突策略
- 结构校验：
  - 快照版本号有效；
  - 必填字段存在；
  - 科目编码不重复；
  - 期间月份合法（1..12）。
- 冲突策略（最小）：
  - 默认 `reject`（发现冲突即拒绝）；
  - 后续可扩展 `skip/overwrite`，本阶段不开放。

### B5. 导入前/后校验
- 导入前：
  - 复用 `backup-restore-verify` 同类校验口径；
  - 账套名称冲突检查；
  - 快照完整性检查。
- 导入后：
  - 调用初始化完整性检查（`init-integrity` 等效口径）；
  - 核对 `subjects/periods` 数量与快照一致。

### B6. 审计与失败回滚（最小）
- 审计记录：模块 `book_import`，动作 `preview/commit`，记录 `task_id/book_name/source/operator/result`。
- 失败回滚：导入事务失败整体回滚，不保留半成品账套。

### B7. 风险边界
- 不允许覆盖现有生产账套数据（仅新建导入）。
- 不允许跳过结构校验强制导入。
- 不在本阶段处理跨版本复杂迁移脚本。

## C. 与第二批能力衔接（实现导向）
- 复用第二批 P0 能力：`backup-snapshot`、`backup-restore-verify`、`init-integrity`。
- 复用凭证规则校验链：借贷平衡、科目合法、期间合法。
- 复用审计风格与角色头（`X-User`/`X-Role`）。
- 复用回归方法：`unittest + test_client + 证据文件路径`。
