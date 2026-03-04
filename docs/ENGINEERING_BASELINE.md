# Engineering Baseline (Xinyi_AI)

> Purpose: make the project operable, auditable, and window-switch-safe.

## 1. One-command entries

### 1.1 Recover project context (for window switching)
Run:
- `bash scripts/ops/project_state.sh`

### 1.2 Start / stop / restart
- Start: `bash scripts/ops/start_app.sh`
- Stop: `bash scripts/ops/stop_app.sh`
- Restart: `bash scripts/ops/restart_app.sh`

### 1.3 Gates & evidence pack
- Gate pack (local): `bash scripts/ops/gate_all.sh`
  - Output: `/tmp/xinyi_gate_<ts>/INDEX.md`

### 1.4 Doctor (full ops suite)
- `bash scripts/ops/doctor.sh`
  - Output: `/tmp/xinyi_doctor_<ts>/INDEX.md`

## 2. Local commit enforcement (must-run secrets gate)
Install hooks:
- `bash scripts/ops/install_githooks.sh`

Mechanism:
- `.githooks/pre-commit` calls `scripts/ops/gate_secrets.sh`
- Local `--no-verify` can bypass hooks, but CI gates still block at server side

## 3. CI enforcement
Workflows:
- `gate-secrets` (push/PR) - blocks token/key patterns in diff
- `ci-smoke` (push/PR) - starts app + health_check + dashboard smoke (anonymous)
- `ci-release-gate` (push/PR) - release-grade gate, recommended as required check

Branch protection recommendation:
- Require status checks to pass before merging
- Select at least: `ci-release-gate` (optionally add `gate-secrets`, `ci-smoke`)

## 4. Evidence conventions
- Gate pack: `/tmp/xinyi_gate_<ts>/`
- Doctor pack: `/tmp/xinyi_doctor_<ts>/`
- Web audit pack: `/tmp/xinyi_audit_<ts>/`

Each pack contains:
- `INDEX.md` (entrypoint)
- `evidence_*.txt` (step logs)

## 5. Local ops env (authenticated smokes)
Template:
- `docs/ops/OPS_ENV.example`

Local file (DO NOT COMMIT):
- `var/run/ops.env`

## 6. Window wake-up phrase (copy/paste)
Use this exact sentence in a new ChatGPT window:

`加载工程上下文：Xinyi_AI 项目，继续 CLI 任务卡。`

## 7. Daily operator flow (recommended)
1. `bash scripts/ops/project_state.sh`
2. `bash scripts/ops/restart_app.sh`
3. `bash scripts/ops/gate_all.sh`
4. Before release/merge: ensure Actions `gate-secrets`, `ci-smoke`, `ci-release-gate` all PASS
5. If needed, archive evidence via `bash scripts/ops/web_audit_pack.sh`
