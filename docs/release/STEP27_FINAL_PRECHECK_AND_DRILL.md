# STEP27-D 发布前最终检查与模拟演练（最小版）

## 1. 文档信息
- 项目：Xinyi_AI
- 阶段：STEP27-D（Final Precheck & Drill）
- 执行日期：2026-02-27
- 执行环境：Windows 11 + WSL2 Ubuntu 22.04 + MySQL 8.0
- 输入依据：
  - `docs/release/STEP27_RELEASE_CHECKLIST.md`（STEP27-A）
  - `docs/ops/STEP27_OPS_RUNBOOK.md`（STEP27-B）
  - `docs/ops/STEP27_INCIDENT_MONITORING_PLAN.md`（STEP27-C）
  - `docs/STEP26_TRIAL_COMMERCIAL.md`（STEP26 实测与回归）

## 2. A. 发布前最终检查（关键项）

### 2.1 版本/分支确认
- 命令：`git rev-parse --short HEAD` -> `d395d13`
- 命令：`git branch --show-current` -> `main`
- 命令：`git status --short` -> `?? docs/ops/`（文档变更待提交）
- 结论：版本与分支正确；发布前需先提交当前文档变更。

### 2.2 数据库迁移状态确认
- 命令：`alembic current` -> `20260227_000017 (head)`
- 命令：`alembic heads` -> `20260227_000017 (head)`
- 命令：`alembic upgrade head` -> 成功（无新增迁移）
- 结论：迁移状态一致，通过。

### 2.3 `.env` 配置项检查（脱敏）
- 检查结果：`.env` 存在，包含
  - `FLASK_ENV=<masked>`
  - `DB_HOST=<masked>`
  - `DB_PORT=<masked>`
  - `DB_NAME=<masked>`
  - `DB_USER=<masked>`
  - `DB_PASSWORD=<masked>`
- 结论：关键项齐备，通过。

### 2.4 核心启动/日志/备份命令确认
- 启动命令：`python3 app.py`（可启动）
- 日志路径：`logs/`（目录存在）
- 备份命令可执行性：
  - `mysqldump --version` 成功
  - `mysqldump ... --no-data xinyi_ai > /tmp/step27d_backup_schema.sql` 成功（`872` 行）
- 结论：通过。

### 2.5 关键页面/API 冒烟（最小）
- `GET /` -> 200，`{"status":"ok"}`
- `GET /dashboard` -> 200
- `GET /api/system/roles` -> 200（`roles_items=2`）
- `GET /api/assets/changes?book_id=9` -> 200（`changes_items=1`）
- `GET /api/assets/ledger?book_id=9&dep_year=2025&dep_month=2` -> 200（`ledger_items=2`）
- 结论：通过。

## 3. B. 最小发布演练（实际执行）

### 3.1 执行链路
1. 执行迁移检查与升级：`alembic current && alembic heads && alembic upgrade head`
2. 启动服务：`python3 app.py`（后台拉起）
3. 健康检查：`/`、`/dashboard`、`/api/system/roles`、`/api/assets/changes`、`/api/assets/ledger`
4. 停止服务：结束后台进程

### 3.2 结果与耗时
- 粗粒度耗时：`elapsed_sec=1`
- 结果：
  - `dashboard=200`
  - `roles=200`
  - `changes=200`
  - `ledger=200`
  - `health={"status":"ok"}`
- 演练结论：最小发布链路可执行。

## 4. C. 最小应急演练（桌面演练）

### 4.1 演练场景
- 场景：发布后 `GET /api/assets/ledger` 出现持续 500（参照 STEP26 历史案例）。
- 分级：`P0`（核心查询不可用，涉及账务口径风险）。

### 4.2 按预案执行动作（不破坏数据）
1. 发现故障：记录路径、参数、时间窗口、状态码。
2. 初步分类：按 STEP27-C 判定 P0。
3. 先止损：暂停资产台账相关业务操作与导出。
4. 收集证据：
   - 错误日志/堆栈
   - 失败请求样本
   - 当前 commit 与迁移版本
5. 定位修复：按 STEP27-B 路径定位 service SQL。
6. 回归验证：至少验证 `/api/assets/ledger` + S4->S6 联动口径。
7. 恢复服务：验证通过后恢复并观察 30 分钟。
8. 复盘：24 小时内输出复盘模板记录。

### 4.3 回滚决策条件对照（引用 STEP27-A）
- 若出现以下任一项，触发回滚评估：
  - 核心流程持续 500
  - 发现错账风险
  - 迁移后关键表异常
- 回滚前必须确认：证据留存 + 备份可用 + 决策人确认。

## 5. D. 结论

### 5.1 文档可执行性
- STEP27-A/B/C 在本次最小演练中可执行，关键命令与流程可落地。

### 5.2 发布阻断缺口
- 当前未发现阻断发布的技术性 P0。
- 发现 1 项流程缺口（非功能故障）：
  - 发布前需先提交并归档本轮 STEP27 文档变更（当前 `git status --short` 显示 `?? docs/ops/`）。

### 5.3 是否可进入 STEP27-E
- 结论：**有条件可进入 STEP27-E**。
- 条件：先完成文档提交归档（版本冻结），再进行发布准备签收。
