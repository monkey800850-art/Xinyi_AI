# Ops Safety Kit (OSK)

Portable safety/quality gate kit for Git projects.

## Included
- Local pre-commit gate wiring via `hooksPath`
- `gate_all.sh` entrypoint (secrets + optional gates)
- `doctor.sh` evidence runner
- Optional packaged scripts copied from `scripts/ops`
- GitHub Actions template: `ci/github/gate-secrets.yml`

## Install
```bash
bash ops-safety-kit/install.sh
```

## Uninstall
```bash
bash ops-safety-kit/uninstall.sh
```

## Run
```bash
bash ops-safety-kit/scripts/gate_all.sh
bash ops-safety-kit/scripts/doctor.sh
```

## Evidence
- Install: `/tmp/evidence_osk_install.txt`
- Uninstall: `/tmp/evidence_osk_uninstall.txt`
- Doctor pack: `/tmp/osk_run_<ts>/INDEX.md`

## Porting to another repo
1. Copy `ops-safety-kit/` into target repo root.
2. Ensure scripts in `ops-safety-kit/scripts/` match target project.
3. Run `bash ops-safety-kit/install.sh`.
4. Optionally copy `ops-safety-kit/ci/github/gate-secrets.yml` into `.github/workflows/`.
