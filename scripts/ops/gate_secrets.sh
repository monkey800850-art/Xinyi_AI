#!/usr/bin/env bash
set -euo pipefail

echo "[gate] secrets scan..."

# 1) staged 文件名直接拦截
if git diff --cached --name-only | egrep -qi '(^|/)(ghp_[A-Za-z0-9]+|.*\.(pem|key|p12|pfx|crt|cer|der))$'; then
  echo "[FAIL] staged contains token/key/cert-like files."
  git diff --cached --name-only | egrep -i '(^|/)(ghp_[A-Za-z0-9]+|.*\.(pem|key|p12|pfx|crt|cer|der))$' || true
  exit 1
fi

# 2) staged 内容关键字拦截（ghp_ / PRIVATE KEY）
if git diff --cached -U0 | egrep -qi '(ghp_[A-Za-z0-9]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)'; then
  echo "[FAIL] staged diff seems to contain a token/private key material."
  exit 1
fi

echo "[OK] secrets scan passed."
