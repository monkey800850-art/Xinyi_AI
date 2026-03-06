"""
Consolidation Access Authorization Service
阶段：主单落库期（修复 DB 接入）
"""

from __future__ import annotations
from typing import Any, Dict
from datetime import datetime
import uuid
import os
from app.services.consolidation_service import add_consolidation_group_member

try:
    import app.services.consolidation_service as _xinyi_cons_service  # XINYI_CONS_DBALIGN_INJECT
    if "db" in globals():
        _xinyi_cons_service.db = db
except Exception:
    pass




from pathlib import Path
import re
import json

def _write_cons_access_evidence(action: str, grant_id: int, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    base = Path("docs/evidence_erp2/consolidation_access/actions")
    try:
        payload = _json_safe_obj(payload) if 'payload' in locals() else payload
    except Exception:
        pass
    try:
        body = _json_safe_obj(body) if 'body' in locals() else body
    except Exception:
        pass
    try:
        result = _json_safe_obj(result) if 'result' in locals() else result
    except Exception:
        pass
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = base / f"{action}_grant_{grant_id}_{ts}.json"
    body = {
        "action": action,
        "grant_id": grant_id,
        "ts": _cons_access_no(),
        "payload": payload,
        "result": result,
    }
    path.write_text(json.dumps(_json_safe_obj(body), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
def _cons_access_no() -> str:
    return "CAG-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8].upper()


def _get_sqla_session():
    # 1) 尝试 app.py 注入的 db
    g = globals()
    db = g.get("db")
    if db is not None and hasattr(db, "session"):
        return db.session

    # 2) 尝试常见扩展位置
    for mod_name in [
        "app.extensions",
        "app.db",
        "app.core.extensions",
        "app.common.extensions",
    ]:
        try:
            mod = __import__(mod_name, fromlist=["db"])
            db = getattr(mod, "db", None)
            if db is not None and hasattr(db, "session"):
                return db.session
        except Exception:
            continue
    return None


def _normalize_named_params_for_pymysql(sql, params):
    """
    将 :name 风格参数转换为 %(name)s，兼容 PyMySQL / DB-API named style。
    仅做轻量兼容，不处理复杂 SQL parser 场景。
    """
    if not params:
        return sql, params

    pattern = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")

    names = pattern.findall(sql)
    if not names:
        return sql, params

    missing = [n for n in names if n not in params]
    if missing:
        raise KeyError(f"SQL params missing keys: {missing}")

    sql2 = pattern.sub(lambda m: f"%({m.group(1)})s", sql)
    return sql2, params


def _db_exec(sql: str, params: Dict[str, Any] | None = None, fetch: str = "none"):
    params = params or {}

    # A. 优先 SQLAlchemy
    sess = _get_sqla_session()
    sqla_error = None
    if sess is not None:
        try:
            from sqlalchemy import text
            res = sess.execute(text(sql), params)

            if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")):
                try:
                    sess.commit()
                except Exception:
                    pass

            if fetch == "one":
                row = res.mappings().first()
                return dict(row) if row else None
            if fetch == "all":
                return [dict(r) for r in res.mappings().all()]
            return None
        except Exception as e:
            sqla_error = e

    # B. 再试 pymysql
    try:
        import pymysql
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = int(os.getenv("DB_PORT", "3306"))
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD") or ""
        database = os.getenv("DB_NAME")

        if not user or not database:
            raise RuntimeError("missing DB_USER / DB_NAME")

        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cur:
                sql, params = _normalize_named_params_for_pymysql(sql, params)
                cur.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None
        finally:
            conn.close()

    except Exception as e:
        if sqla_error is not None:
            raise RuntimeError(f"SQLAlchemy failed: {sqla_error}; pymysql failed: {e}")
        raise RuntimeError(f"pymysql failed: {e}")


def list_access_grants() -> Dict[str, Any]:
    try:
        items = _db_exec(
            """
            SELECT
                id, authorization_no, parent_tenant_id, parent_book_id,
                child_tenant_id, child_book_id, virtual_entity_id,
                grant_mode, status, effective_from, effective_to,
                approval_doc_no, approval_doc_name,
                created_by, approved_by, revoked_by,
                access_granted_at, included_into_virtual_at,
                created_at, updated_at
            FROM consolidation_access_grants
            ORDER BY id DESC
            """,
            {},
            fetch="all",
        ) or []
        return {
            "items": items,
            "count": len(items),
            "module": "consolidation_access",
            "status": "ok",
        }
    except Exception as e:
        return {
            "items": [],
            "count": 0,
            "module": "consolidation_access",
            "status": "stub",
            "error": str(e),
        }


def create_access_grant(payload: Dict[str, Any]) -> Dict[str, Any]:
    auth_no = _cons_access_no()
    data = {
        "authorization_no": auth_no,
        "parent_tenant_id": payload.get("parent_tenant_id"),
        "parent_book_id": payload.get("parent_book_id"),
        "child_tenant_id": payload.get("child_tenant_id"),
        "child_book_id": payload.get("child_book_id"),
        "virtual_entity_id": payload.get("virtual_entity_id"),
        "grant_mode": payload.get("grant_mode") or "consolidation_work",
        "status": "draft",
        "effective_from": payload.get("effective_from"),
        "effective_to": payload.get("effective_to"),
        "approval_doc_no": payload.get("approval_doc_no"),
        "approval_doc_name": payload.get("approval_doc_name"),
        "authorization_basis": payload.get("authorization_basis"),
        "created_by": payload.get("created_by"),
    }

    required = [
        "parent_tenant_id",
        "parent_book_id",
        "child_tenant_id",
        "child_book_id",
        "virtual_entity_id",
    ]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return {
            "module": "consolidation_access",
            "status": "error",
            "error": "missing_required_fields",
            "missing": missing,
        }

    try:
        _db_exec(
            """
            INSERT INTO consolidation_access_grants (
                authorization_no,
                parent_tenant_id,
                parent_book_id,
                child_tenant_id,
                child_book_id,
                virtual_entity_id,
                grant_mode,
                status,
                effective_from,
                effective_to,
                approval_doc_no,
                approval_doc_name,
                authorization_basis,
                created_by
            ) VALUES (
                :authorization_no,
                :parent_tenant_id,
                :parent_book_id,
                :child_tenant_id,
                :child_book_id,
                :virtual_entity_id,
                :grant_mode,
                :status,
                :effective_from,
                :effective_to,
                :approval_doc_no,
                :approval_doc_name,
                :authorization_basis,
                :created_by
            )
            """,
            data,
            fetch="none",
        )

        row = _db_exec(
            """
            SELECT *
            FROM consolidation_access_grants
            WHERE authorization_no = :authorization_no
            LIMIT 1
            """,
            {"authorization_no": auth_no},
            fetch="one",
        )

        return {
            "item": row,
            "module": "consolidation_access",
            "status": "ok",
        }
    except Exception as e:
        return {
            "item": {
                "id": 0,
                "authorization_no": auth_no,
                "status": "draft",
                "payload": payload,
            },
            "module": "consolidation_access",
            "status": "stub",
            "error": str(e),
        }


def _safe_add_group_member(add_member_func, group_id, child_book_id, payload=None):
    """
    兼容不同 add_consolidation_group_member 签名：
    - add_member_func(dict)
    - add_member_func(group_id, payload_dict)
    - add_member_func(group_id=..., book_id=...)
    返回统一结果 dict。
    """
    payload = dict(payload or {})
    if "group_id" not in payload:
        payload["group_id"] = group_id
    if "book_id" not in payload:
        payload["book_id"] = child_book_id
    if "member_book_id" not in payload:
        payload["member_book_id"] = child_book_id
    if "child_book_id" not in payload:
        payload["child_book_id"] = child_book_id

    attempts = [
        lambda: add_member_func(payload),
        lambda: add_member_func(group_id, payload),
        lambda: add_member_func(group_id=group_id, book_id=child_book_id),
        lambda: add_member_func(group_id=group_id, payload=payload),
    ]

    last_err = None
    for fn in attempts:
        try:
            ret = fn()
            if isinstance(ret, dict):
                return ret
            return {"status": "ok", "raw_result": ret}
        except Exception as e:
            last_err = e

    raise last_err

def get_access_grant(grant_id: int) -> Dict[str, Any]:
    rows = _db_exec(
        """
    SELECT id, authorization_no, parent_tenant_id, parent_book_id, child_tenant_id, child_book_id,
           virtual_entity_id, grant_mode, status, effective_from, effective_to,
           approval_doc_no, approval_doc_name, authorization_basis,
           access_granted_at, included_into_virtual_at, created_at, updated_at
    FROM consolidation_access_grants
    WHERE id = :grant_id
    LIMIT 1
    """,
        {"grant_id": grant_id},
        fetch="all",
    )
    if not rows:
        raise ValueError(f"access_grant_not_found:{grant_id}")
    return rows[0]



def _normalize_member_type_for_bind(payload=None):
    payload = dict(payload or {})
    current = payload.get("member_type")

    candidates = [
        current,
        payload.get("type"),
        payload.get("entity_type"),
        "book",
        "company",
        "subsidiary",
        "entity",
        "normal",
    ]

    for v in candidates:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            payload["member_type"] = s
            return payload

    payload["member_type"] = "book"
    return payload


def _json_safe_value(v):
    try:
        import datetime as _dt
        if isinstance(v, (_dt.date, _dt.datetime)):
            return v.isoformat()
    except Exception:
        pass
    return v

def _json_safe_obj(obj):
    if isinstance(obj, dict):
        return {k: _json_safe_obj(_json_safe_value(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe_obj(_json_safe_value(v)) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe_obj(_json_safe_value(v)) for v in obj]
    return _json_safe_value(obj)

def approve_and_activate_access_grant(grant_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        row0 = _db_exec(
            """
            SELECT *
            FROM consolidation_access_grants
            WHERE id = :id
            LIMIT 1
            """,
            {"id": grant_id},
            fetch="one",
        )

        if not row0:
            return {
                "item": None,
                "module": "consolidation_access",
                "status": "not_found",
                "error": "grant_not_found",
            }

        group_id = row0.get("virtual_entity_id")
        child_book_id = row0.get("child_book_id")
        child_tenant_id = row0.get("child_tenant_id")
        bind_payload = _normalize_member_type_for_bind(
            {
                "group_id": group_id,
                "book_id": child_book_id,
                "member_book_id": child_book_id,
                "child_book_id": child_book_id,
                "member_type": "book",
                "status": "active",
                "tenant_id": child_tenant_id,
                "source": "consolidation_access_grant",
                "source_grant_id": grant_id,
            }
        )

        if not group_id:
            return {
                "item": row0,
                "module": "consolidation_access",
                "status": "error",
                "error": "missing_virtual_entity_id",
            }

        if not child_book_id:
            return {
                "item": row0,
                "module": "consolidation_access",
                "status": "error",
                "error": "missing_child_book_id",
            }

        # XINYI_CONS_ACCESS_ALREADY_BOUND_GUARD
        already_bound = False
        already_bound_row = None
        try:
            already_bound_row = _db_exec(
                """
                SELECT id, group_id, book_id
                FROM consolidation_members
                WHERE group_id = :group_id
                  AND book_id = :book_id
                LIMIT 1
                """,
                {
                    "group_id": group_id,
                    "book_id": child_book_id,
                },
                fetch="one",
            )
            already_bound = already_bound_row is not None
        except Exception:
            # 若当前环境无法直接查成员表，则保持兼容，继续走原绑定逻辑
            already_bound = False

        if already_bound:
            member_bind_result = {
                "status": "already_bound",
                "group_id": group_id,
                "book_id": child_book_id,
                "member_id": already_bound_row.get("id") if isinstance(already_bound_row, dict) else None,
                "note": "member already exists in consolidation_members",
            }
        else:
            # --- XINYI_CONS_MEMBER_INSERT_PATCH ---
            # 临时绕过 provider.begin()，直接写 consolidation_members
            existing = _db_exec(
                """
                SELECT id FROM consolidation_members
                WHERE group_id = :group_id
                  AND book_id = :book_id
                LIMIT 1
                """,
                {
                    "group_id": group_id,
                    "book_id": child_book_id,
                },
                fetch="one",
            )

            if existing:
                member_bind_result = {"status": "already_bound"}
            else:
                _db_exec(
                    """
                    INSERT INTO consolidation_members
                    (group_id, book_id, status, created_at)
                    VALUES
                    (:group_id, :book_id, 'active', NOW())
                    """,
                    {
                        "group_id": group_id,
                        "book_id": child_book_id,
                    },
                    fetch="none",
                )

                member_bind_result = {"status": "bound"}
            # --- XINYI_CONS_MEMBER_INSERT_PATCH_END ---

        bind_status = None
        if isinstance(member_bind_result, dict):
            bind_status = member_bind_result.get("status")

        # 若成员纳入失败，则不进入 active
        if bind_status == "error":
            return {
                "item": row0,
                "module": "consolidation_access",
                "status": "error",
                "error": "member_bind_failed",
                "member_bind_result": member_bind_result,
            }

        _db_exec(
            """
            UPDATE consolidation_access_grants
            SET
                status = 'active',
                approved_by = :approved_by,
                approval_doc_no = COALESCE(:approval_doc_no, approval_doc_no),
                approval_doc_name = COALESCE(:approval_doc_name, approval_doc_name),
                access_granted_at = NOW(),
                included_into_virtual_at = NOW()
            WHERE id = :id
            """,
            {
                "id": grant_id,
                "approved_by": payload.get("approved_by"),
                "approval_doc_no": payload.get("approval_doc_no"),
                "approval_doc_name": payload.get("approval_doc_name"),
            },
            fetch="none",
        )

        row = _db_exec(
            "SELECT * FROM consolidation_access_grants WHERE id = :id LIMIT 1",
            {"id": grant_id},
            fetch="one",
        )

        result = {
            "item": row,
            "module": "consolidation_access",
            "status": "ok" if row else "not_found",
            "member_bind_result": member_bind_result,
        }
        result["evidence_path"] = _write_cons_access_evidence("approve_and_activate", grant_id, payload, result)
        return _json_safe_obj(result)

    except Exception as e:
        result = {
            "item": {
                "id": grant_id,
                "status": "active",
                "payload": payload,
            },
            "module": "consolidation_access",
            "status": "stub",
            "error": str(e),
        }
        return _json_safe_obj(result)


def revoke_access_grant(grant_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _db_exec(
            """
            UPDATE consolidation_access_grants
            SET
                status = 'revoked',
                revoked_by = :revoked_by
            WHERE id = :id
            """,
            {
                "id": grant_id,
                "revoked_by": payload.get("revoked_by"),
            },
            fetch="none",
        )
        row = _db_exec(
            "SELECT * FROM consolidation_access_grants WHERE id = :id LIMIT 1",
            {"id": grant_id},
            fetch="one",
        )
        return {
            "item": row,
            "module": "consolidation_access",
            "status": "ok" if row else "not_found",
        }
    except Exception as e:
        return {
            "item": {
                "id": grant_id,
                "status": "revoked",
                "payload": payload,
            },
            "module": "consolidation_access",
            "status": "stub",
            "error": str(e),
        }
