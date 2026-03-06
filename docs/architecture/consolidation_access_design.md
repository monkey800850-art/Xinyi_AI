# Consolidation Access Authorization Design

## 模块名称
合并授权接入（Consolidation Access Authorization）

## 业务目标
在未合并前，各租户账套默认完全隔离、互不可见。
在合并授权生效后，被合并公司账套同时：
1. 授权母公司在限定范围内访问
2. 纳入母公司虚拟合并体系

## 核心原则
1. 默认绝对隔离
2. 授权必须来自被合并方
3. 授权生效 = 纳入合并体系（原子动作）
4. 跨租户访问必须留痕
5. 授权可到期、可撤销

## 推荐主状态
- draft
- pending
- approved
- active
- revoked
- expired

## active 状态含义
active 不是“批准结束”，而是：
- 访问授权已生效
- 已纳入虚拟合并主体
二者同时成立

## 建议核心字段
- id
- authorization_no
- parent_tenant_id
- parent_book_id
- child_tenant_id
- child_book_id
- virtual_entity_id
- grant_mode
- effective_from
- effective_to
- status
- approval_doc_no
- approval_doc_name
- created_by
- approved_by
- revoked_by
- created_at
- updated_at

## grant_mode 建议
- read_only
- consolidation_work
- controlled_edit

## API 草案
- GET  /api/consolidation/access-grants
- POST /api/consolidation/access-grants
- GET  /api/consolidation/access-grants/<grant_id>
- POST /api/consolidation/access-grants/<grant_id>/approve-and-activate
- POST /api/consolidation/access-grants/<grant_id>/revoke

## 本阶段说明
当前阶段仅建立服务骨架、路由骨架与文档，不落库、不改现有合并逻辑。
