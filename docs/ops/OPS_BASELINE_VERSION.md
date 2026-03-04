# OPS Baseline Version

- version: ops-stable-20260304-a3ce8e4
- date: 2026-03-04 13:24 (+0800)
- repo: /home/x1560/Xinyi_AI
- branch: main
- head: a3ce8e4

## Included capabilities
- Local gates:
  - gate_secrets (+ patterns)
  - gate_hygiene (+ patterns)
  - pre-commit via hooksPath (.githooks)
- CI gates:
  - gate-secrets
  - ci-hygiene
  - ci-smoke
  - ci-uat
  - ci-release-gate
- Ops entrypoints:
  - start_app / stop_app / restart_app
  - health_check
  - gate_all / doctor
  - project_state (window recovery)
  - web_audit_pack (+ INDEX.md)
- UAT runners:
  - uat_run (anonymous)
  - uat_auth_run (cookie reuse, ops.env)

## Standard evidence locations
- gate: /tmp/xinyi_gate_<ts>/
- doctor: /tmp/xinyi_doctor_<ts>/
- audit: /tmp/xinyi_audit_<ts>/

## Window wake-up phrase


## Daily operating procedure
1) bash scripts/ops/project_state.sh
2) bash scripts/ops/gate_all.sh
3) bash scripts/ops/doctor.sh
4) bash scripts/ops/web_audit_pack.sh
