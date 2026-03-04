#!/usr/bin/env bash
set -euo pipefail

echo "[gate] hygiene scan..."

# staged file list
staged="$(git diff --cached --name-only || true)"

fail() { echo "[FAIL] $*"; exit 1; }

# (A) Block Zone.Identifier artifacts
if echo "$staged" | rg -n ':[Zz]one\.Identifier' >/dev/null; then
  echo "$staged" | rg -n ':[Zz]one\.Identifier' || true
  fail "staged contains Zone.Identifier artifacts"
fi

# (B) Block .env (any)
if echo "$staged" | rg -n '(^|/)\.env(\.|$)' >/dev/null; then
  echo "$staged" | rg -n '(^|/)\.env(\.|$)' || true
  fail "staged contains .env files (must not be committed)"
fi

# (C) Block key/cert-like files by name
if echo "$staged" | rg -n '\.(pem|key|p12|pfx|crt|cer|der)$' >/dev/null; then
  echo "$staged" | rg -n '\.(pem|key|p12|pfx|crt|cer|der)$' || true
  fail "staged contains key/cert-like files"
fi

echo "[OK] hygiene scan passed."
