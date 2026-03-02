# 合并治理与报表引擎架构设计方案（总纲）

## 0. 文档定位与边界

### 0.1 文档定位
- 本文档是“合并治理与报表引擎”的**架构与实施基线**，用于后续 CLI/Web 体检逐项对照。
- 本文档不是“已完成功能说明书”，文中所有能力均标注“现状已具备”或“待建设”。
- 本文档覆盖：治理模型、作业流程、规则引擎、报表模板引擎、权限边界、阶段实施与验收。

### 0.2 当前系统已完成前置能力（现状依据）
- 多账套管理（STEP2）：
  - 代码路径：`app/services/book_service.py`、`templates/system_books.html`、`static/js/system_books.js`
  - 关键接口：`/api/books`（`app.py`）
- 建账初始化前台（STEP3）：
  - 代码路径：`templates/system_book_init.html`、`static/js/system_book_init.js`
  - 关键接口：`POST /books`、`GET /api/books/<book_id>/init-integrity`（`app.py`）
- 建账时法人/非法人天然合并关系前置（STEP3-BACKFILL）：
  - 代码路径：`app/services/book_service.py`（`account_book_type`、`parent_legal_book_id`、天然组合并成员绑定）
  - 关系表：`legal_entities`、`consolidation_groups`、`consolidation_group_members`
- 关系管理前台产品化（STEP4-1）：
  - 代码路径：`templates/system_consolidation.html`、`static/js/system_consolidation.js`
  - 关键接口：`/api/consolidation/*`、`/api/consolidation/virtual-entities/*`（`app.py`）
- 余额表合并口径与树表一体展示（STEP4-2）：
  - 代码路径：`app/services/trial_balance_service.py`、`templates/trial_balance.html`、`static/js/trial_balance.js`
  - 关键接口：`GET /api/trial_balance`（支持 `book_id/consolidation_group_id/virtual_entity_id`）

### 0.3 当前未完成能力边界（必须明确）
- 未形成“合并授权台账”与“授权有效期校验”的治理闭环（当前关系纳入更多是模型层与管理层，不等于法定授权完备）。
- 未形成“合并参数台账”（股权比例、控制类型、全并标记、纳入范围、有效期）作为引擎输入。
- 未形成“集团内交易标记”标准字段与流水化沉淀（凭证/分录层）作为自动抵销前提。
- 未形成“抵销规则模板引擎”（规则版本、条件表达、分录模板、建议生成、审核流）。
- 未形成“合并后余额层 + 四大报表模板引擎”完整链路。
- 未形成“管理汇总口径”与“法定合并报表”在页面、接口、导出层的强约束提示体系。

### 0.4 术语定义（统一口径）
- 法人账套：具备独立法人地位的会计核算账套；默认与其他法人账套数据隔离。
- 非法人账套：不具备独立法人地位但需独立核算的账套；在本系统中作为“天然合并单元”纳入其所属法人口径。
- 虚拟主体：为管理汇总或授权合并而定义的逻辑合并容器，不天然拥有跨法人读取权限。
- 管理汇总口径：用于经营分析与内部管理汇总的口径，不直接等同法定披露口径。
- 法定合并口径：满足授权、参数、抵销、审计留痕等法定治理条件后形成的报表口径。
- 合并作业单（Job）：一次可追溯的合并执行单元，包含期间、范围、口径、状态、执行日志与产物。
- 合并前余额：在合并范围确定后、抵销前生成的汇总余额结果。
- 合并后余额：抵销分录审核入账后形成的余额结果，是四大报表取数基础。
- 抵销分录建议：由规则引擎根据模板与条件生成的候选抵销分录，仅可作为建议，需人工审核确认。

---

## 1. 核心业务法则（固化）

1. 法人账套间默认独立，不能天然合并。
2. 法人纳入虚拟合并主体必须有法定程序授权（合同/决议/审批链），无授权不得纳入。
3. 非法人账套是“天然合并单元”，默认纳入所属法人口径，不等同普通成员挂接。
4. 软件/平台默认无权读取未授权外单位数据，系统调用范围必须受授权与纳入状态约束。
5. 当前阶段边界：
   - 管理汇总口径：用于经营分析、管理看板、内部复盘。
   - 法定合并报表：需满足治理、授权、参数、抵销、审计留痕等法定要求。
   - 两者不可混同，页面文案与导出抬头必须可区分。

---

## 2. 合并治理数据模型设计

> 说明：本节包含“已存在真源”与“待新增模型”。所有新增表均为架构设计目标，不代表当前已实现。

### 2.1 A. 合并授权/纳入表（待新增）

#### 表：`consolidation_authorizations`（建议）
- 用途：记录“纳入某合并主体”是否合法授权、授权范围与有效期。
- Source of Truth：本表是授权状态唯一真源（授权是否生效以本表判定）。
- 关键字段（建议）：
  - `id` PK
  - `authorization_code` 授权单号（唯一）
  - `virtual_entity_id` 虚拟合并主体ID
  - `authorized_legal_entity_id` 被授权纳入法人实体ID
  - `authorization_type`（合同/董事会决议/监管批复/其他）
  - `approval_status`（draft/pending/approved/rejected/revoked）
  - `effective_from`、`effective_to`
  - `document_ref`（外部文件编号或存证ID）
  - `signed_at`、`approved_by`
  - `status`、`is_enabled`
  - `created_by`、`created_at`、`updated_by`、`updated_at`
- 作为抵销引擎输入字段：`virtual_entity_id`、`authorized_legal_entity_id`、`effective_from/to`、`approval_status`。

### 2.2 B. 合并参数表（待新增）

#### 表：`consolidation_parameters`（建议）
- 用途：沉淀纳入范围与计算参数，作为年度合并引擎参数输入。
- Source of Truth：参数以该表当前生效版本为准。
- 关键字段（建议）：
  - `id` PK
  - `virtual_entity_id`
  - `member_entity_id`
  - `ownership_ratio` 持股比例
  - `voting_ratio` 表决权比例
  - `control_type`（control/joint_control/significant_influence/no_control）
  - `consolidation_method`（full/equity/proportionate/exclude）
  - `full_consolidation_flag`（0/1）
  - `include_scope`（all/fs_only/bs_only/custom）
  - `scope_config_json`（科目/业务域粒度范围）
  - `effective_from`、`effective_to`
  - `version_no`、`version_status`（draft/active/archived）
  - `approved_by`、`approved_at`
- 作为抵销引擎输入字段：`control_type`、`consolidation_method`、`ownership_ratio`、`include_scope`、`scope_config_json`、`effective_from/to`。

### 2.3 C. 主体关系真源与映射（现状 + 规划）

#### 现状真源（已存在）
- `legal_entities`：主体实体真源（法人/非法人实体映射）。
- `consolidation_groups`：合并组/天然组/虚拟组容器。
- `consolidation_group_members`：成员挂接真源（包含成员状态）。
- 代码依据：`app/services/consolidation_manage_service.py`、`app/services/consolidation_service.py`、`app/services/book_service.py`。

#### 规划增强（待新增）
- `consolidation_scope_snapshots`（建议）：每次合并作业固化当期范围快照，避免“事后范围漂移”。
  - 核心字段：`job_id`、`scope_hash`、`scope_json`、`generated_at`。

### 2.4 D. 集团内交易标记策略（待新增）

#### 表：`voucher_line_group_tags`（建议）
- 用途：在凭证分录层标记“集团内交易”，作为自动抵销规则触发前提。
- Source of Truth：以分录标记表为准，不从文本推断作为正式口径。
- 关键字段（建议）：
  - `id` PK
  - `voucher_id`、`voucher_line_id`
  - `book_id`
  - `counterparty_entity_id` 对手方实体ID
  - `intragroup_flag`（0/1）
  - `transaction_type`（internal_sale/internal_loan/internal_service/internal_investment/...）
  - `reference_doc_no`
  - `tag_source`（manual/import/rule_infer）
  - `tag_confidence`（0-1，规则推断时可用）
  - `effective_period`
  - `status`、`is_enabled`
- 作为抵销引擎输入字段：`intragroup_flag`、`transaction_type`、`counterparty_entity_id`、`effective_period`。

### 2.5 E. 审计与操作日志要求（现状 + 规划）

#### 现状
- `audit_logs` 已用于系统操作日志，接口在 `app/services/audit_service.py`、`app/services/system_service.py`。

#### 规划要求
- 对以下操作必须写审计日志并可追溯：
  - 授权创建/变更/撤销
  - 合并参数版本启用/停用
  - 成员纳入/停用
  - 抵销分录建议生成/人工确认/作废
  - 报表生成与导出
- 建议字段补充：`before_json`、`after_json`、`reason_code`、`request_trace_id`。

### 2.6 现状数据模型映射表（现有表 -> 规划表）

| 现有表/对象（当前） | 角色（当前） | 规划表/对象（目标） | 关系说明 |
|---|---|---|---|
| `books` | 账套主数据 | `books`（沿用） | 继续作为账套主数据真源，不承载授权判定。 |
| `legal_entities` | 法人/非法人实体映射 | `legal_entities`（沿用） | 继续作为实体真源，供授权与参数表引用。 |
| `consolidation_groups` | 合并容器（天然组/虚拟组） | `consolidation_groups`（沿用） | 继续作为分组容器，不替代授权台账。 |
| `consolidation_group_members` | 分组成员关系 | `consolidation_group_members`（沿用） | 继续描述成员挂接关系，授权有效性由新授权表控制。 |
| `virtual_entities` | 虚拟主体主数据 | `virtual_entities`（沿用） | 继续作为虚拟主体定义，与授权/参数表形成一对多关系。 |
| `audit_logs` | 操作审计日志 | `audit_logs`（沿用+增强字段） | 治理动作继续落审计，后续补齐 before/after 等字段。 |
| `trial_balance` 查询结果（服务层对象） | 汇总余额结果 | `consolidation_jobs` + `consolidation_job_results`（规划） | 从“即时查询”升级为“作业化产物”可追溯。 |
| 无（当前缺失） | — | `consolidation_authorizations`（新增） | 作为纳入授权真源，控制未授权不可见。 |
| 无（当前缺失） | — | `consolidation_parameters`（新增） | 作为股权/控制/纳入范围参数真源。 |
| 无（当前缺失） | — | `consolidation_jobs`（新增） | 作业单状态机与执行入口。 |
| 无（当前缺失） | — | `consolidation_job_logs`（新增） | 作业级日志与失败原因追溯。 |
| 无（当前缺失） | — | `voucher_line_group_tags`（新增） | 集团内交易标记，为规则建议引擎提供输入。 |
| 无（当前缺失） | — | `elimination_rule_templates`（新增） | 抵销规则模板与版本管理。 |
| 无（当前缺失） | — | `report_templates` / `report_template_lines`（新增） | 四大报表模板与映射配置。 |

---

## 3. 合并作业流程设计

### 3.1 合并日合并（MVP优先）

#### 目标
- 先打通“可控、可审、可回放”的合并日作业闭环。

#### 流程
1. 确定范围（主体 + 期间 + 生效授权 + 生效参数）。
2. 生成汇总余额表（合并前）。
3. 手工编制抵销分录（人工输入/导入）。
4. 审核并记账（抵销分录入账到合并工作底稿域）。
5. 生成合并后余额。
6. 输出合并日底稿/报表（管理汇总口径）。

#### 当前与未来边界
- 当前已有：范围选择与余额汇总基础（`trial_balance_service.py`）。
- 待建设：抵销分录作业域、审核流、合并后余额层、底稿产物。

### 3.2 年度合并报表（增强版）

#### 目标
- 在MVP基础上引入规则模板驱动，产出“自动建议 + 人工确认”的年度作业能力。

#### 流程
1. 确定范围（同上）。
2. 自动生成汇总余额（可批量期间）。
3. 根据抵销规则模板生成抵销建议分录。
4. 人工审核确认（逐条或批量）。
5. 生成合并后余额。
6. 生成四大报表（法定模板版本）。

### 3.3 软件内统一处理顺序（强制）
- 确定范围 -> 汇总余额 -> 抵销分录 -> 审核记账 -> 合并后余额 -> 四大报表。

---

## 4. 抵销规则引擎与模板预置架构

### 4.1 A. 规则框架（模型与执行思路）

#### 规则模型（建议）
- `elimination_rule_templates`
  - `rule_code`、`rule_name`、`category`、`priority`
  - `condition_expr`（条件表达式/DSL）
  - `subject_mapping_json`
  - `entry_template_json`（借贷分录模板）
  - `auto_suggest_flag`
  - `version_no`、`version_status`、`effective_from/to`
- `elimination_rule_runs`
  - `job_id`、`rule_id`、`input_scope_hash`、`result_summary_json`
- `elimination_entry_suggestions`
  - `job_id`、`rule_id`、`voucher_draft_json`、`confidence`、`review_status`

#### 执行思路
1. 基于作业范围与期间提取候选交易与余额。
2. 按规则优先级匹配条件表达式。
3. 生成建议分录草稿与解释信息。
4. 人工审核后转正式抵销分录。

### 4.2 B. 预置模板范围（分阶段）

#### MVP核心类别（本期架构必须预留）
- 内部往来抵销
- 内部销售与成本抵销
- 内部投资（基础）
- 内部借款与利息（基础）

#### 后续扩展类别（暂不要求本期实现）
- 内部固定资产未实现损益
- 内部存货未实现利润递延
- 递延所得税相关抵销
- 外币折算差额与少数股东权益专项规则

### 4.3 C. 自动/手工边界
- 合并日：优先手工抵销（保证可控性与解释性）。
- 年度合并：支持自动建议，但必须人工审核确认后生效。

---

## 5. 四大报表模板引擎架构

### 5.1 报表范围
- 资产负债表
- 利润表
- 现金流量表（先基础后增强）
- 所有者权益变动表（先结构后明细）

### 5.2 模板定义层（待新增）
- 建议表：`report_templates`、`report_template_lines`、`report_template_mappings`
- 核心能力：
  - 行项目结构树
  - 科目/规则映射
  - 准则版本（企业会计准则版本）
  - 模板版本（v1/v2/...）

### 5.3 报表生成层（待新增）
- 输入：合并后余额层（非原始余额）。
- 输出：标准报表数据集 + 导出数据集。
- 约束：报表生成逻辑与模板定义解耦，禁止在代码里硬编码行项目。

### 5.4 准则版本与模板版本管理
- 模板版本不可覆盖更新，需版本化发布与停用。
- 每次报表生成记录使用的模板版本、参数版本、规则版本。

---

## 6. 权限、授权与数据边界设计

### 6.1 授权前不可见原则
- 未生效授权的主体，不可出现在可选范围，不可查询，不可导出。

### 6.2 授权生效后的查询边界
- 查询范围 = 用户权限范围 ∩ 授权生效范围 ∩ 参数有效范围。

### 6.3 软件运维与业务数据边界
- 运维角色可管理系统可用性，不等于可读取任意业务数据明细。
- 业务访问必须走业务授权链路。

### 6.4 审计日志与留痕要求
- 关键治理行为必须留痕，支持“谁在何时以何原因做了什么变更”的审计追踪。

### 6.5 页面/接口提示文案要求
- 必须明确“当前视角：管理汇总口径/法定合并口径”。
- 必须明确“查询范围受授权与纳入状态限制”。
- 禁止出现“平台可随时读取所有账套”的误导性文案。

---

## 7. 分阶段实施方案（Phase A ~ E）

### 7.1 Phase A：治理模型与参数层（先方案+模型+页面MVP）
- 目标：建立授权、参数、范围快照的数据基础与管理入口。
- 前置条件：
  - STEP2~STEP4 基线稳定可回归。
  - 主体关系管理接口可用（`/api/consolidation/*`）。
- 核心交付：
  - 授权表/参数表/范围快照表模型与DDL
  - 管理页面MVP（授权登记、参数维护、生效状态）
  - 权限校验与审计留痕
- 非目标：自动抵销、四大报表生成。
- 验收标准（高层）：
  - 可登记并查询授权与参数；
  - 查询能按生效范围过滤；
  - 审计日志可追溯增删改。

### 7.2 Phase B：合并日作业MVP（手工抵销）
- 目标：打通合并日作业闭环。
- 前置条件：Phase A 完成并上线。
- 核心交付：
  - 合并作业单（job）
  - 合并前余额快照
  - 手工抵销分录录入/审核/记账
  - 合并后余额层
- 非目标：规则自动建议。
- 验收标准：
  - 可完成一次完整合并日流程并重演；
  - 抵销分录与合并后余额可对账；
  - 底稿导出可审阅。

### 7.3 Phase C：规则模板引擎与自动抵销建议（年度）
- 目标：提升年度合并效率与一致性。
- 前置条件：Phase B 稳定，且分录层交易标记机制可用。
- 核心交付：
  - 规则模板管理
  - 规则执行器
  - 自动建议分录与人工确认流
- 非目标：全规则自动记账（仍保留人工确认）。
- 验收标准：
  - MVP四类模板可运行；
  - 建议分录可解释、可追溯；
  - 人工确认后入账链路稳定。

### 7.4 Phase D：四大报表引擎完善
- 目标：从合并后余额生成标准报表。
- 前置条件：Phase C 可稳定生成并确认抵销结果。
- 核心交付：
  - 报表模板定义引擎
  - 四大报表生成与导出
  - 模板版本管理
- 非目标：覆盖所有行业个性化报表。
- 验收标准：
  - 四大报表可按模板生成；
  - 模板版本可回溯；
  - 报表与合并后余额可勾稽。

### 7.5 Phase E：审计/授权/合规增强
- 目标：完成合规要求闭环。
- 前置条件：A-D 核心能力可用。
- 核心交付：
  - 精细化授权策略
  - 合规提示与拦截增强
  - 审计报表与追溯工具
- 非目标：替代企业法务流程本身。
- 验收标准：
  - 未授权访问可被拦截并可审计；
  - 合规检查项可批量体检；
  - 操作留痕满足内控抽查。

---

## 8. 风险与前置条件

### 8.1 已具备前置
- STEP2~STEP4 关系与余额汇总基础已具备（见 0.2 对应代码路径）。

### 8.2 仍需完成的前置
- 凭证查询链路进一步标准化（作业域与合并域隔离）。
- 序时账导入与真实业务数据联调验收。
- 明细账/辅助账主体口径扩展与一致性校验。
- 授权与参数表模型落地。

### 8.3 技术风险
- 历史库结构漂移导致兼容分支复杂（当前已有动态列兼容写法，后续可能继续增加）。
- 多版本模板/规则并行时的结果一致性与可追溯性要求高。

### 8.4 业务风险
- 授权信息不完整导致误纳入或漏纳入。
- 参数缺失（如控制类型）导致自动建议偏差。

### 8.5 合规风险
- 对“平台是否可读取外单位数据”的误解可能引发合规争议，需在界面、接口、导出中持续强化边界说明。

---

## 9. 体检对照指引（CLI/Web）

### 9.1 对照方法
- 以本总纲章节为一级维度（0~9），逐章输出：已完成/部分完成/未完成。
- 每章必须给出：
  - 现状证据（代码路径/接口/表）
  - 阻塞点
  - 偏离项（与本方案不一致处）
  - 下一张任务卡建议

### 9.2 每次体检输出模板
- `章节状态`：已完成/部分完成/未完成
- `证据路径`：至少1条代码路径或接口
- `阻塞点`：是否存在前置缺失
- `偏离方案`：是否出现越阶段开发或边界混淆
- `建议任务卡`：下一步最小闭环任务

### 9.3 与本仓库现有实现映射（用于快速体检）
- 关系治理入口：`templates/system_consolidation.html`、`static/js/system_consolidation.js`、`app/services/consolidation_manage_service.py`
- 合并口径余额表：`app/services/trial_balance_service.py`、`templates/trial_balance.html`、`static/js/trial_balance.js`
- 账套与建账：`app/services/book_service.py`、`templates/system_book_init.html`
- 审计日志：`app/services/audit_service.py`、`app/services/system_service.py`
