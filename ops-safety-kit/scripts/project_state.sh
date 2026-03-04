#!/usr/bin/env bash
set -euo pipefail

echo "=================================="
echo "XINYI PROJECT STATE"
echo "=================================="

echo ""
echo "== Repo =="
echo "path: $(pwd)"
echo "branch: $(git rev-parse --abbrev-ref HEAD)"
echo "head: $(git rev-parse --short HEAD)"
echo ""

echo "== Working tree status (dirty?) =="
git status --short || true
echo ""

echo "== RISK SCAN (filenames only) =="
echo "-- .env files --"
git ls-files -o --exclude-standard 2>/dev/null | rg -n '(^|/)\.env(\.|$)' || true
git ls-files 2>/dev/null | rg -n '(^|/)\.env(\.|$)' || true
echo "-- Zone.Identifier artifacts --"
find . -type f -name '*:Zone.Identifier*' -print 2>/dev/null | head -n 50 || true
echo "-- key/cert-like files --"
git ls-files 2>/dev/null | rg -n '\.(pem|key|p12|pfx|crt|cer|der)$' || true
echo ""

echo "== Recommended next action =="
echo "1) If risky files appear: run scripts/ops/gate_hygiene.sh and scripts/ops/gate_secrets.sh"
echo "2) To capture a snapshot for window switch: run scripts/ops/gate_all.sh"
echo ""

echo "== Recent commits =="
git log -5 --oneline
echo ""

echo "== Ops scripts =="
ls scripts/ops
echo ""

echo "== Latest gate run =="
latest_gate=$(ls -td /tmp/xinyi_gate_* 2>/dev/null | head -1 || true)

if [[ -n "${latest_gate}" ]]; then
  echo "dir: ${latest_gate}"
  echo ""
  echo "INDEX:"
  sed -n '1,120p' "${latest_gate}/INDEX.md" 2>/dev/null || true
else
  echo "No gate_all run found."
fi

echo ""
echo "=================================="
echo "WINDOW RECOVERY HINT"
echo "=================================="
echo "If switching ChatGPT window:"
echo ""
echo "1) Run:"
echo "   bash scripts/ops/project_state.sh"
echo ""
echo "2) Paste output into new window with:"
echo ""
echo "   加载工程上下文：Xinyi_AI 项目，继续 CLI 任务卡。"
echo ""
echo "=================================="
