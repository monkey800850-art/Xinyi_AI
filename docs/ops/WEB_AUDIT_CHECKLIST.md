# WEB Audit Checklist (Read-only)

## Principles
- Read-only: no code changes, no commits (unless explicitly in a task), no PRs.
- Evidence-first: all checks must produce artifacts.

## Baseline
- Repo:
- Branch:
- HEAD:
- Date/Time:
- Environment (WSL/Container/etc):
- Service URL:

## A) Commit/Diff (Secrets)
- Commit ID:
- Files changed count:
- Files list:
- Manual diff keywords check: PASS/FAIL
- Repo search keywords check (local rg or GitHub search): PASS/FAIL
- Notes:

## B) Runtime Browser Smoke
- ROOT / : status
- LOGIN: status
- USERS (anon): status
- USERS (auth): status
- DASH (anon/auth): status
- Leak check (debug/traceback/env): PASS/FAIL

## C) Evidence index
- evidence_smoke_auth.txt:
- evidence_health_check.txt:
- evidence_smoke_dashboard.txt:
- commit diff snapshot:
- secret history scan:
