#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
DEP_YEAR="${DEP_YEAR:-2025}"
DEP_MONTH="${DEP_MONTH:-2}"
TIMEOUT_SEC="${TIMEOUT_SEC:-10}"
TEST_PREFIX="${TEST_PREFIX:-STEP28R_$(date +%H%M%S)}"
CREATE_SAMPLE="${CREATE_SAMPLE:-1}"
BOOK_ID="${BOOK_ID:-}"

H_ADMIN_USER="${H_ADMIN_USER:-step28_admin}"
H_ADMIN_ROLE="${H_ADMIN_ROLE:-admin}"

pass_count=0
fail_count=0
blocked_count=0
fail_items=()

tmp_body="$(mktemp)"
trap 'rm -f "${tmp_body}"' EXIT

log() { echo "[INFO] $*"; }
pass() { echo "[PASS] $1"; pass_count=$((pass_count + 1)); }
fail() { echo "[FAIL] $1 :: $2"; fail_count=$((fail_count + 1)); fail_items+=("$1"); }
blocked() { echo "[BLOCKED] $1 :: $2"; blocked_count=$((blocked_count + 1)); fail_items+=("$1"); }

api_get() {
  local path="$1"
  local code
  code=$(curl -m "$TIMEOUT_SEC" -sS -o "$tmp_body" -w "%{http_code}" "${BASE_URL}${path}" || echo "000")
  echo "$code"
}

api_post_json() {
  local path="$1"
  local json_payload="$2"
  local code
  code=$(curl -m "$TIMEOUT_SEC" -sS -o "$tmp_body" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -H "X-User: ${H_ADMIN_USER}" \
    -H "X-Role: ${H_ADMIN_ROLE}" \
    -d "$json_payload" \
    "${BASE_URL}${path}" || echo "000")
  echo "$code"
}

json_get() {
  local file="$1"
  local key="$2"
  python3 - "$file" "$key" <<'PY'
import json,sys
f,k=sys.argv[1],sys.argv[2]
try:
    obj=json.load(open(f,'r',encoding='utf-8'))
except Exception:
    print("")
    raise SystemExit(0)
val=obj
for part in k.split('.'):
    if isinstance(val,dict):
        val=val.get(part)
    else:
        val=None
        break
print("" if val is None else val)
PY
}

log "STEP28 T3 minimal regression"
log "BASE_URL=${BASE_URL} DEP=${DEP_YEAR}-${DEP_MONTH} TEST_PREFIX=${TEST_PREFIX}"

book_id="$BOOK_ID"
category_id=""
asset_a_id=""
asset_b_id=""
asset_a_code="${TEST_PREFIX}_A"
asset_b_code="${TEST_PREFIX}_B"

if [[ "$CREATE_SAMPLE" == "1" || -z "$book_id" ]]; then
  log "creating sample book/category/assets for isolated regression"

  code=$(curl -m "$TIMEOUT_SEC" -sS -o "$tmp_body" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${TEST_PREFIX}_BOOK\",\"accounting_standard\":\"enterprise\"}" \
    "${BASE_URL}/books" || echo "000")
  if [[ "$code" != "201" ]]; then
    blocked "sample-book-create" "status=${code} body=$(head -c 200 "$tmp_body")"
  else
    book_id="$(json_get "$tmp_body" "book_id")"
    if [[ -z "$book_id" ]]; then
      blocked "sample-book-parse" "book_id missing in /books response"
    else
      pass "sample-book-create"
    fi
  fi

  if [[ -n "$book_id" ]]; then
    payload=$(cat <<JSON
{"book_id":${book_id},"code":"${TEST_PREFIX}_CAT","name":"${TEST_PREFIX} CAT","depreciation_method":"STRAIGHT_LINE","default_useful_life_months":60,"default_residual_rate":5,"expense_subject_code":"6602","accumulated_depr_subject_code":"1602"}
JSON
)
    code=$(api_post_json "/api/assets/categories" "$payload")
    if [[ "$code" != "201" ]]; then
      blocked "sample-category-create" "status=${code} body=$(head -c 200 "$tmp_body")"
    else
      category_id="$(json_get "$tmp_body" "id")"
      if [[ -z "$category_id" ]]; then
        blocked "sample-category-parse" "category id missing"
      else
        pass "sample-category-create"
      fi
    fi
  fi

  if [[ -n "$book_id" && -n "$category_id" ]]; then
    payload_a=$(cat <<JSON
{"book_id":${book_id},"asset_code":"${asset_a_code}","asset_name":"${TEST_PREFIX} Asset A","category_id":${category_id},"status":"ACTIVE","original_value":12000,"residual_rate":5,"residual_value":600,"useful_life_months":60,"depreciation_method":"STRAIGHT_LINE","purchase_date":"2025-01-01","start_use_date":"2025-01-01","capitalization_date":"2025-01-01","is_depreciable":1}
JSON
)
    code=$(api_post_json "/api/assets" "$payload_a")
    if [[ "$code" != "201" ]]; then
      blocked "sample-asset-a-create" "status=${code} body=$(head -c 200 "$tmp_body")"
    else
      asset_a_id="$(json_get "$tmp_body" "id")"
      pass "sample-asset-a-create"
    fi

    payload_b=$(cat <<JSON
{"book_id":${book_id},"asset_code":"${asset_b_code}","asset_name":"${TEST_PREFIX} Asset B","category_id":${category_id},"status":"ACTIVE","original_value":8000,"residual_rate":5,"residual_value":400,"useful_life_months":60,"depreciation_method":"STRAIGHT_LINE","purchase_date":"2025-03-01","start_use_date":"2025-03-01","capitalization_date":"2025-03-01","is_depreciable":1}
JSON
)
    code=$(api_post_json "/api/assets" "$payload_b")
    if [[ "$code" != "201" ]]; then
      blocked "sample-asset-b-create" "status=${code} body=$(head -c 200 "$tmp_body")"
    else
      asset_b_id="$(json_get "$tmp_body" "id")"
      pass "sample-asset-b-create"
    fi
  fi
fi

if [[ -z "$book_id" ]]; then
  blocked "precondition-book" "book_id unavailable. set BOOK_ID=<id> or keep CREATE_SAMPLE=1"
fi
if [[ -z "$asset_a_id" || -z "$asset_b_id" ]]; then
  blocked "precondition-assets" "sample assets unavailable for S5/S4->S6 checks"
fi

# S4 depreciation
if [[ -n "$book_id" ]]; then
  payload_dep=$(cat <<JSON
{"book_id":${book_id},"year":${DEP_YEAR},"month":${DEP_MONTH},"voucher_status":"draft"}
JSON
)
  code=$(api_post_json "/api/assets/depreciation" "$payload_dep")
  if [[ "$code" == "201" ]]; then
    success_count="$(json_get "$tmp_body" "success_count")"
    if [[ -n "$success_count" && "$success_count" -ge 1 ]]; then
      pass "s4-depreciation-run"
    else
      fail "s4-depreciation-run" "status=201 but success_count=${success_count}"
    fi
  elif [[ "$code" == "400" ]] && rg -q "本期已计提" "$tmp_body"; then
    pass "s4-depreciation-run(reuse-period)"
  else
    fail "s4-depreciation-run" "status=${code} body=$(head -c 220 "$tmp_body")"
  fi
fi

# S5 change + list
if [[ -n "$asset_a_id" ]]; then
  payload_ch=$(cat <<JSON
{"change_type":"TRANSFER","change_date":"${DEP_YEAR}-02-20","to_department_id":5001,"note":"${TEST_PREFIX}_NOTE"}
JSON
)
  code=$(api_post_json "/api/assets/${asset_a_id}/change" "$payload_ch")
  if [[ "$code" == "200" ]]; then
    pass "s5-change-create"
  else
    fail "s5-change-create" "status=${code} body=$(head -c 220 "$tmp_body")"
  fi

  code=$(api_get "/api/assets/changes?book_id=${book_id}&asset_code=${asset_a_code}")
  if [[ "$code" != "200" ]]; then
    fail "s5-change-list" "status=${code} body=$(head -c 220 "$tmp_body")"
  else
    read -r ok_note ok_operator item_count < <(python3 - "$tmp_body" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
items=obj.get('items') or []
first=items[0] if items else {}
ok_note=1 if (first.get('note') or '').strip() else 0
ok_op=1 if (first.get('operator') or '').strip() else 0
print(ok_note, ok_op, len(items))
PY
)
    if [[ "$item_count" -ge 1 && "$ok_note" == "1" && "$ok_operator" == "1" ]]; then
      pass "s5-change-list"
    else
      fail "s5-change-list" "items=${item_count} note_ok=${ok_note} operator_ok=${ok_operator}"
    fi
  fi
fi

# S6 ledger linkage
if [[ -n "$book_id" ]]; then
  code=$(api_get "/api/assets/ledger?book_id=${book_id}&dep_year=${DEP_YEAR}&dep_month=${DEP_MONTH}")
  if [[ "$code" != "200" ]]; then
    fail "s6-ledger-query" "status=${code} body=$(head -c 220 "$tmp_body")"
  else
    read -r has_a has_b a_gt0 b_eq0 total_items < <(python3 - "$tmp_body" "$asset_a_code" "$asset_b_code" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
a_code=sys.argv[2]; b_code=sys.argv[3]
items=obj.get('items') or []
mp={x.get('asset_code'):x for x in items}
a=mp.get(a_code); b=mp.get(b_code)
has_a=1 if a else 0
has_b=1 if b else 0
try:
    a_gt0=1 if a and float(a.get('accumulated_depr',0))>0 else 0
except Exception:
    a_gt0=0
try:
    b_eq0=1 if b and float(b.get('accumulated_depr',-1))==0 else 0
except Exception:
    b_eq0=0
print(has_a, has_b, a_gt0, b_eq0, len(items))
PY
)
    if [[ "$has_a" == "1" && "$has_b" == "1" && "$a_gt0" == "1" && "$b_eq0" == "1" ]]; then
      pass "s4-to-s6-ledger-linkage"
    else
      fail "s4-to-s6-ledger-linkage" "items=${total_items} has_a=${has_a} has_b=${has_b} a_gt0=${a_gt0} b_eq0=${b_eq0}"
    fi
  fi
fi

echo "---"
echo "summary: pass_count=${pass_count} fail_count=${fail_count} blocked_count=${blocked_count}"
if [[ ${#fail_items[@]} -gt 0 ]]; then
  echo "failed_or_blocked_items: ${fail_items[*]}"
fi

if (( fail_count > 0 || blocked_count > 0 )); then
  exit 1
fi
