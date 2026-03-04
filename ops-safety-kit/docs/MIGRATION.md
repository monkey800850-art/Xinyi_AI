# OSK Migration Notes

- This kit is packaging-only; it does not change business logic.
- Existing `scripts/ops` are not removed.
- You can gradually switch local/CI references from `scripts/ops` to `ops-safety-kit/scripts`.

## Environment gotchas (from Xinyi_AI hardening)

### 1) Do NOT assume `~` points to the real home
Some execution environments map `~` to non-standard paths. OSK scripts MUST anchor to repo root via:
- `git rev-parse --show-toplevel`

### 2) Proxy / no_proxy
- Prefer curl with `--noproxy '*'` when running local checks.
- Python urllib fallback in OSK disables proxies by default (ProxyHandler({})).

### 3) Restricted network environments (Errno 1: Operation not permitted)
Some sandboxes block outbound socket/connect even to localhost.
OSK health_check will classify this as `NETWORK_RESTRICTED`.

Recommended:
- CI / normal dev: `OSK_HC_STRICT=1` (strict)
- Restricted sandbox: `OSK_HC_STRICT=0` (degrade, still produces evidence)

### 4) Profiles
- Default local: `OSK_PROFILE=local` runs secrets + hygiene only (portable)
- Enable DB/service bound smoke only when environment supports it:
  - `OSK_ENABLE_DB_GATES=1`
  - `OSK_ENABLE_RELEASE_GATES=1`
