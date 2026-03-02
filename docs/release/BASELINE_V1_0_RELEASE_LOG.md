# BASELINE v1.0 发布日志

## 1. 发布信息
- 版本标签：`baseline-v1.0`
- 发布分支：`main`
- 基线提交：
  - `c1e26cb0b85dbf660a15661b179b83cb2aec2715`
  - message: `feat: baseline consolidation engine updates and regression coverage`
- 发布日期：`2026-03-03`

## 2. 本次变更摘要
- 合并引擎能力补齐（购买日、存货未实现利润、跨期转回、资产转让相关服务）。
- 合并调整集状态与生成规则增强（审阅/锁定流程联动）。
- 新增合并相关迁移脚本（收购事件、内部交易、递延税与滚动字段）。
- 新增回归测试：
  - `tests/test_arch18_purchase_method_generate.py`
  - `tests/test_arch19_up_inventory_generate.py`
  - `tests/test_arch20_up_inventory_deferred_tax.py`
  - `tests/test_arch21_up_inventory_reversal.py`
  - `tests/test_arch22_ic_asset_transfer_onboard.py`

## 3. 验证记录
- 全量自动化测试：
  - 命令：`PYTHONPATH=. pytest -q`
  - 结果：`57 passed`
- 合并 gate：
  - 命令：`scripts/ops/gate_consolidation.sh`
  - 结果：`PASS`
  - 关键检查：smoke、unit tests、`/system/consolidation`、`/api/consolidation/parameters`

## 4. 回滚点与回滚步骤
- 回滚点（本次基线）：`c1e26cb0b85dbf660a15661b179b83cb2aec2715`
- 回滚命令（生成反向提交）：
  - `git revert c1e26cb`
- 如包含标签回退：
  - 删除本地标签：`git tag -d baseline-v1.0`
  - 删除远程标签：`git push origin :refs/tags/baseline-v1.0`

## 5. 发布后检查
- `git ls-remote --heads origin main` 应可读取远程分支。
- `git push origin main` 推送成功后，再执行：
  - `git push origin baseline-v1.0`
- 推送完成后建议再次执行：
  - `bash scripts/ops/gate_consolidation.sh | tail -n 160`

