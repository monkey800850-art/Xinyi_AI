# UAT Exit Gate (Engineering-UAT Preparation)

This gate defines when we can exit the "engineering UAT preparation" phase and enter business UAT.

## P0 (must pass)
- Local ops entrypoints exist and runnable:
  - `scripts/ops/start_app.sh`, `stop_app.sh`, `restart_app.sh`
  - `scripts/ops/health_check.sh`
  - `scripts/ops/gate_all.sh`, `scripts/ops/doctor.sh`, `scripts/ops/project_state.sh`
- Local pre-commit hook installed (hooksPath = `.githooks`) and blocks secrets
- Latest `gate_all` pack shows:
  - `gate_secrets: PASS`
  - `gate_hygiene: PASS` (if present)
  - `health_check: PASS`
  - `smoke_ui: DONE` (or SKIP only if script missing)
- Latest `doctor` pack created successfully (INDEX.md exists)

## P1 (should pass)
- Anonymous UAT runner passes:
  - `scripts/ops/uat_run.sh` PASS
- Authenticated UAT runner passes (if ops.env exists):
  - `scripts/ops/uat_auth_run.sh` PASS
- Web audit pack created and contains consolidated INDEX.md

## P2 (nice to have)
- Ops freeze tag created and pushed
- Branch protection enabled with required CI checks

## Evidence sources
- gate pack: `/tmp/xinyi_gate_<ts>/INDEX.md`
- doctor pack: `/tmp/xinyi_doctor_<ts>/INDEX.md`
- audit pack: `/tmp/xinyi_audit_<ts>/INDEX.md`
