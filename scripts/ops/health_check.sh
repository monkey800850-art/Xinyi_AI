#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "=== git status -sb ==="
git status -sb

echo
echo "=== untracked by top-level dir ==="
git status --porcelain=v1 -uall | awk '
BEGIN {
  dirs["app/"]=0; dirs["tests/"]=0; dirs["migrations/"]=0;
  dirs["templates/"]=0; dirs["static/"]=0; dirs["docs/"]=0;
  dirs["scripts/"]=0; dirs["other"]=0;
}
/^\?\? / {
  path=substr($0,4)
  if (index(path,"app/")==1) dirs["app/"]++;
  else if (index(path,"tests/")==1) dirs["tests/"]++;
  else if (index(path,"migrations/")==1) dirs["migrations/"]++;
  else if (index(path,"templates/")==1) dirs["templates/"]++;
  else if (index(path,"static/")==1) dirs["static/"]++;
  else if (index(path,"docs/")==1) dirs["docs/"]++;
  else if (index(path,"scripts/")==1) dirs["scripts/"]++;
  else dirs["other"]++;
}
END {
  printf("app/: %d\n", dirs["app/"]);
  printf("tests/: %d\n", dirs["tests/"]);
  printf("migrations/: %d\n", dirs["migrations/"]);
  printf("templates/: %d\n", dirs["templates/"]);
  printf("static/: %d\n", dirs["static/"]);
  printf("docs/: %d\n", dirs["docs/"]);
  printf("scripts/: %d\n", dirs["scripts/"]);
  printf("other: %d\n", dirs["other"]);
}'

echo
echo "=== abnormal file scan ==="
zone_count="$(find . -type f -name '*:Zone.Identifier' | wc -l | tr -d ' ')"
dir_count="$(find . -maxdepth 2 -type d \( -name '_selfcheck' -o -name '_health' \) | wc -l | tr -d ' ')"
mapfile -t colon_files < <(find . -name '*:*' | grep -Ev '^\./https?://')
colon_count="${#colon_files[@]}"

echo "zone_identifier_count=${zone_count}"
echo "diagnostic_dir_count=${dir_count}"
echo "colon_filename_count=${colon_count}"
echo "colon_filename_sample(top20):"
if (( colon_count > 0 )); then
  printf '%s\n' "${colon_files[@]}" | head -n 20
else
  echo "(none)"
fi

if (( zone_count > 0 || dir_count > 0 || colon_count > 0 )); then
  exit 2
fi
exit 0
