#!/usr/bin/env python3
"""Scan HTML page routes and compare with side-nav coverage.

Only scans GET page routes that render templates. API routes are excluded.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]


def _extract_render_template_name(func: ast.FunctionDef) -> str | None:
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "render_template":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                return node.args[0].value
    return None


def _scan_blueprint_routes(py_file: Path, decorator_prefix: str) -> List[Dict[str, str]]:
    src = py_file.read_text(encoding="utf-8")
    mod = ast.parse(src)
    out: List[Dict[str, str]] = []

    for node in mod.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        route = None
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == decorator_prefix
                and dec.func.attr == "get"
                and dec.args
                and isinstance(dec.args[0], ast.Constant)
                and isinstance(dec.args[0].value, str)
            ):
                route = dec.args[0].value
                break
        if not route:
            continue
        template = _extract_render_template_name(node)
        if not template:
            continue
        out.append(
            {
                "path": route,
                "endpoint": node.name,
                "template": template,
            }
        )
    return out


def _scan_nav_urls(py_file: Path) -> List[str]:
    src = py_file.read_text(encoding="utf-8")
    mod = ast.parse(src)
    urls: List[str] = []

    class _Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name != "_build_main_nav":
                return
            for n in ast.walk(node):
                if not isinstance(n, ast.Dict):
                    continue
                keys = []
                vals = []
                for k, v in zip(n.keys, n.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.append(k.value)
                        vals.append(v)
                if "url" not in keys:
                    continue
                idx = keys.index("url")
                v = vals[idx]
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    urls.append(v.value)

    _Visitor().visit(mod)
    return sorted(set(urls))


def _module_of(path: str) -> str:
    if path.startswith("/system/consolidation"):
        return "合并"
    if path.startswith("/system/"):
        return "系统"
    if path.startswith("/dashboard"):
        return "工作台"
    if path.startswith("/voucher/"):
        return "总账与凭证"
    if path.startswith("/reports/"):
        return "报表"
    if path.startswith("/tax/"):
        return "税务"
    if path.startswith("/payroll"):
        return "薪资"
    if path.startswith("/banks/") or path.startswith("/payments"):
        return "资金"
    if path.startswith("/reimbursements"):
        return "报销"
    if path.startswith("/assets"):
        return "资产"
    if path.startswith("/masters/"):
        return "基础资料/辅助"
    if path.startswith("/demo/"):
        return "工具/演示"
    if path == "/":
        return "首页"
    return "其它"


def _is_menu_candidate(path: str) -> bool:
    if path in {"/", "/healthz"}:
        return False
    if "<" in path or ">" in path:
        return False
    return True


def main() -> None:
    core_routes = _scan_blueprint_routes(ROOT / "app/routes/core_pages.py", "core_pages_bp")
    consolidation_routes = _scan_blueprint_routes(ROOT / "app/routes/consolidation.py", "consolidation_bp")
    page_routes = sorted(core_routes + consolidation_routes, key=lambda x: x["path"])

    menu_candidates = [r for r in page_routes if _is_menu_candidate(r["path"])]
    nav_urls = _scan_nav_urls(ROOT / "app.py")

    for r in page_routes:
        r["module"] = _module_of(r["path"])
        r["is_menu_candidate"] = _is_menu_candidate(r["path"])
        r["in_nav"] = r["path"] in nav_urls

    missing_in_nav = [r for r in menu_candidates if r["path"] not in nav_urls]

    by_module: Dict[str, int] = {}
    for r in menu_candidates:
        key = r["module"]
        by_module[key] = by_module.get(key, 0) + 1

    out = {
        "page_route_count": len(page_routes),
        "menu_candidate_count": len(menu_candidates),
        "module_counts": dict(sorted(by_module.items(), key=lambda kv: kv[0])),
        "nav_url_count": len(nav_urls),
        "missing_in_nav_count": len(missing_in_nav),
        "missing_in_nav": missing_in_nav,
        "menu_candidates": menu_candidates,
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
