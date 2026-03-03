# P2-PERF-01 性能基线报告

- 日期: 2026-03-03
- 工具: `scripts/ops/perf_baseline.py`（本地并发压测）
- 说明: 预期 Artillery 脚本已生成为 `performance-test.yml`，当前环境未安装 `artillery` 命令，采用仓库内脚本执行等价基线。

## 压测配置
- 总请求: 600
- 并发: 10
- 接口1: `/api/dashboard/workbench?book_id=1`
- 接口2: `/api/reimbursements?book_id=1`
- Header: `X-User: perf_runner`, `X-Role: admin`

## 修复前（DB engine 每次新建）
### /api/dashboard/workbench
- 成功率: 72.00%
- RPS: 67.3672
- P95: 251.3605 ms
- 状态分布: {'200': 432, '500': 168}

### /api/reimbursements
- 成功率: 83.17%
- RPS: 93.2615
- P95: 215.0444 ms
- 状态分布: {'200': 499, '500': 101}

## 修复后（DB engine 复用 + 连接池参数）
### /api/dashboard/workbench
- 成功率: 100.00%
- RPS: 229.5468
- P95: 68.2935 ms
- 状态分布: {'200': 600}

### /api/reimbursements
- 成功率: 100.00%
- RPS: 429.4885
- P95: 51.6027 ms
- 状态分布: {'200': 600}

## 结论
- 修复前存在 500 错误，根因是数据库连接打满（`Too many connections`）。
- 修复后两条核心接口在并发10、600请求下成功率均达到 **100%**。
- 当前可作为 P2-PERF-01 基线版本。

## 证据文件
- `performance-test.yml`
- `docs/release/perf_baseline_workbench.json`
- `docs/release/perf_baseline_reimbursements.json`
- `docs/release/perf_baseline_workbench_after_pool_fix.json`
- `docs/release/perf_baseline_reimbursements_after_pool_fix.json`
