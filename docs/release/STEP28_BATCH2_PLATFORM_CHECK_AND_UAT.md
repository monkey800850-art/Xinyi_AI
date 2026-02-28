# STEP28 第二批执行记录（平台核查 + P0补齐 + UI全链测试）

## 1. 执行范围
- STEP28-B-T1（规则优先凭证建议，已延续）
- 平台能力只读核查（并对 P0 项补齐）
- 科目管理优化（最小改动）
- UI 入口全链测试（端到端/UAT风格）

## 2. 平台能力核查结论（只读）
1. 会计分录批量导入：`未发现专用批量导入 API`（P1，暂不在本批强行补齐）
2. 账套引入/导入：`未发现专用账套导入 API`（P1，暂不在本批强行补齐）
3. 账套备份：
   - DB 脚本备份：已具备 `scripts/ops/db_backup.sh`
   - 业务级账套备份：本批新增 `GET /api/books/<book_id>/backup-snapshot`
4. 恢复验证：
   - DB 级恢复验证：本批新增 `scripts/ops/db_restore_verify.sh`
   - 业务级恢复校验：本批新增 `POST /api/books/backup-restore-verify`
5. 账套删除安全控制：
   - 未发现硬删除入口
   - 本批新增安全停用入口 `POST /api/books/<book_id>/disable`（角色 + 二次确认 + 审计）
6. 初始化完整性：
   - 本批补齐账套创建时期间初始化（3年）
   - 新增完整性检查 `GET /api/books/<book_id>/init-integrity`

## 3. 本批代码变更
- `app/services/book_service.py`
  - 新增期间初始化、初始化完整性检查、业务级备份快照、恢复校验、安全停用
- `app.py`
  - 新增：
    - `GET /api/books/<book_id>/init-integrity`
    - `GET /api/books/<book_id>/backup-snapshot`
    - `POST /api/books/backup-restore-verify`
    - `POST /api/books/<book_id>/disable`
  - 为上述能力增加审计记录
- `app/services/standard_importer.py`
  - 新增类别一致性校验（warn-only）
- `app/services/trial_balance_service.py`
  - 增加编码前缀父级回退逻辑
  - 增加 `category_summary` 分类汇总输出
- `scripts/ops/db_restore_verify.sh`
  - 新增 DB 备份恢复验证脚本
- `tests/test_step28_batch2_platform_subjects.py`
  - 新增第二批核心回归测试
- `app/services/tax_service.py`
  - 新增年终奖计税切换：`calc_year_end_bonus_tax`
  - 新增劳务报酬个税：`calc_labor_service_tax`
- `app.py`
  - 新增税务计算 API：
    - `POST /api/tax/calc/year-end-bonus`
    - `POST /api/tax/calc/labor-service`
- `tests/test_step28_batch2_tax_calcs.py`
  - 新增税务两项回归测试（成功/异常）

## 4. P0 实测结果（真实执行）

### 4.1 回归测试
命令：
```bash
python3 -m unittest -v tests/test_step28_b_t1_template_preview.py tests/test_step28_batch2_platform_subjects.py tests/test_step28_batch2_tax_calcs.py
```
结果：
- `Ran 13 tests in 1.089s`
- `OK`

### 4.2 DB 备份与恢复验证
备份命令：
```bash
scripts/ops/db_backup.sh --backup-dir /tmp/step28_batch2_backups
```
结果：
- `[OK] backup completed`
- `file=/tmp/step28_batch2_backups/xinyi_ai_20260228_062316.sql`
- `size_bytes=1354198`

恢复验证命令：
```bash
scripts/ops/db_restore_verify.sh --dump-file /tmp/step28_batch2_backups/xinyi_ai_20260228_062316.sql --user root --password 88888888
```
结果：
- `[OK] restore_verify_passed`
- `table_count=36`
- `books_count=22`
- `subjects_count=9028`
- `cleanup=dropped`

## 5. UI入口全链测试（真实记录）

执行方式：使用 Flask `test_client` 从页面路由入口触发，再调用对应 API 链路。

### 5.1 页面入口可达
- `GET /dashboard` -> `200`
- `GET /voucher/entry` -> `200`
- `GET /reports/trial_balance` -> `200`
- `GET /system/audit` -> `200`

### 5.2 成功链路
1. 初始化：
   - `POST /books` -> `201`（`book_id=23`, `subjects=421`）
   - `GET /api/books/23/init-integrity` -> `200`（`ok=true`, `period_count=36`）
2. 账套操作：
   - `GET /api/books/23/backup-snapshot` -> `200`（`subject_count=421`, `period_count=36`）
   - `POST /api/books/backup-restore-verify` -> `200`（`ok=true`）
3. 科目管理/凭证建议：
   - `GET /api/autocomplete?type=subject&book_id=23&q=100&limit=5` -> `200`（`items=5`）
   - `POST /api/vouchers/template-suggest` -> `200`（`success=true`）
4. 关键报表（余额表）：
   - `POST /api/vouchers`（posted）-> `201`
   - `GET /api/trial_balance?...` -> `200`（`items=421`, `category_summary=6`）

### 5.3 失败链路
1. 业务级恢复校验失败：
   - 篡改快照期间后 `POST /api/books/backup-restore-verify` -> `400`，`ok=false`
2. 凭证建议失败：
   - 模板参数传非法科目 `999999` -> `400`，`subject_not_found:999999`
3. 账套停用权限失败：
   - 非 `admin/boss` 角色调用 `POST /api/books/<id>/disable` -> `403 forbidden`

## 6. 税务两项实现与实测（本批必做）

### 6.1 年终奖单独计税/并入计税切换
- API：`POST /api/tax/calc/year-end-bonus`
- 输入：`bonus_amount`、`tax_mode(separate/merge)`、`biz_year`
- 输出：`tax_mode/tax_amount/taxable_base/rate/quick_deduction/explain`
- 实测：
  1. `separate` 成功：`200`，`tax_amount=1080.0`
  2. `merge` 成功：`200`，`tax_amount=1080.0`
  3. 非法模式失败：`400`，`tax_mode must be one of: separate, merge`

### 6.2 劳务报酬个税计算
- API：`POST /api/tax/calc/labor-service`
- 输入：`gross_amount`、`period(可选)`
- 输出：`gross_amount/taxable_base/tax_amount/rate/explain`
- 实测：
  1. 成功：`gross_amount=10000` -> `200`，`taxable_base=8000.0`，`tax_amount=1600.0`
  2. 非法金额失败：`gross_amount=-1` -> `400`，`gross_amount must be > 0`

### 6.3 关键页面与API补充回归
- 页面：
  - `/dashboard` -> `200`
  - `/voucher/entry` -> `200`
  - `/reports/trial_balance` -> `200`
  - `/tax/summary` -> `200`
- 新增税务 API：
  - `bonus_separate_ok` -> `200`
  - `bonus_merge_ok` -> `200`
  - `bonus_invalid_mode_fail` -> `400`
  - `labor_ok` -> `200`
  - `labor_invalid_amount_fail` -> `400`

## 7. 已知限制与后续
1. 会计分录批量导入 API：本批仅核查，未实现（P1）
2. 账套导入/迁移 API：本批仅核查，未实现（P1）
3. 年终奖 `merge` 采用最小可验证口径（仅以 bonus 作为综合所得计税基数，未并入全年工资流水）
4. 劳务报酬按最小版预扣规则实现，未接入申报周期汇缴差异处理
5. 本批保持最小改动，未引入 AI 识别/生成逻辑

## 8. 第5轮 G 统一回归与收口（2026-02-28）

### 8.1 统一回归（单测/API）
命令：
```bash
python3 -m unittest -v tests/test_step28_b_t1_template_preview.py tests/test_step28_batch2_platform_subjects.py tests/test_step28_c_subject_category.py tests/test_step28_batch2_tax_calcs.py
```
结果：
- `Ran 16 tests in 1.887s`
- `OK`

覆盖：
- STEP28-B-T1：模板建议与规则校验（4）
- 平台/P0：初始化、备份恢复验证、停用安全（4）
- 科目优化：类别一致性、不一致告警、fallback（3）
- 税务两项：年终奖切换、劳务报酬（5）

### 8.2 关键页面不回归
命令：Flask `test_client` 页面访问
结果：
- `GET /dashboard` -> `200`
- `GET /voucher/entry` -> `200`
- `GET /reports/trial_balance` -> `200`
- `GET /tax/summary` -> `200`

### 8.3 缺陷分级
- 本轮回归未出现失败项。
- P0：0，P1：沿用既有遗留（分录批量导入、账套导入），P2：0。

### 8.4 第二批最终结论
- 第二批完成：`完成`。
- 可进入下一轮：`可进入 H（UI 全链测试）`。

## 9. 第6轮 H UI 全链测试（端到端/UAT，2026-02-28）

### 9.1 测试环境与证据
- 执行方式：Flask `test_client`（从 UI 页面入口触发并串联后端调用链）。
- 证据文件：`/tmp/step28_h_ui_uat_239020.json`
- 总用例：`22`，通过：`22`，失败：`0`（失败链路为“预期失败”校验，均命中预期状态码）。

### 9.2 覆盖范围
- 初始化/完整性：`POST /books`、`GET /api/books/<id>/init-integrity`
- 账套操作：`GET /api/books/<id>/backup-snapshot`、`POST /api/books/backup-restore-verify`、`POST /api/books/<id>/disable`
- 科目/凭证：`/voucher/entry`、`POST /api/vouchers/template-suggest`、`POST /api/vouchers/template-preview`、`/reports/trial_balance`
- 报表：`GET /api/trial_balance`（类别汇总 + fallback）
- 税务：`/tax/summary`、`POST /api/tax/calc/year-end-bonus`、`POST /api/tax/calc/labor-service`
- 审计页面：`/system/audit`

### 9.3 成功链路（节选）
1. 初始化与完整性：`POST /books -> 201`，`GET init-integrity -> 200, ok=true`
2. 账套备份与恢复校验：`snapshot -> 200`，`backup-restore-verify -> 200, ok=true`
3. 凭证与报表：`template-suggest -> 200`，`POST voucher(posted) -> 201`，`trial_balance -> 200`，`category_summary` 含 `ASSET/PNL`
4. 老数据 fallback：清空 `subjects.category` 后 `trial_balance -> 200`，`category_source=prefix_fallback`
5. 税务调用链：bonus `separate/merge -> 200`，labor -> `200`

### 9.4 失败链路（均为预期拦截）
1. 停用权限拦截：非管理员 `POST /api/books/<id>/disable -> 403`
2. 停用确认拦截：错误确认串 `POST /api/books/<id>/disable -> 400`
3. 凭证非法科目：`template-preview(debit=999999) -> 400`
4. 年终奖非法模式：`year-end-bonus(tax_mode=invalid) -> 400`
5. 劳务报酬非法金额：`labor-service(gross=-1) -> 400`
6. 关闭期间拦截：`template-preview(biz_date in closed period) -> 400`

### 9.5 缺陷分级结果
- 新增缺陷：`0`
- P0：`0`
- P1：`0`（本轮未发现新增；历史 P1 遗留保持不变）
- P2：`0`

### 9.6 结论
- 本轮 H 结论：UI 全链测试通过（按当前范围）。
- 是否立即开修复卡：`否`（未发现新增 P0/P1 缺陷）。
