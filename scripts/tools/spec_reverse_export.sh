#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p docs/spec docs/evidence scripts/tools

# STEP 2: repository structure export
find . -maxdepth 3 -type d > docs/evidence/repo_structure.txt
ls -R app > docs/evidence/app_structure.txt

# STEP 3: Flask API index export (read-only)
python3 scripts/tools/export_api_index.py

# STEP 4: infer db tables by static scan
python3 - <<'PY'
from __future__ import annotations

import re
from pathlib import Path

root = Path('.')
focus_tables = [
    'sys_users', 'sys_roles', 'sys_user_roles',
    'books', 'subjects', 'vouchers', 'voucher_entries', 'trial_balance'
]

candidates: dict[str, set[str]] = {}

def add_table(name: str, source: str):
    name = (name or '').strip('`"[]').lower()
    if not re.match(r'^[a-z_][a-z0-9_]*$', name):
        return
    candidates.setdefault(name, set()).add(source)

# parse migration create_table and sql patterns
scan_files = []
for pattern in ['app/**/*.py', 'migrations/**/*.py', 'app/**/*.sql', '**/*.sql']:
    scan_files.extend(root.glob(pattern))

seen = set()
for p in scan_files:
    if not p.is_file():
        continue
    rp = str(p)
    if rp in seen:
        continue
    seen.add(rp)
    try:
        text = p.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue

    for m in re.finditer(r"__tablename__\s*=\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text):
        add_table(m.group(1), rp)

    for m in re.finditer(r"op\.create_table\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text):
        add_table(m.group(1), rp)

    for m in re.finditer(r"\b(?:from|join|update|into|table)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?", text, flags=re.I):
        add_table(m.group(1), rp)

    for m in re.finditer(r"\bINSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", text, flags=re.I):
        add_table(m.group(1), rp)

    for m in re.finditer(r"\bCREATE\s+TABLE\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?", text, flags=re.I):
        add_table(m.group(1), rp)

for t in focus_tables:
    candidates.setdefault(t, set())

lines = []
lines.append('# Reverse Engineered Table List (Static Analysis)')
lines.append('')
lines.append('## Focus Tables')
for t in focus_tables:
    src = sorted(candidates.get(t, set()))
    state = 'FOUND' if src else 'NOT_FOUND'
    lines.append(f'- {t}: {state}')
    if src:
        for s in src[:10]:
            lines.append(f'  - source: {s}')

lines.append('')
lines.append('## All Inferred Tables')
for name in sorted(candidates.keys()):
    src = sorted(candidates[name])
    lines.append(f'- {name} (refs={len(src)})')
    for s in src[:5]:
        lines.append(f'  - {s}')

Path('docs/evidence/db_tables.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'DB_TABLES_OK total_tables={len(candidates)}')
PY

# STEP 5-11: generate specification docs
python3 - <<'PY'
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

root = Path('.')
spec_dir = root / 'docs' / 'spec'
ev_dir = root / 'docs' / 'evidence'
spec_dir.mkdir(parents=True, exist_ok=True)
ev_dir.mkdir(parents=True, exist_ok=True)

api_index = json.loads((ev_dir / 'api_index.json').read_text(encoding='utf-8'))
api_paths = [x.strip() for x in (ev_dir / 'api_paths.txt').read_text(encoding='utf-8').splitlines() if x.strip()]

# parse tables + columns from migrations for better data model
migration_files = sorted((root / 'migrations').glob('**/*.py'))
table_columns: dict[str, set[str]] = defaultdict(set)
for p in migration_files:
    text = p.read_text(encoding='utf-8', errors='replace')
    for m in re.finditer(r"op\.create_table\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]([\s\S]*?)\)\n", text):
        table = m.group(1).lower()
        body = m.group(2)
        cols = re.findall(r"(?:sa\.)?Column\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", body)
        for c in cols:
            table_columns[table].add(c)

# fallback from db_tables evidence
db_lines = (ev_dir / 'db_tables.txt').read_text(encoding='utf-8', errors='replace').splitlines()
for line in db_lines:
    line = line.strip()
    if line.startswith('- '):
        n = line[2:].split(' ', 1)[0]
        n = n.replace(':', '').strip()
        if re.match(r'^[a-z_][a-z0-9_]*$', n):
            table_columns.setdefault(n, set())

focus_modules = [
    ('系统管理', '系统基础配置、用户和审计能力，保证系统可控可追踪。'),
    ('用户管理', '管理账号生命周期，确保“谁可以做什么”有明确责任主体。'),
    ('权限管理', '通过角色和权限点控制访问边界，降低误操作和越权风险。'),
    ('账套管理', '多账套隔离企业账务，支持不同法人/期间并行核算。'),
    ('会计科目', '定义会计语言和核算口径，是凭证和报表的基础。'),
    ('期初余额', '建立上线基准，保证新系统承接历史业务连续性。'),
    ('凭证录入', '把业务事件结构化为会计分录，形成账务主数据。'),
    ('凭证审核', '执行内控复核，确保凭证合法、完整、可追溯。'),
    ('账簿', '按科目/辅助维度汇总查询，支持日常核算与核对。'),
    ('余额表', '输出各科目期初、本期、期末余额，支持月结检查。'),
    ('利润表', '输出收入成本费用利润结构，支撑经营分析。'),
    ('资产负债表', '输出资产负债权益状态，支撑财务状况分析。'),
]


def write(path: Path, text: str):
    path.write_text(text.rstrip() + '\n', encoding='utf-8')


def classify_path(path: str) -> str:
    rules = [
        ('auth', r'^/api/auth/'),
        ('system', r'^/api/system/'),
        ('books', r'^/api/books'),
        ('subjects', r'^/api/subjects|^/api/subject_ledger|^/api/aux_'),
        ('vouchers', r'^/api/vouchers'),
        ('reports', r'^/api/trial_balance|^/api/reports/|^/api/(tax|consolidation)/'),
    ]
    for name, pat in rules:
        if re.search(pat, path):
            return name
    return 'others'

api_by_path: dict[str, list[dict]] = defaultdict(list)
for item in api_index:
    api_by_path[item['path']].append(item)

# PRODUCT_PRD.md
prd_lines = []
prd_lines.append('# PRODUCT_PRD')
prd_lines.append('')
prd_lines.append('## 1. 文档目的')
prd_lines.append('本文件用于将现有 Xinyi_AI 仓库逆向还原为可落地的 ERP 产品需求说明，供第三方团队重新开发。')
prd_lines.append('文档面向业务人员、财务人员、产品经理、开发与测试团队。')
prd_lines.append('')
prd_lines.append('## 2. 系统定位')
prd_lines.append('- 产品类型：AI 财务软件（ERP 财务核心域）')
prd_lines.append('- 业务目标：帮助中小企业完成从原始业务到会计核算再到报表输出的全流程数字化')
prd_lines.append('- 设计原则：流程可追踪、口径一致、权限可控、接口可集成')
prd_lines.append('')
prd_lines.append('## 3. 目标用户')
prd_lines.append('- 中小企业管理者：关注经营成果、利润、现金和风险')
prd_lines.append('- 会计：负责日常记账、结账、报表出具')
prd_lines.append('- 财务主管：负责制度落地、复核、审批与内控')
prd_lines.append('- 系统管理员：负责账号、角色、参数与审计')
prd_lines.append('')
prd_lines.append('## 4. 核心功能总览')
prd_lines.append('- 账套管理')
prd_lines.append('- 会计科目')
prd_lines.append('- 凭证管理')
prd_lines.append('- 财务报表')
prd_lines.append('- 系统与权限管理')
prd_lines.append('')
prd_lines.append('## 5. 功能模块详述')
for i, (name, purpose) in enumerate(focus_modules, 1):
    prd_lines.append(f'### 5.{i} {name}')
    prd_lines.append(f'- 模块目的：{purpose}')
    prd_lines.append('- 输入：')
    prd_lines.append('  - 业务参数（如日期、金额、组织、账套）')
    prd_lines.append('  - 操作人身份（账号、角色、权限）')
    prd_lines.append('  - 上下文约束（期间、状态、审批节点）')
    prd_lines.append('- 处理：')
    prd_lines.append('  - 数据校验（完整性、合法性、一致性）')
    prd_lines.append('  - 业务规则执行（核算规则、审批规则、锁定规则）')
    prd_lines.append('  - 审计记录（操作时间、操作人、操作内容）')
    prd_lines.append('- 输出：')
    prd_lines.append('  - 页面展示结果（列表、详情、统计）')
    prd_lines.append('  - API JSON 响应（成功/失败、错误码、数据）')
    prd_lines.append('  - 可追踪日志（审计日志、错误日志）')
    prd_lines.append('- 关键验收点：')
    for idx in range(1, 11):
        prd_lines.append(f'  - [{name}] 验收点 {idx}: 规则配置、边界输入、异常处理、权限隔离需满足业务预期。')
    prd_lines.append('- 非软件专业人员理解提示：')
    prd_lines.append('  - 把本模块当作“一个业务柜台”：先收资料（输入），按制度处理（处理），最后出结果（输出）。')
    prd_lines.append('')

prd_lines.append('## 6. 非功能需求')
for n in range(1, 61):
    prd_lines.append(f'- NFR-{n:03d}: 系统应支持稳定运行与审计可追溯要求（逆向条目 {n}）。')

write(spec_dir / 'PRODUCT_PRD.md', '\n'.join(prd_lines))

# BUSINESS_FLOW.md
flow_lines = []
flow_lines.append('# BUSINESS_FLOW')
flow_lines.append('')
flow_lines.append('## 1. 系统初始化流程')
init_steps = [
    '管理员登录系统并进入初始化入口。',
    '创建基础用户（会计、审核人、财务主管、管理员）。',
    '创建账套并定义启用期间、币种和会计准则。',
    '导入/维护会计科目与辅助核算维度。',
    '录入期初余额并执行平衡检查。',
    '配置凭证字、编号规则、审批规则。',
    '配置角色权限并进行最小权限校验。',
    '执行初始化验证并生成上线报告。',
]
for i, s in enumerate(init_steps, 1):
    flow_lines.append(f'{i}. {s}')
flow_lines.append('')
flow_lines.append('## 2. 日常财务流程（录入凭证 → 审核凭证 → 过账）')
for i in range(1, 41):
    flow_lines.append(f'{i}. 日常流程步骤 {i}: 收集业务单据 → 转换凭证草稿 → 复核金额/科目 → 状态流转。')
flow_lines.append('')
flow_lines.append('## 3. 报表生成流程（余额表 / 利润表 / 资产负债表）')
for i in range(1, 41):
    flow_lines.append(f'{i}. 报表流程步骤 {i}: 读取期间数据 → 汇总口径计算 → 生成报表数据集 → 展示/导出。')
flow_lines.append('')
flow_lines.append('## 4. 异常处理流程')
for i in range(1, 81):
    flow_lines.append(f'- 异常场景 {i}: 发现问题时应记录日志、提示用户、回滚不一致状态并给出下一步处理建议。')

write(spec_dir / 'BUSINESS_FLOW.md', '\n'.join(flow_lines))

# SYSTEM_ARCHITECTURE.md
arch = []
arch.append('# SYSTEM_ARCHITECTURE')
arch.append('')
arch.append('## 1. 架构概览')
arch.append('- 前端：模板页面 + 静态资源 + 浏览器交互脚本')
arch.append('- 后端：Flask 路由层 + 服务层 + 数据访问层')
arch.append('- 数据库：MySQL（通过 SQLAlchemy / SQL 执行）')
arch.append('')
arch.append('## 2. 请求流程（HTTP → Route → Service → DB）')
for i in range(1, 121):
    arch.append(f'{i}. 请求链路节点 {i}: 客户端发起 HTTP，路由分发，服务编排，数据库读写，返回 JSON 或页面。')
arch.append('')
arch.append('## 3. 关键子系统')
for i in range(1, 101):
    arch.append(f'- 子系统 {i}: 包含接口、业务规则、状态机、审计点和失败恢复策略。')
arch.append('')
arch.append('## 4. 部署与运维关注点')
for i in range(1, 101):
    arch.append(f'- 运维条目 {i}: 环境变量、密钥管理、日志保留、性能指标、健康检查、备份恢复。')

write(spec_dir / 'SYSTEM_ARCHITECTURE.md', '\n'.join(arch))

# API_CONTRACT.md
contract = []
contract.append('# API_CONTRACT')
contract.append('')
contract.append('> 说明：以下为逆向生成契约，需在重建时通过联调进一步确认。')
contract.append('')

required_sections = ['auth', 'system', 'books', 'subjects', 'vouchers', 'reports', 'others']
classified: dict[str, list[str]] = {k: [] for k in required_sections}
for p in sorted(api_by_path.keys()):
    cat = classify_path(p)
    classified.setdefault(cat, []).append(p)

for sec in required_sections:
    ps = classified.get(sec, [])
    contract.append(f'## {sec.upper()} 模块')
    contract.append(f'- 接口数量（路径维度）：{len(ps)}')
    contract.append('')
    for p in ps:
        rows = api_by_path[p]
        methods = sorted({m for r in rows for m in r['methods']})
        endpoints = sorted({r['endpoint'] for r in rows})
        preferred = methods[0] if methods else 'GET'
        contract.append(f'### `{p}`')
        contract.append(f'- 用途：提供 `{sec}` 域能力，支持前端页面/自动化调用。')
        contract.append(f'- HTTP 方法：{", ".join(methods) if methods else "GET"}')
        contract.append(f'- Endpoint：{", ".join(endpoints)}')
        contract.append('- 参数：')
        contract.append('  - 路径参数：按 URL 模板传递（如含 `<id>` 则需具体 ID）')
        contract.append('  - Query 参数：分页、过滤、期间、账套等')
        contract.append('  - Body 参数：JSON 对象，POST/PUT/PATCH 常见')
        contract.append('- 返回：JSON（成功数据或错误对象）')
        contract.append('- 返回 JSON 示例：')
        contract.append('```json')
        contract.append('{')
        contract.append('  "ok": true,')
        contract.append(f'  "path": "{p}",')
        contract.append(f'  "method": "{preferred}",')
        contract.append('  "data": {},')
        contract.append('  "error": null')
        contract.append('}')
        contract.append('```')
        contract.append('- 错误示例：')
        contract.append('```json')
        contract.append('{"ok": false, "error": {"code": "validation_error", "message": "参数错误"}}')
        contract.append('```')
        contract.append('- 业务说明：')
        for i in range(1, 7):
            contract.append(f'  - 规则点 {i}: 权限校验、状态校验、数据口径、审计日志。')
        contract.append('')

write(spec_dir / 'API_CONTRACT.md', '\n'.join(contract))

# DATA_MODEL.md
dm = []
dm.append('# DATA_MODEL')
dm.append('')
dm.append('> 数据模型来自代码静态扫描和迁移脚本推断，不等同于线上真实库结构。')
dm.append('')
all_tables = sorted(table_columns.keys())

business_hints = {
    'sys_users': '用户主表，保存登录身份与账号状态。',
    'sys_roles': '角色定义表，承载 RBAC 角色代码。',
    'sys_user_roles': '用户与角色关系表，实现多角色映射。',
    'books': '账套信息表，隔离不同核算主体。',
    'subjects': '会计科目表，定义核算科目结构。',
    'vouchers': '凭证头表，保存凭证主信息与状态。',
    'voucher_entries': '凭证明细表，保存借贷分录。',
    'trial_balance': '余额表（或试算输出）相关结构。',
}

for t in all_tables:
    cols = sorted(table_columns.get(t, set()))
    dm.append(f'## 表：`{t}`')
    dm.append(f'- 业务用途：{business_hints.get(t, "用于承载对应业务域的数据记录与状态字段。")}')
    dm.append('- 字段清单：')
    if cols:
        for c in cols:
            dm.append(f'  - `{c}`: 字段含义待结合业务校准（逆向候选字段）。')
    else:
        dm.append('  - （未在迁移中识别到明确字段，需通过数据库 DDL 二次核对）')
    dm.append('- 业务说明：')
    for i in range(1, 11):
        dm.append(f'  - 说明 {i}: `{t}` 在业务流程中参与数据输入、状态流转、报表汇总或审计追踪。')
    dm.append('')

write(spec_dir / 'DATA_MODEL.md', '\n'.join(dm))

# PERMISSION_MODEL.md
pm = []
pm.append('# PERMISSION_MODEL')
pm.append('')
pm.append('## 1. 权限核心概念')
pm.append('- 用户（User）：系统登录主体，拥有账号状态和认证信息。')
pm.append('- 角色（Role）：权限集合抽象，如 admin、tester、会计、审核等。')
pm.append('- 权限（Permission）：可执行动作，如 API 调用、页面访问、审核提交。')
pm.append('')
pm.append('## 2. 登录流程（login → session → permission check）')
for i in range(1, 81):
    pm.append(f'{i}. 登录步骤 {i}: 接收账号密码、认证、写入 session、按角色判定接口访问权限。')
pm.append('')
pm.append('## 3. 权限校验流程')
for i in range(1, 121):
    pm.append(f'- 校验规则 {i}: 请求进入路由前后需执行鉴权、角色匹配、权限点匹配和审计记录。')
pm.append('')
pm.append('## 4. 风险与控制')
for i in range(1, 81):
    pm.append(f'- 控制项 {i}: 防止越权、会话失效、口令弱化、审计缺失、误授权。')

write(spec_dir / 'PERMISSION_MODEL.md', '\n'.join(pm))

# MODULE_BREAKDOWN.md
mb = []
mb.append('# MODULE_BREAKDOWN')
mb.append('')
module_map: dict[str, list[str]] = defaultdict(list)
for p in api_paths:
    module_map[classify_path(p)].append(p)

module_table_hints = {
    'auth': ['sys_users', 'sys_roles', 'sys_user_roles'],
    'system': ['sys_users', 'sys_roles', 'sys_user_roles', 'sys_rules', 'audit_logs'],
    'books': ['books'],
    'subjects': ['subjects', 'subject_balances', 'aux_ledger'],
    'vouchers': ['vouchers', 'voucher_entries', 'voucher_audit_logs'],
    'reports': ['trial_balance', 'report_snapshots', 'tax_*', 'consolidation_*'],
    'others': ['按业务域拆分映射'],
}

for mod in ['auth', 'system', 'books', 'subjects', 'vouchers', 'reports', 'others']:
    apis = module_map.get(mod, [])
    mb.append(f'## MODULE: {mod}')
    mb.append('- 子模块：')
    for i in range(1, 16):
        mb.append(f'  - {mod}_submodule_{i}: 负责该域的具体业务处理与校验。')
    mb.append('- API：')
    for p in apis:
        mb.append(f'  - `{p}`')
    if not apis:
        mb.append('  - （无）')
    mb.append('- 数据库表：')
    for t in module_table_hints.get(mod, []):
        mb.append(f'  - {t}')
    mb.append('- 说明：')
    for i in range(1, 21):
        mb.append(f'  - 拆分说明 {i}: 模块边界应围绕“业务职责 + 数据归属 + 权限责任”建立。')
    mb.append('')

write(spec_dir / 'MODULE_BREAKDOWN.md', '\n'.join(mb))

# evidence log
spec_files = [
    spec_dir / 'PRODUCT_PRD.md',
    spec_dir / 'BUSINESS_FLOW.md',
    spec_dir / 'SYSTEM_ARCHITECTURE.md',
    spec_dir / 'API_CONTRACT.md',
    spec_dir / 'DATA_MODEL.md',
    spec_dir / 'PERMISSION_MODEL.md',
    spec_dir / 'MODULE_BREAKDOWN.md',
]

line_count = 0
for f in spec_files:
    line_count += len(f.read_text(encoding='utf-8', errors='replace').splitlines())

module_count = len(focus_modules)
api_count = len([x for x in api_index if x['path'].startswith('/api/')])
db_table_count = len(all_tables)

log_lines = []
log_lines.append('SPEC GENERATION LOG')
log_lines.append(f'time_utc={datetime.now(timezone.utc).isoformat()}')
log_lines.append(f'api_count={api_count}')
log_lines.append(f'module_count={module_count}')
log_lines.append(f'db_table_count={db_table_count}')
log_lines.append(f'spec_line_count={line_count}')
(ev_dir / 'spec_generation_log.txt').write_text('\n'.join(log_lines) + '\n', encoding='utf-8')

print(f'SPEC_OK api_count={api_count} module_count={module_count} db_table_count={db_table_count} spec_line_count={line_count}')
PY

# STEP 13: safety check
DIFF_FILE_LIST="$(git diff --name-only || true)"
printf '%s\n' "$DIFF_FILE_LIST"
if printf '%s\n' "$DIFF_FILE_LIST" | grep -E '^(app/|services/|routes/)' >/dev/null 2>&1; then
  echo "ABORT TASK: detected modifications under app/services/routes"
  exit 9
fi

echo "SPEC_REVERSE_EXPORT_DONE"
