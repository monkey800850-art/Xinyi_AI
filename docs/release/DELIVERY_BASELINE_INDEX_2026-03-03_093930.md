# Delivery Baseline Evidence Index

- timestamp: 2026-03-03_093930
- tag: delivery/cons-v1.0-2026-03-03_093930
- branch: main
- head: 3df34dbac7f471a72043ded377bc3625ac147c07

## Gates
- docs/release/gate_release_2026-03-03_093930.log
- docs/release/gate_consolidation.log
- docs/release/smoke.log
- docs/release/pytest_all.log

## Snapshots
- snapshots/cons/routes_snapshot_latest.json
- snapshots/cons/db_snapshot_latest.json

## Audit Whitepaper
- docs/audit/CONSOLIDATION_SYSTEM_WHITEPAPER.md

## Git status
On branch main
Your branch is ahead of 'origin/main' by 62 commits.
  (use "git push" to publish your local commits)

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/release/CONS_BASELINE_2026-03-03_091241.md
	docs/release/DELIVERY_BASELINE_INDEX_2026-03-03_093930.md

nothing added to commit but untracked files present (use "git add" to track)

## Recent commits (last 30)
3df34db TASK-CONS-35-FIX: make gate_release reproducible (PYTHONPATH + latest snapshots)
c52bc66 TASK-CONS-34: generate consolidation system whitepaper
f5d70ac TASK-CONS-33: add release gate (contract enforcement layer)
39131b7 TASK-CONS-31 完成：系统回归与性能优化
1388dc8 TASK-CONS-30 完成：报表披露与审计包生成
8098931 TASK-CONS-29 完成：合并作业单与合并报表最终校验与审批流
4100f5b TASK-CONS-28 完成：合并报表自动化生成与调节
148699d TASK-CONS-27 完成：合并范围与口径配置
d03ca13 TASK-CONS-26 完成：审计日志与权限控制
f5e7df3 TASK-CONS-25 完成：报表模板与合并报表生成
279bccf TASK-CONS-24 完成：合并作业单与合并后余额层
b03b3c0 docs(step27): add release checklist for step27-a
95efa74 TASK-CONS-22 完成：NCI 动态计算
e5a4c93 TASK-CONS-21 完成：权益法核算引擎
a0f5ac7 feat: implement purchase date processing (PPA + goodwill + deferred tax)
dcfe03f feat: consolidation type engine for same_control / non_same_control
0db8eaa docs(release): add baseline v1.0 release log and rollback guide
c1e26cb feat: baseline consolidation engine updates and regression coverage
dc85cec feat: add consolidation type contract with auth audit and tests
c7e9b95 feat: adjustment_set status workflow and audited regeneration rules
a9485a4 feat: adjustment_set workflow (draft/reviewed/locked) with audited regeneration rules
bba4c26 feat: onboarding IC match generates draft eliminations (audited, idempotent)
472388a feat: onboarding-day intercompany match generates draft eliminations
ccdf4ae feat: consolidation NCI structure and disclosure contract
92bc6b1 feat: consolidation control decision contract and tests
0df42bb feat: consolidation ownership contract with auth gate and audit
42e6e21 feat: parameters drive default scope for consolidation trial balance
420eb0b feat: manual consolidation eliminations and after_elim trial balance
5beca04 feat: enforce effective member scope for consolidation trial balance
6c32a2a feat: onboarding member join with auth gate and audit log
