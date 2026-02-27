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
- 预期输出：`scripts/ops/backup_db.sh` + 备份留痕模板。
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
