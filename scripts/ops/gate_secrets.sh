#!/usr/bin/env bash
set -euo pipefail

echo "[gate] secrets scan..."

# 1) staged 文件名直接拦截
if git diff --cached --name-only | egrep -qi '(^|/)(ghp_[A-Za-z0-9]+|.*\.(pem|key|p12|pfx|crt|cer|der))$'; then
  echo "[FAIL] staged contains token/key/cert-like files."
  git diff --cached --name-only | egrep -i '(^|/)(ghp_[A-Za-z0-9]+|.*\.(pem|key|p12|pfx|crt|cer|der))$' || true
  exit 1
fi

# 2) staged 内容按 patterns 文件拦截
PAT_FILE="${PAT_FILE:-scripts/ops/secrets_patterns.txt}"
if [[ ! -f "${PAT_FILE}" ]]; then
  echo "[FAIL] patterns file missing: ${PAT_FILE}"
  exit 1
fi
PAT_TMP="$(mktemp)"
trap 'rm -f "${PAT_TMP}"' EXIT
awk 'NF && $0 !~ /^[[:space:]]*#/' "${PAT_FILE}" > "${PAT_TMP}"

if git diff --cached -U0 -- . ':(exclude)scripts/ops/secrets_patterns.txt' | rg -n -f "${PAT_TMP}" >/dev/null; then
  echo "[FAIL] staged diff seems to contain a token/private key material."
  exit 1
fi

echo "[OK] secrets scan passed."
