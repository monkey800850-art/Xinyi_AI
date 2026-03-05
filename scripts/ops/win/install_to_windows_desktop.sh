#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SRC_DIR="$ROOT_DIR/scripts/ops/win"
START_BAT="$SRC_DIR/Start_Xinyi_AI.bat"
STOP_BAT="$SRC_DIR/Stop_Xinyi_AI.bat"

if [[ ! -f "$START_BAT" ]]; then
  echo "ERROR: missing $START_BAT"
  exit 1
fi

# Prefer cmd.exe to discover the active Windows Desktop path.
DESKTOP_WIN_RAW="$(cmd.exe /c "echo %USERPROFILE%\\Desktop" 2>/dev/null | tr -d '\r' | tail -n 1)"
if [[ -z "$DESKTOP_WIN_RAW" ]]; then
  echo "ERROR: unable to resolve Windows Desktop via cmd.exe"
  exit 1
fi

DESKTOP_WIN="${DESKTOP_WIN_RAW//\\//}"
if [[ "$DESKTOP_WIN" =~ ^([A-Za-z]):/(.*)$ ]]; then
  DRIVE_LOWER="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
  DESKTOP_WSL="/mnt/${DRIVE_LOWER}/${BASH_REMATCH[2]}"
else
  echo "ERROR: unexpected Windows desktop path: $DESKTOP_WIN_RAW"
  exit 1
fi

if [[ ! -d "$DESKTOP_WSL" ]]; then
  echo "ERROR: desktop path not found in WSL: $DESKTOP_WSL"
  exit 1
fi

cp -f "$START_BAT" "$DESKTOP_WSL/"
if [[ -f "$STOP_BAT" ]]; then
  cp -f "$STOP_BAT" "$DESKTOP_WSL/"
fi

echo "Copied launcher(s) to: $DESKTOP_WSL"
echo "- $(basename "$START_BAT")"
if [[ -f "$STOP_BAT" ]]; then
  echo "- $(basename "$STOP_BAT")"
fi
