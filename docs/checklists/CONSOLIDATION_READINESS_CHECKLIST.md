# 合并治理与报表引擎体检对照清单

> 使用方式：CLI/Web 每次体检按本清单逐项输出“已完成/部分完成/未完成”，并附证据路径。

## 字段说明
- 检查项ID：唯一检查标识。
- 检查项描述：需要满足的能力目标。
- 所属阶段：对应 Phase A~E。
- 前置条件：进入本项检查前必须满足的依赖。
- 验收要点：判断完成与否的最小标准。
- 当前状态：`TODO` / `PARTIAL` / `DONE`。
- 证据示例：体检时应提供的接口/页面/表字段证据。
- 备注：补充约束与实现提示。

## A. 授权与纳入治理

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-A01 | 建立合并授权主表（授权单号、授权类型、审批状态） | Phase A | 关系模型可用 | 能新增/查询授权记录，单号唯一 | DONE | 表：`consolidation_authorizations(approval_document_number,approval_document_name,status)` | 已按 TASK-CONS-AUTH-01 落地首版结构 |
| CONS-A02 | 授权有效期控制（生效/失效） | Phase A | CONS-A01 | 查询时按有效期过滤纳入范围 | DONE | 接口：`GET /api/authorizations?virtual_subject_id=...` + 服务层按 `effective_start/effective_end` 校验 | 当前校验接入余额表合并查询 |
| CONS-A03 | 授权撤销流程 | Phase A | CONS-A01 | 撤销后范围立即失效并留痕 | DONE | 接口：`PATCH /api/authorizations/{id}/revoke` | 采用状态更新，未做物理删除 |
| CONS-A04 | 虚拟主体纳入法人前置授权校验 | Phase A | CONS-A01 | 未授权法人不可纳入虚拟主体 | DONE | 拦截错误码：`authorization_missing/suspended/revoked/expired` | 首批接入：`/api/trial_balance` 虚拟主体口径 |
| CONS-A05 | 授权变更审计留痕 | Phase E | 审计日志机制可用 | before/after、操作者、时间完整 | PARTIAL | 表：`audit_logs(module='consolidation_auth')` | 已记录 create/status 变更，before/after 细化待补强 |

## B. 合并参数表（股权比例、全并标记等）

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-B01 | 建立合并参数表（股权比例、控制类型、合并方式） | Phase A | 授权模型已定义 | 参数可按成员维护 | TODO | 表：`consolidation_parameters(ownership_ratio,control_type)` | 设计表：`consolidation_parameters` |
| CONS-B02 | 参数有效期与版本控制 | Phase A | CONS-B01 | 同一成员同一期间仅1个生效版本 | TODO | 唯一键：`(virtual_subject_id,parent,child,effective_from,version)` | 需要版本号 |
| CONS-B03 | 全并标记与纳入范围字段落地 | Phase A | CONS-B01 | 能驱动后续引擎输入 | TODO | 字段：`full_consolidation_flag/include_in_consolidation` | `full_consolidation_flag/include_scope` |
| CONS-B04 | 参数审批启用机制 | Phase A | CONS-B02 | draft不可用于正式作业 | TODO | 接口返回：`version_status=active` 才可执行作业 | 引入 `version_status` |
| CONS-B05 | 参数缺失拦截 | Phase B | CONS-B01 | 作业启动前提示缺失项并阻断 | TODO | 错误码：`consolidation_parameter_missing` | 作业前校验清单 |

## C. 凭证/分录集团内交易标记

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-C01 | 分录层集团内交易标记模型落地 | Phase B | 凭证模型可扩展 | 可记录对手方、交易类型、标记来源 | TODO | 表：`voucher_line_group_tags(counterparty_entity_id,transaction_type)` | 建议表：`voucher_line_group_tags` |
| CONS-C02 | 手工标记入口（凭证/分录） | Phase B | CONS-C01 | 用户可对分录打标与修改 | TODO | 页面：凭证分录编辑区出现“集团内交易标记”控件 | 初期手工优先 |
| CONS-C03 | 导入链路支持交易标记字段 | Phase C | CONS-C01 | 导入后标记字段可查可用 | TODO | 导入API响应含：`intragroup_flag` | 与导入映射联调 |
| CONS-C04 | 标记质量校验 | Phase C | CONS-C01 | 缺少对手方或类型时给出告警 | TODO | 校验结果：`tag_quality_warnings[]` | 质量阈值可配置 |

## D. 合并日作业（汇总余额、手工抵销）

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-D01 | 合并作业单（job）模型建立 | Phase B | A/B模块可用 | 可创建/关闭作业单 | TODO | 表：`consolidation_jobs(status,period_start,period_end)` | 包含期间与范围 |
| CONS-D02 | 作业范围快照固化 | Phase B | CONS-D01 | 作业启动时固化范围Hash与范围明细 | TODO | 字段：`scope_hash/scope_json` | 防止事后漂移 |
| CONS-D03 | 合并前汇总余额快照 | Phase B | CONS-D01 | 作业内可查看并复核合并前余额 | TODO | 接口：`GET /api/consolidation/jobs/{id}/pre-balance` | 来源：余额汇总能力 |
| CONS-D04 | 手工抵销分录录入 | Phase B | CONS-D01 | 支持新增/编辑/删除草稿分录 | TODO | 接口：`POST /api/consolidation/jobs/{id}/elimination-entries` | 人工主导 |
| CONS-D05 | 抵销分录审核确认 | Phase B | CONS-D04 | 未审核分录不得进入合并后余额 | TODO | 字段：`entry.review_status=approved` | 双人复核可选 |
| CONS-D06 | 合并后余额生成 | Phase B | CONS-D05 | 合并后余额可追溯到抵销分录 | TODO | 接口：`GET /api/consolidation/jobs/{id}/post-balance` | 勾稽校验 |
| CONS-D07 | 合并日底稿导出 | Phase B | CONS-D06 | 导出含范围、分录、合并后余额摘要 | TODO | 导出记录：`export_audit_logs.report_key=consolidation_job` | 用于审阅归档 |

## E. 年度合并（自动抵销建议）

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-E01 | 规则模板主表（版本化） | Phase C | Phase B稳定 | 模板可新增/启停/版本管理 | TODO | 表：`elimination_rule_templates(version_no,version_status)` | `elimination_rule_templates` |
| CONS-E02 | 条件表达与科目映射配置 | Phase C | CONS-E01 | 可配置匹配条件与映射关系 | TODO | 字段：`condition_expr/subject_mapping_json` | 支持解释输出 |
| CONS-E03 | 建议分录生成引擎 | Phase C | CONS-E01、C类标记可用 | 可按规则输出建议分录 | TODO | 接口：`POST /api/consolidation/jobs/{id}/suggestions:run` | 记录运行批次 |
| CONS-E04 | 建议分录人工审核流 | Phase C | CONS-E03 | 可逐条确认/驳回并记录原因 | TODO | 接口：`POST /api/consolidation/suggestions/{id}/review` | 审核后方可入账 |
| CONS-E05 | MVP四类规则模板预置 | Phase C | CONS-E01 | 内部往来/销售成本/投资/借款利息可跑通 | TODO | 模板代码：`INTRA_ARAP/INTRA_SALE/INTRA_INVEST/INTRA_LOAN` | 其余规则暂缓 |

## F. 四大报表模板与生成

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-F01 | 资产负债表模板定义层 | Phase D | 合并后余额可用 | 行结构+映射可配置 | TODO | 表：`report_templates(code='BS')` | 模板版本化 |
| CONS-F02 | 利润表模板定义层 | Phase D | 同上 | 可配置并可复用映射规则 | TODO | 表：`report_templates(code='PL')` | 与准则版本关联 |
| CONS-F03 | 现金流量表基础版模板 | Phase D | 同上 | 基础口径可生成 | TODO | 表：`report_templates(code='CF')` | 增强版后续 |
| CONS-F04 | 所有者权益变动表结构模板 | Phase D | 同上 | 先支持结构化输出 | TODO | 表：`report_templates(code='SOE')` | 明细后续 |
| CONS-F05 | 报表生成引擎（统一） | Phase D | F01~F04 | 能从合并后余额统一出报表 | TODO | 接口：`POST /api/consolidation/jobs/{id}/reports:generate` | 禁止硬编码口径 |
| CONS-F06 | 报表模板版本管理 | Phase D | F01~F05 | 同报表可保留多个历史版本 | TODO | 字段：`template_version/is_active` | 支持回溯 |
| CONS-F07 | 报表勾稽校验规则 | Phase D | F05 | 关键勾稽关系自动检查与告警 | TODO | 接口返回：`cross_checks[]` | 出具校验结果 |

## G. 审计与权限边界

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-G01 | 授权前不可见拦截 | Phase E | A模块上线 | 未授权主体不可选不可查 | TODO | 错误码：`authorization_not_granted` | 查询接口强校验 |
| CONS-G02 | 授权生效范围内可见 | Phase E | A模块上线 | 仅可见授权生效范围 | TODO | 响应字段：`authorized_scope_ids[]` | 需结合用户权限 |
| CONS-G03 | 运维与业务数据边界控制 | Phase E | 权限模型可扩展 | 运维角色不默认拥有业务明细读取权 | TODO | RBAC策略：`ops_role_no_business_read` | 合规重点 |
| CONS-G04 | 治理操作全链路审计 | Phase E | 审计日志机制可用 | 关键动作均有可追溯日志 | TODO | `audit_logs` 可按 `entity_type/entity_id` 追溯 | 含授权/参数/作业 |
| CONS-G05 | 导出行为审计 | Phase E | 报表导出可用 | 导出行为可追溯到人、时间、范围 | TODO | 表：`export_audit_logs(filters,file_name,operator)` | 与导出审计表联动 |

## H. 管理汇总口径 vs 法定合并报表边界提示

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-H01 | 页面层口径标签明确 | Phase A | 页面可迭代 | 页面显示“管理汇总/法定合并”标识 | TODO | 页面：`/reports/trial_balance` 顶部口径标签 | 防误读 |
| CONS-H02 | 接口响应包含口径标识 | Phase B | 作业接口可扩展 | 返回字段包含口径类型与版本 | TODO | 字段：`scope_type/report_basis/template_version` | 导出同口径 |
| CONS-H03 | 导出文件抬头口径声明 | Phase D | 报表导出可用 | 文件抬头明确口径与版本 | TODO | 导出标题：`法定合并/管理汇总 + 版本` | 合规要求 |
| CONS-H04 | 未达法定条件时限制“法定合并”入口 | Phase E | 授权参数校验可用 | 不满足条件时强提示并拦截 | TODO | 错误码：`statutory_gate_not_ready` | 防误用 |

## I. 文档基线与体检证据（本任务新增）

| 检查项ID | 检查项描述 | 所属阶段 | 前置条件 | 验收要点 | 当前状态 | 证据示例（接口/页面/表字段） | 备注 |
|---|---|---|---|---|---|---|---|
| CONS-I01 | 术语定义已落档（统一口径） | Phase A | 总纲文档存在 | 文档含法人/非法人/虚拟主体/口径/job等术语定义 | DONE | `docs/architecture/...PLAN.md` 0.4 节 | 对应 TASK-ARCH-CONS-01-DOC-FIX |
| CONS-I02 | 现状数据模型映射表已落档 | Phase A | 总纲文档存在 | 文档给出“现有表->规划表”映射 | DONE | `docs/architecture/...PLAN.md` 2.6 节 | 对应 TASK-ARCH-CONS-01-DOC-FIX |
| CONS-I03 | 清单证据示例列已补齐 | Phase A | 体检清单存在 | 所有分组条目具备证据示例列 | DONE | `docs/checklists/...CHECKLIST.md` 各表头 | 对应 TASK-ARCH-CONS-01-DOC-FIX |

---

## 体检执行说明（CLI/Web）

- 每次体检应至少输出：
  - 已完成项ID列表
  - 部分完成项ID列表（并说明缺口）
  - 未完成项ID列表
  - 阻塞项（缺前置条件）
  - 下一阶段建议任务卡（按优先级）
- 建议按阶段汇总完成率：
  - `Phase A 完成率 = A+B+H(部分)+I`
  - `Phase B 完成率 = C+D`
  - `Phase C 完成率 = E`
  - `Phase D 完成率 = F`
  - `Phase E 完成率 = G+H(合规拦截)`
