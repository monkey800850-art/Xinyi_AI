# STEP28 执行计划（主线重排：STEP28-A + STEP28-B）

## 1. 输入依据
- `docs/release/STEP27_SIGNOFF.md`
- `docs/release/STEP27_RELEASE_CHECKLIST.md`
- `docs/ops/STEP27_OPS_RUNBOOK.md`
- `docs/ops/STEP27_INCIDENT_MONITORING_PLAN.md`
- `docs/release/STEP27_FINAL_PRECHECK_AND_DRILL.md`

## 2. STEP28 主线定义

### 2.1 STEP28-A（已落地）：运维能力增强（最小自动化）
目标：将 STEP27 手工流程固化为可重复执行入口，降低发布窗口漏检风险。

### 2.2 STEP28-B（新增主线）：会计凭证录入 AI 增强（规则 + AI）
目标：采用递进路线提升凭证录入效率与准确率，**先规则后 AI**，避免直接跳端到端自动记账。

## 3. STEP28-A 与 STEP28-B 关系说明
- STEP28-A 提供稳定底座（健康检查、备份、最小回归），保障发布与试运行过程可控。
- STEP28-B 在该底座上推进“凭证录入增强”，先确定性规则，再引入 AI 识别与建议。
- 两者并行但不冲突：A 负责可用性与运维确定性，B 负责业务录入效率与智能化。

## 4. STEP28-A 现状（已完成）

### A-T1 自动化健康检查脚本（完成）
- 交付物：`scripts/ops/health_check.sh`
- 验收：关键健康接口 PASS/FAIL 输出与退出码。
- 实测：`pass=6 fail=0`。

### A-T2 数据库备份脚本化（完成，A1补齐于 2026-02-28）
- 交付物：`scripts/ops/db_backup.sh`
- 验收：时间戳备份文件落盘、失败非0、支持 `.env`/环境变量/参数覆盖。
- 本轮实测（成功）：
  - 命令：`scripts/ops/db_backup.sh --backup-dir /tmp/step28_a1_t2_restart`
  - 结果：`[OK] backup completed`
  - 文件：`/tmp/step28_a1_t2_restart/xinyi_ai_20260228_074057.sql`
  - 大小：`size_bytes=1799611`
  - 退出码：`exit=0`
- 本轮实测（失败）：
  - 命令：`scripts/ops/db_backup.sh --bad-opt`
  - 结果：`[ERROR] Unknown option: --bad-opt`
  - 退出码：`exit=1`

### A-T3 关键链路最小回归（完成，A1补齐于 2026-02-28）
- 交付物：`scripts/ops/min_regression.sh`
- 覆盖：S5 与 S4->S6。
- 本轮实测（成功）：
  - 前置：本地启动 `python3 app.py`
  - 命令：`scripts/ops/min_regression.sh`
  - 复核输出样例：`TEST_PREFIX=STEP28R_074306`
  - 结果：`pass_count=8 fail_count=0 blocked_count=0`
  - 关键通过项：`s4-depreciation-run`、`s5-change-create`、`s5-change-list`、`s4-to-s6-ledger-linkage`
  - 退出码：`exit=0`
- 本轮实测（异常）：
  - 命令：`BASE_URL=http://127.0.0.1:59999 scripts/ops/min_regression.sh`
  - 复核输出样例：`TEST_PREFIX=STEP28R_074248`
  - 结果：`blocked_count=3`（含 `sample-book-create` 等阻断）
  - 退出码：`exit=1`

## 5. STEP28-B：会计凭证录入 AI 增强（规则优先 + AI增强）

## 阶段1：凭证模板库 / 规则引擎优先（最小可用、最高确定性）

### 目标
- 建立/增强凭证模板库（按业务类型、票据类型、交易场景）。
- 支持模板参数化字段：摘要、金额、日期、对方单位、税额等。
- 增强规则校验：借贷平衡、科目合法性、期间合法性、辅助核算必填。
- 在不依赖 AI 的前提下先提升录入效率与准确率。

### 交付物
- 文档：`docs/ai/STEP28B_PHASE1_TEMPLATE_RULES.md`
- 配置：`config/voucher_templates.json`（或同等结构化模板库）
- 服务/API：凭证草稿生成与规则校验入口（复用现有 `api/vouchers` 能力，新增最小规则封装）
- 页面（可选最小）：凭证录入页模板选择器（如仅后端先行则记录为后续）

### 最小验收标准
- 至少 3 类业务场景模板可用（示例：费用报销、固定资产折旧、税费计提）。
- 模板生成分录后，规则校验可明确返回通过/失败原因。
- 人工修改后可正常保存凭证，且审计链不受影响。

## 阶段2：AI识别层（输入结构化）

### 目标
- 面向电子发票、语音文本、账单、合同等非结构化输入。
- AI 仅做字段提取：金额、税额、日期、交易方、票据类型、业务关键词。
- **不直接做最终记账决策**。

### 交付物
- 文档：`docs/ai/STEP28B_PHASE2_EXTRACTION_SPEC.md`
- 接口：`/api/ai/extract`（示意）返回结构化字段 + 置信度 + 原文片段映射
- 样本集：最小脱敏样本与提取结果对照清单

### 最小验收标准
- 对既定样本集，关键字段提取成功率达到预设阈值（阈值在文档中定义）。
- 低置信字段明确标记，不自动落账。
- 失败样本可追溯到原始输入与提取日志。

## 阶段3：AI+规则生成“凭证建议”（人审后入账）

### 目标
- AI 输出建议：业务类型、科目建议、借贷方向、摘要建议、金额拆分、置信度。
- 规则层继续校验并约束最终结果。
- 人工审核确认后生成正式凭证。
- 强化可审计：保留原始材料、识别结果、建议分录、人工修改记录。

### 交付物
- 文档：`docs/ai/STEP28B_PHASE3_SUGGESTION_FLOW.md`
- 接口：建议生成/采纳流程 API（草稿态）
- 审计字段扩展方案：建议版本号、人工修订痕迹

### 最小验收标准
- 建议分录可被人工一键采纳或修订后采纳。
- 采纳前必须经过规则校验。
- 审计日志可回放“原始输入 -> AI建议 -> 人工最终分录”。

## 阶段4：反馈闭环（先做规则学习，不急于模型训练）

### 目标
- 记录 AI 建议与最终入账差异。
- 统计高频修正项，优先优化模板和规则优先级。
- 为后续模型增强积累高质量数据。

### 交付物
- 文档：`docs/ai/STEP28B_PHASE4_FEEDBACK_LOOP.md`
- 统计报表：建议采纳率、人工修订热点、规则命中率
- 数据规范：差异样本标注字段定义

### 最小验收标准
- 至少形成一版“高频修正项 TOP 列表”。
- 模板/规则优化能反映在下一轮建议质量变化中。
- 闭环数据可用于后续模型训练评估（本阶段不要求训练）。

## 6. 风险与边界（STEP28-B）
- AI 不直接替代会计判断，不允许自动最终入账。
- 最终入账必须人工确认，并可追溯修改行为。
- 低置信度建议必须提示并阻断自动采纳。
- 规则校验优先级高于 AI 建议。

## 7. 与现有凭证/审计/权限体系衔接点
- 凭证体系：复用现有凭证保存与状态流转链路（不破坏现有 `voucher` 主流程）。
- 审计体系：沿用并扩展审计日志，记录 AI 建议与人工修订轨迹。
- 权限体系：建议查看/采纳/覆盖需区分角色权限（录入、复核、会计主管）。

## 8. 执行顺序（STEP28 后续）
1. STEP28-B 阶段1（模板与规则先行）
2. STEP28-B 阶段2（AI识别输入结构化）
3. STEP28-B 阶段3（AI建议 + 人审采纳）
4. STEP28-B 阶段4（反馈闭环与规则优化）

## 9. STEP28-B 首个可执行子任务建议（仅建议，不执行）
- 建议任务：`B1-T2 模板扩展与辅助核算校验补强`。
- 最小动作：
  1. 扩展模板参数（department/project/person）并补齐可选维度占位。
  2. 新增辅助核算必填规则（按科目属性）和更细粒度错误码。
  3. 增补模板预览接口示例与前端联调字段说明。
- 交付验收：模板预览在“参数完整/缺失/维度不合法”三类场景下均有清晰可读回包。

## 10. STEP28-B B1-T1 完成记录（2026-02-27）
- 交付物：
  - `app/services/voucher_template_service.py`
  - `app.py`（`POST /api/vouchers/template-preview` + `POST /api/vouchers/template-suggest`）
  - `tests/test_step28_b_t1_template_preview.py`
- 复用点盘点（服务/API/表）：
  - 服务复用：`app/services/voucher_service.py::_check_period_open`（期间合法性检查复用）；科目合法性复用 `subjects` 表口径（`code + is_enabled`）。
  - API 复用：沿用凭证域路由风格 `POST /api/vouchers/*`，保持仅“草稿建议/预览”不入账。
  - 审计与权限风格复用：复用 `X-User/X-Role` 头解析与 `log_audit` 记录风格（module=`voucher`）。
  - 关键表复用：`books`、`subjects`、`accounting_periods`、`audit_logs`（不写 `vouchers/voucher_lines`）。
- API 路径：
  - `POST /api/vouchers/template-preview`
  - `POST /api/vouchers/template-suggest`（与 preview 同规则，同为 preview-only）
- 已支持模板类型（最小 3 类）：
  - `BANK_FEE`（银行手续费）
  - `ASSET_DEPRECIATION`（固定资产折旧）
  - `EXPENSE_REIMBURSEMENT_PAYMENT`（费用报销付款）
- 能力范围：
  - 模板参数替换：`amount` / `biz_date` / `summary_text` / `counterparty`（并可覆盖默认科目参数）
  - 规则校验：借贷平衡、科目合法性（存在+启用）、期间合法性（账期开放）
  - 结果结构：`success/template_info/voucher_draft/validations/errors/warnings/audit_hint`
- 实测结果（2026-02-27，本地 `python3 -m unittest -v tests/test_step28_b_t1_template_preview.py`）：
  - 总计：4/4 通过（2 成功 + 2 失败），`Ran 4 tests in 0.539s`
  - `ok_preview`：`BANK_FEE` -> HTTP 200, `success=true`
  - `ok_suggest`：`ASSET_DEPRECIATION` -> HTTP 200, `success=true`
  - `fail_subject`：`EXPENSE_REIMBURSEMENT_PAYMENT`（`debit_subject_code=999999`）-> HTTP 400, `subject_not_found:999999`
  - `fail_period`：`BANK_FEE`（关闭账期 2025-02）-> HTTP 400, `会计期间已结账`
  - 非落账验证：实测脚本输出 `voucher_count 0`
- 本轮复测结果（2026-02-28）：
  - 回归命令：`python3 -m unittest -v tests/test_step28_b_t1_template_preview.py`
  - 回归结果：`Ran 4 tests in 0.555s`，`OK`
  - API复测：`ok_preview=200`、`ok_suggest=200`、`fail_subject=400(subject_not_found:999999)`、`fail_period=400(会计期间已结账)`
  - 非落账复核：`voucher_count=0`

## 11. 第二批增量完成记录（2026-02-28）
- 平台能力核查（只读）：
  - 已核查：会计分录批量导入、账套引入/导入、备份恢复、删除安全、初始化完整性
  - 结论：P0 已补齐；P1（会计分录批量导入、账套导入）保留后续
- P0 补齐交付：
  - 初始化完整性：`POST /books` 增加期间初始化（3年）；`GET /api/books/<id>/init-integrity`
  - 备份恢复：
    - DB级：`scripts/ops/db_backup.sh` + `scripts/ops/db_restore_verify.sh`
    - 业务级：`GET /api/books/<id>/backup-snapshot` + `POST /api/books/backup-restore-verify`
  - 删除安全控制：`POST /api/books/<id>/disable`（`admin/boss` + `confirm_text` + 审计）
- 科目管理最小优化：
  - `standard_importer` 增加类别一致性校验（warn-only，不把类别硬当一级科目）
  - `trial_balance` 增加编码前缀父级回退与 `category_summary` 分类汇总兼容输出
- UI入口全链测试：
  - 页面入口：`/dashboard`、`/voucher/entry`、`/reports/trial_balance`、`/system/audit` 全部 `200`
  - 关键链路成功：初始化、账套快照与恢复校验、科目联想、凭证建议、余额表
  - 关键失败链路：恢复校验篡改快照失败、非法科目建议失败、非授权停用账套失败
- Payroll/Tax 本批必做项（已实现）：
  - 年终奖计税切换：`POST /api/tax/calc/year-end-bonus`（`separate/merge`）
  - 劳务报酬个税计算：`POST /api/tax/calc/labor-service`
  - 税务实测：5组（成功/失败均覆盖），并纳入回归 `13 tests -> OK`
- 详情记录：`docs/release/STEP28_BATCH2_PLATFORM_CHECK_AND_UAT.md`

## 12. 第3轮-C 科目管理优化完成记录（2026-02-28）
- 变更范围（最小改动）：
  - 新增：`app/services/subject_category_service.py`（类别映射与前缀推导）
  - 接入：`app/services/standard_importer.py`（初始化导入类别一致性校验，warn-only）
  - 接入：`app/services/trial_balance_service.py`（类别优先 + 前缀fallback 汇总兼容）
  - 测试：`tests/test_step28_c_subject_category.py`
- 字段策略（不改表结构）：
  - 运行时映射 `category_code`（ASSET/LIABILITY/EQUITY/COST/PNL）与 `category_name`。
  - 兼容现有 `subjects.category`：非空时优先使用；空值时按 `subject_code` 首位回退。
- 一致性校验接入点：
  - 初始化导入路径：`import_subjects_from_standard`。
  - 校验口径：`subject_code` 前缀类别 vs `category` 文本类别，输出 `category_validation`（`mode=warn_only`）。
- 余额表兼容口径：
  - `items` 增加 `category_code/category_name/category_source`。
  - `category_summary` 按 `category_code+category_name` 汇总；老数据空类别回退前缀。
- 实测（真实执行）：
  - 单测命令：`python3 -m unittest -v tests/test_step28_c_subject_category.py`
    - 结果：`Ran 3 tests in 0.792s`，`OK`
  - 回归命令：`python3 -m unittest -v tests/test_step28_batch2_platform_subjects.py`
    - 结果：`Ran 4 tests in 0.938s`，`OK`
  - API 复核（test client）：
    - 一致成功：`GET /api/trial_balance` -> `200`，`category_codes` 含 `ASSET/PNL`
    - 不一致告警：`POST /books`（自定义不一致CSV）-> `201`，`category_validation.mismatch_count=1`，`mode=warn_only`
    - 老数据 fallback：`GET /api/trial_balance` -> `200`，`item(1001).category_source=prefix_fallback`

## 13. 第4轮-D/E/F Payroll-Tax（省额度模式）完成记录（2026-02-28）
- D 设计卡（精简版）：
  - 文档：`docs/release/STEP28_PAYROLL_TAX_DESIGN_CARD.md`
  - 已明确：Payroll MVP、数据模型草案、税务台账衔接、与 STEP28-B 复用关系、范围边界、简化假设。
- E 年终奖计税切换（已实现）：
  - 服务：`app/services/tax_service.py::calc_year_end_bonus_tax`
  - API：`POST /api/tax/calc/year-end-bonus`
  - 参数校验：`bonus_amount` 必填且 `>0`，`tax_mode in {separate, merge}`。
- F 劳务报酬个税（已实现）：
  - 服务：`app/services/tax_service.py::calc_labor_service_tax`
  - API：`POST /api/tax/calc/labor-service`
  - 参数校验：`gross_amount` 必填且 `>0`。
- 单元测试（真实执行）：
  - 命令：`python3 -m unittest -v tests/test_step28_batch2_tax_calcs.py`
  - 结果：`Ran 5 tests in 0.435s`，`OK`
- API 实测（真实执行，5组）：
  - `bonus_separate_ok`：HTTP `200`，`tax_amount=1080.0`
  - `bonus_merge_ok`：HTTP `200`，`tax_amount=1080.0`
  - `bonus_invalid_mode_fail`：HTTP `400`，`tax_mode must be one of: separate, merge`
  - `labor_ok`：HTTP `200`，`taxable_base=8000.0`，`tax_amount=1600.0`
  - `labor_invalid_amount_fail`：HTTP `400`，`gross_amount must be > 0`

## 14. 第5轮-G 第二批统一回归与文档收口（2026-02-28）
- 统一回归命令：
  - `python3 -m unittest -v tests/test_step28_b_t1_template_preview.py tests/test_step28_batch2_platform_subjects.py tests/test_step28_c_subject_category.py tests/test_step28_batch2_tax_calcs.py`
- 结果：
  - `Ran 16 tests in 1.887s`
  - `OK`
- 页面不回归（Flask test_client）：
  - `/dashboard=200`
  - `/voucher/entry=200`
  - `/reports/trial_balance=200`
  - `/tax/summary=200`
- 第二批状态汇总：
  - A1：完成
  - A2：完成
  - B1+B2：完成（P0 关闭）
  - C：完成
  - D+E+F：完成
  - G：完成
- 已知限制（保留）：
  - 年终奖 `merge` 为最小示例口径，未并入全年累计工资流水
  - 劳务报酬未覆盖汇缴差异与非居民复杂规则
  - P1 遗留：会计分录批量导入、账套导入
- 第二批最终结论：`完成`
- 下一步：`可进入第6轮 H（UI 全链测试）`

## 15. 第6轮-H UI 全链测试（2026-02-28）
- 执行方式：Flask `test_client`，从 UI 页面入口触发端到端/UAT 风格链路。
- 证据：`/tmp/step28_h_ui_uat_239020.json`
- 结果总览：`total=22`，`pass=22`，`fail=0`
- 页面状态：
  - `/dashboard=200`
  - `/voucher/entry=200`
  - `/reports/trial_balance=200`
  - `/tax/summary=200`
  - `/system/audit=200`
- 成功链路覆盖：
  - 初始化 + 完整性检查
  - 账套备份快照 + 恢复校验
  - 凭证模板建议 + 过账凭证 + 余额表类别汇总/fallback
  - 税务年终奖（separate/merge）与劳务报酬计算
- 失败链路覆盖（预期拦截）：
  - 停用权限不足（403）
  - 停用确认串错误（400）
  - 凭证非法科目（400）
  - 年终奖非法模式（400）
  - 劳务报酬非法金额（400）
  - 关闭期间凭证建议（400）
- 缺陷分级：本轮新增 `P0=0, P1=0, P2=0`
- 结论：无需立即开修复卡，进入后续阶段可按计划推进。

## 16. 下一步（第三批）规划入口（2026-02-28）
- 规划文档：`docs/release/STEP29_BATCH3_EXECUTION_TREE.md`
- 缺陷修复卡：`docs/release/STEP29_A_DEFECT_REPAIR_CARDS.md`
- P1 方案设计：`docs/release/STEP29_P1_IMPORT_DESIGN.md`
- 说明：第三批仅规划已完成，后续按 `3A -> 3B -> 3C -> 3D` 顺序执行。
