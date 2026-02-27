# STEP26 试商用总结（第一批试商用）

## 1. 试商用范围
- 环境：本地/准生产（MySQL + Flask）
- 模块：系统管理、固定资产（类别/卡片/折旧/变动/台账）、报表与导出、报销/付款/对账/税务等核心流程冒烟
- 目标：验证核心流程可跑通、数据正确性可接受、权限审计无高风险

## 2. 试商用部署与运行
### 2.1 环境准备
1. 准备 MySQL 并创建库 `xinyi_ai`
2. 复制环境变量（如需）：`.env.example` -> `.env`
3. 创建虚拟环境并安装依赖：
   - `python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
4. 初始化/升级数据库：
   - `alembic upgrade head`
5. 启动服务：
   - `python3 app.py`

### 2.2 试商用冒烟路径
- S1 系统管理闭环（用户/角色/规则/审计）
- S2 固定资产类别管理
- S3 固定资产卡片管理
- S4 月度折旧计提
- S5 资产变动（处置/报废/转移）
- S6 资产台账与折旧报表
- S7 跨模块冒烟回归（报销/付款/银行/税务）

## 3. 试商用问题清单
| ID | 类型 | 严重级别 | 描述 | 影响 | 状态 |
|---|---|---|---|---|---|
| TRIAL-001 | 部署/运行 | P0 | 环境未就绪导致服务无法启动（缺少依赖或 `.env` 配置/DB 未迁移） | 阻断全部场景 | 已制定运行手册并补齐检查点 |
| TRIAL-002 | 权限/审计 | P1 | 付款/报销审批类接口未强制要求 `operator`，审计链可能缺失 | 审计风险 | 已修复 |
| TRIAL-003 | 数据正确性 | P1 | 付款/报销更新接口返回状态可能与数据库实际状态不一致 | 影响前端显示与流程判断 | 已修复 |
| TRIAL-004 | 权限/审计 | P1 | 付款创建接口允许提交任意状态（如直接写入 `approved/paid`） | 权限绕过风险 | 已修复 |
| TRIAL-005 | 权限/审计 | P1 | 报销创建接口允许提交任意状态（如直接写入 `approved`） | 权限绕过风险 | 已修复 |
| TRIAL-006 | SQL兼容性 | P0 | `GET /api/assets/changes` 字段歧义（`note/operator`）导致 500 | 阻断S5 | 已修复并回归通过 |
| TRIAL-007 | SQL兼容性 | P0 | `GET /api/assets/ledger` 在 `ONLY_FULL_GROUP_BY` 下报错 | 阻断S6/导出 | 已修复并回归通过 |
| TRIAL-008 | 数据初始化 | P1 | `POST /books` 时科目导入存在 `balance_direction` 空值失败 | 账套初始化不完整 | 已修复并回归通过 |

## 4. 修复清单
| 修复项 | 说明 | 影响模块 | 代码位置 |
|---|---|---|---|
| 强制审批操作必须有 operator | 付款/报销审批、驳回、执行要求 operator 不为空 | 付款/报销 | `app/services/payment_service.py`, `app/services/reimbursement_service.py` |
| 限制创建状态与修正返回状态 | 创建时仅允许 `draft/pending`，更新返回数据库真实状态 | 付款/报销 | `app/services/payment_service.py`, `app/services/reimbursement_service.py` |
| 付款关键动作补审计日志 | submit/approve/reject 增加审计记录 | 付款/审计 | `app.py` |
| 资产变动列表字段消歧 | `ac.note/ac.operator` 等显式前缀，消除联表歧义 | 资产变动（S5） | `app/services/asset_change_service.py` |
| 资产台账聚合兼容 | `MAX(lc.change_type/change_date)` + `SUM` 兼容 `ONLY_FULL_GROUP_BY` | 资产台账（S6） | `app/services/asset_reports_service.py` |
| 科目方向兜底推断 | `balance_direction` 为空时按科目编码/类别/名称推断 | 账套初始化 | `app/services/standard_importer.py` |
| 试商用运行手册 | 标准化部署与冒烟路径 | 运行/交付 | `docs/STEP26_TRIAL_COMMERCIAL.md` |

## 5. 未修复但可接受项
- 无（本轮已覆盖高优先级权限/审计与数据正确性问题）

## 6. 2026-02-27 半量回归实测（P0/P1修复后）
### 6.1 半量回归总览
- 结果：PASS
- 回归范围：S5（资产变动列表）、S6（资产台账）、S4->S6 联动
- 数据上下文：`book_id=9`，资产 `REG_A_194349`（已计提）、`REG_B_194349`（无该期折旧分录）

### 6.2 S5 回归证据
- `POST /api/assets/9/change` -> `200`
  - 返回：`{"asset_id":9,"change_type":"TRANSFER","id":6}`
- `GET /api/assets/changes?book_id=9&asset_code=REG_A_194349` -> `200`
  - 返回摘要：`items_count=1`，首条记录包含 `note="half-reg"`、`operator="reg_admin_194349"`（字段正常）

### 6.3 S6 回归证据
- MySQL 模式：`SELECT @@sql_mode` 返回包含 `ONLY_FULL_GROUP_BY`
- `GET /api/assets/ledger?book_id=9&dep_year=2025&dep_month=2` -> `200`
  - 返回摘要：`items_count=2`
  - 已计提资产 `REG_A_194349`：`accumulated_depr=190.0`
  - 未计提资产 `REG_B_194349`：`accumulated_depr=0.0`，且资产未漏出

### 6.4 S4 -> S6 联动证据
- `POST /api/assets/depreciation` -> `201`
  - 返回摘要：`success_count=1`、`skipped_count=1`、`total_amount=190.0`
- 随后台账查询（S6）口径正确反映：
  - 已计提资产累计折旧同步到台账
  - 无折旧分录资产在按期间筛选后仍保留，累计折旧显示 `0.0`

### 6.5 回归结论
- 本轮回归范围内无 P0
- S5/S6 阻断项已清零
- 建议：已完成收尾文档补齐，可进入 STEP27

## 7. 商用稳定版发布前检查项
1. 数据库迁移与基础数据初始化完成（科目模板、角色与用户）
2. 核心流程回归通过（S1~S7）
3. 折旧、台账、报表导出数据口径抽样核对
4. 权限与审计日志可追溯（付款/报销/凭证/资产变动）
5. 导入/导出样例文件覆盖（银行流水、税务、报表导出）
6. 日志与异常监控（关键错误可定位）

## 8. STEP27 建议
- 基于 2026-02-27 半量回归实测结果，建议进入 STEP27 进行首批正式发布准备（发布说明、运维手册、监控与应急预案）
