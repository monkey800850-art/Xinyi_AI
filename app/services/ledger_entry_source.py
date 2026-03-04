"""
REPORTS-QUERY-09: Ledger entry source adapter (best-effort).

Goal: fetch voucher entry rows (subject_code, debit, credit, aux dims, biz_date) to feed ledger_engine.

This module MUST be safe in restricted environments:
- If no DB backend is available, return [] with warnings.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os

def _get_db_url() -> Optional[str]:
    for k in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "DB_URL"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    return None

def fetch_entries_best_effort(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, List[str]]] = None,
    limit: int = 5000
) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """
    Returns: (entries, warnings, backend)
    backend: "sqlalchemy" | "sqlite3" | "none"
    """
    warnings: List[str] = []
    filters = filters or {}
    url = _get_db_url()
    if not url:
        return [], ["missing_db_url_env"], "none"

    # Try SQLAlchemy first
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(url, future=True)
        # NOTE: we assume a conventional table name; if your schema differs, we still remain safe.
        # Candidates: voucher_entries, journal_entries, gl_entries
        candidates = ["voucher_entries", "journal_entries", "gl_entries", "entries"]
        table = None
        with eng.connect() as conn:
            for t in candidates:
                try:
                    conn.execute(text(f"SELECT 1 FROM {t} LIMIT 1"))
                    table = t
                    break
                except Exception:
                    continue
            if not table:
                return [], ["no_known_entry_table_found"], "sqlalchemy"

            where = []
            bind = {}
            if date_from:
                where.append("biz_date >= :date_from")
                bind["date_from"] = date_from
            if date_to:
                where.append("biz_date <= :date_to")
                bind["date_to"] = date_to

            # Map filters keys to column names (best-effort)
            key_map = {
                "subject": "subject_code",
                "person": "aux_person_id",
                "project": "aux_project_id",
                "department": "aux_department_id",
                "bank_account": "aux_bank_account_id",
            }
            pi = 0
            for fk, vals in filters.items():
                col = key_map.get(fk)
                if not col or not vals:
                    continue
                # IN (:p0,:p1,...) form
                names = []
                for v in vals:
                    n = f"p{pi}"
                    pi += 1
                    names.append(":" + n)
                    bind[n] = v
                where.append(f"{col} IN ({','.join(names)})")

            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            sql = f"""
              SELECT
                biz_date,
                subject_code,
                debit,
                credit,
                aux_person_id,
                aux_project_id,
                aux_department_id,
                aux_bank_account_id
              FROM {table}
              {where_sql}
              LIMIT {int(limit)}
            """
            rs = conn.execute(text(sql), bind)
            cols = list(rs.keys())
            out=[]
            for row in rs.fetchall():
                out.append({cols[i]: row[i] for i in range(len(cols))})
            return out, warnings, "sqlalchemy"
    except Exception as e:
        warnings.append(f"sqlalchemy_fetch_failed: {e}")

    # sqlite3 fallback if sqlite URL
    try:
        import sqlite3
        if url.startswith("sqlite:///"):
            db_path = url[len("sqlite:///"):]
        else:
            return [], warnings + ["no_sqlite_fallback"], "none"

        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            # same candidate probing
            candidates = ["voucher_entries", "journal_entries", "gl_entries", "entries"]
            table=None
            for t in candidates:
                try:
                    cur.execute(f"SELECT 1 FROM {t} LIMIT 1")
                    table=t
                    break
                except Exception:
                    continue
            if not table:
                return [], warnings + ["no_known_entry_table_found"], "sqlite3"

            where=[]
            params=[]
            if date_from:
                where.append("biz_date >= ?"); params.append(date_from)
            if date_to:
                where.append("biz_date <= ?"); params.append(date_to)

            # sqlite filter best-effort (only subject_code)
            if filters.get("subject"):
                vals=filters["subject"]
                ph=",".join(["?"]*len(vals))
                where.append(f"subject_code IN ({ph})")
                params.extend(vals)

            where_sql=(" WHERE " + " AND ".join(where)) if where else ""
            sql=f"""
              SELECT biz_date, subject_code, debit, credit,
                     aux_person_id, aux_project_id, aux_department_id, aux_bank_account_id
              FROM {table}
              {where_sql}
              LIMIT {int(limit)}
            """
            cur.execute(sql, params)
            cols=[d[0] for d in cur.description]
            rows=cur.fetchall()
            out=[{cols[i]: r[i] for i in range(len(cols))} for r in rows]
            return out, warnings, "sqlite3"
        finally:
            conn.close()
    except Exception as e:
        warnings.append(f"sqlite3_fetch_failed: {e}")

    return [], warnings + ["no_executable_backend"], "none"
