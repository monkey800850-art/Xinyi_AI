# STEP27-A 首批正式发布清单（Release Checklist）

## A. 文档头信息
- 项目：Xinyi_AI
- 阶段：STEP27-A（首批正式发布清单与准发布门槛）
- 适用版本：`main @ 43564ff`（发布执行时用 `git rev-parse --short HEAD` 回填）
- 生成日期：2026-02-27
- 执行人：`<填写>`
- 输入依据：
  - `docs/STEP26_TRIAL_COMMERCIAL.md`（含 2026-02-27 半量回归结论）
  - `docs/STEP25_UAT_RESULT.md`
  - `docs/uat/STEP25_UAT_RESULT.md`
  - `README_DEV.md`

## B. 发布前检查清单（可勾选）

### B1. 版本与分支确认
- [ ] 当前分支为 `main`：`git branch --show-current`
- [ ] 计划发布 commit 已确认并记录：`git rev-parse --short HEAD`
- [ ] 工作区干净：`git status`

### B2. 数据库迁移状态确认
- [ ] `alembic current` 与 `alembic heads` 一致
- [ ] `alembic upgrade head` 执行成功（无报错）
- [ ] 迁移版本记录已留档（命令输出粘贴到发布记录）

### B3. 基础数据初始化确认
- [ ] 新建账套 `POST /books` 成功（状态 201）
- [ ] 科目模板初始化无失败（`subject_init_result.failed = 0`）
- [ ] 系统角色/用户可查询：`GET /api/system/roles`、`GET /api/system/users`

### B4. 核心流程验证引用（不重复造结论）
- [ ] STEP26 全量实测结论已通过（见 `docs/STEP26_TRIAL_COMMERCIAL.md`）
- [ ] STEP26 半量回归 PASS（见该文档 6.1）
- [ ] S5/S6 阻断项清零（见该文档 6.5）

### B5. 资产模块关键口径确认
- [ ] 折旧计提可执行：`POST /api/assets/depreciation`（`success_count > 0`）
- [ ] 台账查询在 `ONLY_FULL_GROUP_BY` 下稳定：`GET /api/assets/ledger?...`
- [ ] 台账口径正确：
  - 已计提资产 `accumulated_depr` 正确
  - 未计提资产仍保留且 `accumulated_depr = 0`
- [ ] 资产导出可用：`GET /api/exports/assets/ledger?book_id=<id>`

### B6. 权限与审计追溯确认
- [ ] 审计日志可查询：`GET /api/system/audit`
- [ ] 关键动作可追溯（资产变动/付款/报销/凭证状态变更）
- [ ] 运行侧确认 `X-User/X-Role` 来源受控（网关或中间层注入）

### B7. 配置文件与环境变量确认（脱敏）
- [ ] `APP_ENV`、`DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD` 已配置
- [ ] `.env*` 与目标环境一致（不在仓库存明文密码）
- [ ] 模板文件存在：`templates/standards/enterprise.csv`、`templates/standards/small_enterprise.csv`

### B8. 日志与错误定位路径确认
- [ ] 应用日志路径已确认（默认 `logs/`）
- [ ] 500 错误可定位到 API + SQL/堆栈
- [ ] 发布值守联系人与响应群组已记录

### B9. 备份准备确认（手工可执行）
- [ ] 发布前执行 DB 备份（如 `mysqldump`）
- [ ] 备份文件路径、时间、操作者已记录
- [ ] 至少完成一次备份可恢复性抽检（可简化为测试库恢复）

### B10. 回滚条件与负责人确认
- [ ] 回滚触发条件已确认（见 E 节）
- [ ] 回滚决策人（产品/技术/运维）已指定
- [ ] 回滚执行人和验证人已指定

## C. 准发布门槛（Go / No-Go）

### C1. Go（必须全部满足）
1. P0 缺陷数 = 0（以 STEP26 结论和本次发布前复核为准）。
2. DB 迁移成功且版本一致（`current=head`）。
3. STEP26 关键证据成立：S5/S6 阻断项已清零，半量回归 PASS。
4. 资产口径检查通过（已计提正确、未计提不漏、`0` 展示正确）。
5. 备份完成且回滚责任人已确认。

### C2. No-Go（任一触发即禁止发布）
1. 存在未关闭 P0。
2. 迁移失败或迁移后核心接口 500。
3. 折旧/台账口径出现错账风险。
4. 无可用备份或回滚责任人未明确。

### C3. 可带病进入（受控）
- 仅允许低风险体验项（P2/P3）带病进入，且必须：
  - 不影响核心流程与数据正确性
  - 有明确临时规避方案
  - 有修复计划（版本与责任人）

## D. 已知限制（当前版本）
- 当前无已知阻断发布的 P0（基于 STEP26 半量回归）。
- 关注点：接口身份依赖 `X-User/X-Role` 请求头，生产侧需通过网关/鉴权层统一注入与校验，禁止客户端直传伪造头。
- 关注点：数据库连接与 `.env` 配置必须与目标环境一致，避免因地址/网络导致启动失败。

## E. 回滚触发条件（定义）

### E1. 触发条件
1. 核心流程出现持续 500（资产变动、台账、折旧、付款/报销关键动作）。
2. 发现数据错账风险（折旧累计异常、台账口径错误、状态流转与事实不一致）。
3. 发布迁移失败或迁移后关键表/索引异常。

### E2. 决策与执行角色
- 回滚决策：技术负责人 + 业务负责人（双签）
- 回滚执行：运维/DBA
- 回滚验证：测试/业务验收代表

### E3. 回滚前必须保留证据
- 错误日志与时间窗口
- 失败请求样本（路径、参数、状态码、响应体）
- 关键页面/API截图
- 当前版本 commit id、迁移版本号、备份文件信息

---

## STEP27-A 结论
- 本清单基于 STEP25/STEP26 真实结果整理，可直接用于 STEP27-B/C/D 的逐项执行与签字放行。
