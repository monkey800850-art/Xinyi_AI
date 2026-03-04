# UAT Entry Gate (Xinyi_AI)

## P0 (must pass)
- App can start/restart via `scripts/ops/restart_app.sh`
- `scripts/ops/health_check.sh` PASS
- Local secrets gate installed (`scripts/ops/install_githooks.sh` done)
- CI required checks PASS on main (gate-secrets, ci-smoke, ci-release-gate, ci-hygiene if present)

## P1 (should pass)
- `scripts/ops/gate_all.sh` produces `/tmp/xinyi_gate_<ts>/INDEX.md` with PASS for health_check
- `scripts/ops/doctor.sh` produces `/tmp/xinyi_doctor_<ts>/INDEX.md`
- Logs are standardized (var/log or configured LOG_PATH) and health_check shows LOG_PATH

## P2 (nice to have)
- Authenticated smokes runnable via `var/run/ops.env` (no manual export)
- Web audit pack exists (`scripts/ops/web_audit_pack.sh`)
- Ops freeze tag created and pushed

## Evidence conventions
- gate pack: `/tmp/xinyi_gate_<ts>/`
- doctor pack: `/tmp/xinyi_doctor_<ts>/`
- audit pack: `/tmp/xinyi_audit_<ts>/`
