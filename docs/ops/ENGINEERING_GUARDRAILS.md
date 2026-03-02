# Engineering Guardrails

## 1) Repository Hygiene
- Ban repository noise: `*:Zone.Identifier`, `_selfcheck/`, `_health/`, `*.bak`, `*.save`, `*~`, and accidental header-like filenames.
- `git status -sb` must remain readable and attributable before any merge/release decision.
- Any noise detected by ops checks must be cleaned before continuing regression claims.

## 2) Commit Workflow
- Keep commits small and single-topic.
- Commit message prefixes: `chore`, `test`, `fix`, `feat`.
- Do not mix unrelated refactors with bugfix or test baseline commits.

## 3) Test Rules
- No absolute filesystem paths in tests.
- Use shared test factories under `tests/_helpers/*` (example: book payload factory).
- Default pytest run uses `--maxfail=1`.
- Keep terminal evidence with `tee` for reproducible review.

## 4) DB / Migration Rules
- Any schema change requires migration + test updates.
- Validate table reality with `SHOW CREATE TABLE` and keep tests/code aligned.
- Avoid ambiguous dual-field semantics without explicit compatibility handling.

## 5) CLI Execution Rules
- Batch edits and verification are executed via CLI scripts.
- Every execution report must include:
  - `git show --stat`
  - pytest summary (pass/fail/error counts)
