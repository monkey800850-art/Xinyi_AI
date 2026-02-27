# STEP27-B 运维手册（Ops Runbook，最小可执行版）

## A. 文档头信息
- 项目：Xinyi_AI
- 阶段：STEP27-B（运维手册编写与补齐）
- 适用分支/版本：`main`（执行时记录 `git rev-parse --short HEAD`）
- 生成日期：2026-02-27
- 适用环境：Windows 11 + WSL2 Ubuntu 22.04 + MySQL 8.0
- 前置条件：
  - 已完成 STEP27-A 发布清单评审
  - 已有 STEP26 实测与半量回归结论（见 `docs/STEP26_TRIAL_COMMERCIAL.md`）

## B. 环境准备与依赖

### B1. Python 与依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
依赖来源：`requirements.txt`（Flask / SQLAlchemy / Alembic / PyMySQL / openpyxl）。

### B2. MySQL 服务要求
- 使用 MySQL 8.0。
- Windows 侧 `MySQL80` 服务需启动。
- 项目数据库：`xinyi_ai`（不存在时先创建）。

### B3. WSL 连接 Windows MySQL
- 当前项目实测可用配置：`DB_HOST=127.0.0.1`，`DB_PORT=3306`。
- 不建议继续使用不可达地址（历史曾出现 `192.168.1.1:3306` 超时）。

### B4. 源码拉取网络限制（实战经验）
- 可能出现 GitHub SSH 失败：`kex_exchange_identification`（22/443 被策略拦截）。
- 备用方案：改 HTTPS + PAT。
```bash
git remote -v
git remote set-url origin https://github.com/<org>/<repo>.git
git pull origin main
# push 时按提示输入 GitHub 用户名 + PAT（不要使用账号密码）
```

## C. 配置文件说明（.env）

### C1. 必填项
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

项目读取逻辑见：`app/config.py`（缺任一项会启动失败）。

### C2. 示例（脱敏）
```env
APP_ENV=development
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=xinyi_ai
DB_USER=<db_user>
DB_PASSWORD=<db_password>
```

### C3. 常见错误
- 缺少 `.env` 或缺字段：报 `Missing required database config fields`。
- 库不存在：迁移或启动时报数据库不存在。
- 账号权限不足：迁移/写入时报 `access denied`。

## D. 启动与迁移

### D1. 安装依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### D2. 数据库迁移
```bash
alembic upgrade head
alembic current
alembic heads
```

### D3. 服务启动
```bash
python3 app.py
```
启动时会先做 DB 连通性检查；失败会直接退出并打印错误。

### D4. 启动后最小健康检查
```bash
curl -s http://127.0.0.1:5000/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/dashboard
curl -s http://127.0.0.1:5000/api/system/roles
```
预期：`/` 返回 `{"status":"ok"}`；页面状态码 `200`；系统 API 可返回 JSON。

## E. 数据库与基础数据初始化（最小版）

### E1. 新库创建
```sql
CREATE DATABASE xinyi_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
然后执行 `alembic upgrade head`。

### E2. 基础数据初始化
- 科目模板：通过 `POST /books` 自动触发导入（见 `app/services/standard_importer.py`）。
- 角色/用户：通过系统管理 API 维护。

### E3. 初始化失败定位
- 重点看 `POST /books` 返回中的 `subject_init_result.failed/errors`。
- 重点字段：`balance_direction`（历史问题点，现已补兜底推断）。

## F. 常见故障排查（重点）

### F1. 数据库拒绝连接
现象：启动或 Alembic 报 `Can't connect to MySQL server`。
排查：
1. Windows 侧确认 MySQL80 服务已启动。
2. 核对 `.env`：`DB_HOST=127.0.0.1`、端口/账号正确。
3. 在 WSL 验证：
```bash
mysql -h127.0.0.1 -P3306 -u<user> -p -e "SELECT 1;" xinyi_ai
```

### F2. WSL 到 Windows MySQL 连接
- 以本项目当前经验优先使用 `127.0.0.1`。
- 若使用其他内网 IP 超时，先回退到 `127.0.0.1` 复测。

### F3. GitHub SSH 失败
现象：`kex_exchange_identification`。
处理：改 HTTPS + PAT（见 B4）。

### F4. `ONLY_FULL_GROUP_BY` 引发 SQL 错误识别
- 现象：资产台账相关 SQL 报 `only_full_group_by`。
- 快速确认：
```bash
mysql -h127.0.0.1 -P3306 -u<user> -p -Nse "SELECT @@sql_mode;" xinyi_ai
```
- 若报错，保留失败请求 + SQL 片段，按服务层 SQL 修复，不通过关闭 SQL mode 规避。

### F5. API 500 定位路径
1. 复现请求（记录路径、参数、请求头、时间）。
2. 查看服务终端堆栈（Flask 输出）。
3. 定位到具体 service 文件 SQL（如 `app/services/*.py`）。
4. 记录证据后再修复，避免盲改。

## G. 备份与恢复（最小可执行）

### G1. 备份前确认
- 确认目标库名、账号权限、磁盘空间。
- 记录当前版本 commit 与迁移版本。

### G2. 手工备份
```bash
mysqldump -h127.0.0.1 -P3306 -u<user> -p --single-transaction --routines --triggers xinyi_ai > xinyi_ai_$(date +%F_%H%M%S).sql
```

### G3. 手工恢复
```bash
mysql -h127.0.0.1 -P3306 -u<user> -p -e "CREATE DATABASE IF NOT EXISTS xinyi_ai_restore DEFAULT CHARACTER SET utf8mb4;"
mysql -h127.0.0.1 -P3306 -u<user> -p xinyi_ai_restore < xinyi_ai_<backup_file>.sql
```

### G4. 风险提示
- 恢复前先备份当前库，避免二次覆盖。
- 恢复验证建议在独立库（如 `xinyi_ai_restore`）先做。

## H. 附录

### H1. 常用命令速查
```bash
# 分支/版本
git branch --show-current
git rev-parse --short HEAD
git status

# 迁移
alembic current
alembic heads
alembic upgrade head
alembic downgrade -1

# 启动
python3 app.py
```

### H2. 日志/关键文件路径
- 运行与开发说明：`README_DEV.md`
- 发布清单：`docs/release/STEP27_RELEASE_CHECKLIST.md`
- STEP26 试商用与回归结论：`docs/STEP26_TRIAL_COMMERCIAL.md`
- 环境配置读取：`app/config.py`
- 服务入口：`app.py`
- 运行日志目录：`logs/`

### H3. 发布前联系与响应角色（简化）
- 发布负责人：`<填写>`
- 运维执行人：`<填写>`
- 数据库负责人：`<填写>`
- 回滚决策人：`<填写>`

---

## STEP27-B 结论
- 本手册覆盖首批发布与试运行的最小可执行运维路径，可直接用于值守与故障定位。
- 自动化脚本未新增；当前采用手工可执行替代流程（迁移、备份、恢复、网络切换）。
