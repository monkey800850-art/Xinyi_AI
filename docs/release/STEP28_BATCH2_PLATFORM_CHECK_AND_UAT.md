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
