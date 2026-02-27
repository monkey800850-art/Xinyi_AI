# STEP28 执行计划与首个交付（Kickoff）

## 1. 输入依据
- `docs/release/STEP27_SIGNOFF.md`
- `docs/release/STEP27_RELEASE_CHECKLIST.md`
- `docs/ops/STEP27_OPS_RUNBOOK.md`
- `docs/ops/STEP27_INCIDENT_MONITORING_PLAN.md`
- `docs/release/STEP27_FINAL_PRECHECK_AND_DRILL.md`

## 2. STEP28 首要目标
在不回滚 STEP27 工作的前提下，优先把“人工可执行流程”升级为“可重复执行的最小自动化检查能力”，降低试运行值守成本与漏检风险。

## 3. 任务分解（小步交付）

### T1（优先级 P1）：自动化健康检查脚本
- 目标：将 STEP27-D 的关键健康检查固化为单脚本执行。
- 输出：`scripts/ops/health_check.sh`
- 验收：脚本可对 `/`、`/dashboard`、`/api/system/roles`、`/api/assets/changes`、`/api/assets/ledger` 输出 PASS/FAIL 并返回退出码。

### T2（优先级 P1）：数据库备份脚本化
- 目标：将手工 `mysqldump` 流程标准化。
- 预期输出：`scripts/ops/db_backup.sh` + 备份留痕模板。
- 验收：一条命令完成备份文件落盘并输出元信息（时间、库名、大小）。

### T3（优先级 P2）：关键链路最小回归自动化
- 目标：固化 S4->S6 / S5 核心链路的最小校验。
- 预期输出：可复用的测试命令入口（如 unittest 目标与执行说明）。
- 验收：可在发布窗口前快速复跑，输出明确通过/失败。

## 4. 执行顺序
1. T1 健康检查脚本（先落地，立刻能用）
2. T2 备份脚本化（降低人工失误）
3. T3 最小回归自动化（补齐发布前快速校验）

## 5. 首个子任务交付（本次完成）

### 5.1 交付物
- `scripts/ops/health_check.sh`

### 5.2 使用方式
```bash
# 默认参数执行
scripts/ops/health_check.sh

# 自定义环境
BASE_URL=http://127.0.0.1:5000 BOOK_ID=9 DEP_YEAR=2025 DEP_MONTH=2 scripts/ops/health_check.sh
```

### 5.3 判定规则
- 任一检查失败时返回非 0 退出码。
- 输出包含每项检查结果（PASS/FAIL）与总计汇总。

## 6. 文档留痕
- 本文件作为 STEP28 kickoff 记录，不重复复述 STEP27 结论。
- 后续每个子任务完成后在本文件追加“执行结果与证据路径”。

## 7. T2 执行结果（本次完成）

### 7.1 交付物
- `scripts/ops/db_backup.sh`

### 7.2 能力说明（最小版）
- 读取方式：优先读取环境变量，缺省时从项目根目录 `.env` 补齐 `DB_*`。
- 支持参数覆盖：`--host --port --db --user --password --backup-dir`。
- 支持可选压缩：`--gzip`（输出 `.sql.gz`）。
- 备份命名：`<db_name>_YYYYmmdd_HHMMSS.sql[.gz]`。
- 错误处理：缺配置、命令不存在、目录不可写、连接/导出失败均返回非 0。

### 7.3 使用示例
```bash
# 默认读取 .env 与默认输出目录
scripts/ops/db_backup.sh

# 指定输出目录
BACKUP_DIR=/tmp/step28_backups scripts/ops/db_backup.sh

# 参数覆盖 + gzip
scripts/ops/db_backup.sh --host 127.0.0.1 --port 3306 --db xinyi_ai --user <user> --password <password> --backup-dir /tmp/step28_backups --gzip
```

### 7.4 实测证据（2026-02-27）
- 命令：`BACKUP_DIR=/tmp/step28_backups scripts/ops/db_backup.sh`
- 结果：`exit=0`
- 输出摘要：
  - `file=/tmp/step28_backups/xinyi_ai_20260227_230952.sql`
  - `size_bytes=586084`
  - `db=xinyi_ai host=127.0.0.1 port=3306`
- 说明：在受限沙箱中会因 TCP 限制失败；提权后可正常完成备份导出。
