# Task Card SOP（真绿执行规范）

## 目标
避免 `python3 ... | tee ...` 吞掉失败码导致“假绿提交”。

## 必须遵守
- 任何关键 UAT / 校验命令，必须通过：
  - `scripts/ops/run_and_tee.sh`，或
  - `scripts/ops/taskcard.sh` 的 `run()` 执行。
- 禁止在任务脚本中直接写：`python3 ... | tee ...`。

## 推荐写法（任务卡片段）
```bash
set -e
source scripts/ops/taskcard.sh

run "python3 scripts/reports/uat_xxx.py" "evidence/TASK-XXX/uat.txt"
run "python3 -m compileall app scripts" "evidence/TASK-XXX/compileall.txt"
run "ops-safety-kit/scripts/gate_all.sh" "evidence/TASK-XXX/gate_all.txt"
```

## 快速自检
- 执行：`scripts/ops/check_no_tee_mask.sh`
- 期望：输出 `[OK] no masked python3|tee patterns under scripts/`
