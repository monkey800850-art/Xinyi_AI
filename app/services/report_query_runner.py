"""
REPORTS-QUERY-03: Best-effort query runner for report SQL plans.

Policy:
- Prefer SQLAlchemy if available and a DB URL is present.
- Fallback to sqlite3 if DB URL indicates sqlite:///... or a local sqlite path is configured.
- If neither is possible, return a safe response with warnings (no exception escape).

This runner executes ONLY the SQL produced by our planner endpoints.
It is not a general SQL executor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import os
import re

@dataclass
class RunResult:
    ok: bool
    rows: List[Dict[str, Any]]
    warnings: List[str]
    engine: str  # "sqlalchemy" | "sqlite3" | "none"
    elapsed_ms: Optional[int] = None

def _get_db_url_best_effort() -> Optional[str]:
    # Common env names
    for k in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "DB_URL"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    return None

def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite:///") or url.startswith("sqlite://")

def _sqlite_path_from_url(url: str) -> Optional[str]:
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        # sqlite:///:memory: or sqlite://relative
        rest = url[len("sqlite://"):]
        if rest.startswith("/"):
            # sqlite:////abs/path not fully supported here; best-effort
            return rest.lstrip("/")
        return rest
    return None

def _execute_sqlalchemy(sql: str, params: List[Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warns=[]
    try:
        from sqlalchemy import create_engine, text
    except Exception as e:
        raise RuntimeError(f"sqlalchemy import failed: {e}")

    url = _get_db_url_best_effort()
    if not url:
        raise RuntimeError("missing DB url env (DATABASE_URL/SQLALCHEMY_DATABASE_URI/DB_URL)")

    # Use text() with positional params: SQLAlchemy expects named or positional depending driver.
    # We keep it conservative: if '?' placeholders, try to map to :p0,:p1...
    if "?" in sql:
        new_sql = ""
        pi = 0
        for ch in sql:
            if ch == "?":
                new_sql += f":p{pi}"
                pi += 1
            else:
                new_sql += ch
        bind = {f"p{i}": params[i] for i in range(min(pi, len(params)))}
        sql = new_sql
    else:
        bind = {}

    eng = create_engine(url, future=True)
    with eng.connect() as conn:
        rs = conn.execute(text(sql), bind)
        cols = list(rs.keys())
        out=[]
        for row in rs.fetchall():
            out.append({cols[i]: row[i] for i in range(len(cols))})
        return out, warns

def _execute_sqlite3(sql: str, params: List[Any], db_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    warns=[]
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in (cur.description or [])]
        rows = cur.fetchall() if cols else []
        out=[]
        for r in rows:
            out.append({cols[i]: r[i] for i in range(len(cols))})
        return out, warns
    finally:
        conn.close()

def run_plan(plan: Dict[str, Any]) -> RunResult:
    """
    plan must contain: sql (str), params (list), columns (optional)
    Returns safe RunResult; never raises.
    """
    sql = (plan or {}).get("sql") or ""
    params = (plan or {}).get("params") or []
    warns = list((plan or {}).get("warnings") or [])

    if not sql.strip():
        return RunResult(ok=False, rows=[], warnings=warns + ["missing sql in plan"], engine="none")

    # Try SQLAlchemy first
    try:
        rows, w2 = _execute_sqlalchemy(sql, params)
        return RunResult(ok=True, rows=rows[:200], warnings=warns + w2, engine="sqlalchemy")
    except Exception as e:
        warns.append(f"sqlalchemy_exec_failed: {e}")

    # sqlite3 fallback
    url = _get_db_url_best_effort()
    if url and _is_sqlite_url(url):
        db_path = _sqlite_path_from_url(url)
        if db_path:
            try:
                rows, w2 = _execute_sqlite3(sql, params, db_path)
                return RunResult(ok=True, rows=rows[:200], warnings=warns + w2, engine="sqlite3")
            except Exception as e:
                warns.append(f"sqlite3_exec_failed: {e}")

    return RunResult(ok=False, rows=[], warnings=warns + ["no executable db backend in current environment"], engine="none")
