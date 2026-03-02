import json
from datetime import date
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine
from app.db_router import get_connection_provider
from app.services.audit_service import log_audit


class SystemError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] = None):
        super().__init__(message)
        self.errors = errors or []


def _require(cond: bool, errors: List[Dict[str, object]], field: str, msg: str):
    if not cond:
        errors.append({"field": field, "message": msg})


def list_users(params: Dict[str, str]) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT u.id, u.username, u.display_name, u.is_enabled
                FROM sys_users u
                ORDER BY u.id DESC
                """
            )
        ).fetchall()

        role_map = {}
        role_rows = conn.execute(
            text(
                """
                SELECT ur.user_id, r.id AS role_id, r.code, r.name
                FROM sys_user_roles ur
                JOIN sys_roles r ON r.id = ur.role_id
                """
            )
        ).fetchall()

    for r in role_rows:
        role_map.setdefault(r.user_id, []).append(
            {"id": r.role_id, "code": r.code, "name": r.name}
        )

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "username": r.username,
                "display_name": r.display_name or "",
                "is_enabled": int(r.is_enabled),
                "roles": role_map.get(r.id, []),
            }
        )

    return {"items": items}


def create_or_update_user(payload: Dict[str, object], operator: str, role: str) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    uid = payload.get("id")
    username = (payload.get("username") or "").strip()
    display_name = (payload.get("display_name") or "").strip()
    is_enabled = payload.get("is_enabled", 1)

    _require(username, errors, "username", "必填")
    if errors:
        raise SystemError("validation_error", errors)

    try:
        is_enabled = 1 if int(is_enabled) == 1 else 0
    except Exception:
        raise SystemError("validation_error", [{"field": "is_enabled", "message": "格式非法"}])

    engine = get_engine()
    with engine.begin() as conn:
        if uid:
            conn.execute(
                text(
                    """
                    UPDATE sys_users
                    SET username=:username, display_name=:display_name,
                        is_enabled=:is_enabled, updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": uid,
                    "username": username,
                    "display_name": display_name,
                    "is_enabled": is_enabled,
                },
            )
            user_id = uid
            action = "update"
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO sys_users (username, display_name, is_enabled)
                    VALUES (:username, :display_name, :is_enabled)
                    """
                ),
                {
                    "username": username,
                    "display_name": display_name,
                    "is_enabled": is_enabled,
                },
            )
            user_id = result.lastrowid
            action = "create"

    log_audit("system", f"user_{action}", "user", int(user_id), operator, role, {"username": username})
    return {"id": user_id}


def set_user_enabled(user_id: int, is_enabled: int, operator: str, role: str) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE sys_users SET is_enabled=:v, updated_at=NOW() WHERE id=:id"),
            {"id": user_id, "v": 1 if is_enabled else 0},
        )
    log_audit("system", "user_enabled", "user", user_id, operator, role, {"is_enabled": 1 if is_enabled else 0})
    return {"id": user_id, "is_enabled": 1 if is_enabled else 0}


def set_user_roles(user_id: int, role_ids: List[int], operator: str, role: str) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sys_user_roles WHERE user_id=:id"), {"id": user_id})
        for rid in role_ids:
            conn.execute(
                text("INSERT INTO sys_user_roles (user_id, role_id) VALUES (:uid, :rid)"),
                {"uid": user_id, "rid": rid},
            )
    log_audit("system", "user_roles", "user", user_id, operator, role, {"roles": role_ids})
    return {"id": user_id, "role_ids": role_ids}


def list_roles(params: Dict[str, str]) -> Dict[str, object]:
    tenant_id = (params.get("tenant_id") or "").strip() or None
    provider = get_connection_provider()
    with provider.connect(tenant_id=tenant_id) as conn:
        rows = conn.execute(
            text("SELECT id, code, name, description, data_scope, is_enabled FROM sys_roles ORDER BY id DESC")
        ).fetchall()
        perm_rows = conn.execute(
            text("SELECT role_id, perm_key FROM sys_role_permissions ORDER BY role_id")
        ).fetchall()

    perm_map: Dict[int, List[str]] = {}
    for r in perm_rows:
        perm_map.setdefault(r.role_id, []).append(r.perm_key)

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "description": r.description or "",
                "data_scope": r.data_scope or "ALL",
                "is_enabled": int(r.is_enabled),
                "permissions": perm_map.get(r.id, []),
            }
        )

    return {"items": items}


def create_or_update_role(payload: Dict[str, object], operator: str, role: str) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    rid = payload.get("id")
    code = (payload.get("code") or "").strip()
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    data_scope = (payload.get("data_scope") or "ALL").strip().upper()
    is_enabled = payload.get("is_enabled", 1)

    _require(code, errors, "code", "必填")
    _require(name, errors, "name", "必填")
    if errors:
        raise SystemError("validation_error", errors)

    try:
        is_enabled = 1 if int(is_enabled) == 1 else 0
    except Exception:
        raise SystemError("validation_error", [{"field": "is_enabled", "message": "格式非法"}])

    engine = get_engine()
    with engine.begin() as conn:
        if rid:
            conn.execute(
                text(
                    """
                    UPDATE sys_roles
                    SET code=:code, name=:name, description=:description,
                        data_scope=:data_scope, is_enabled=:is_enabled, updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": rid,
                    "code": code,
                    "name": name,
                    "description": description,
                    "data_scope": data_scope,
                    "is_enabled": is_enabled,
                },
            )
            role_id = rid
            action = "update"
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO sys_roles (code, name, description, data_scope, is_enabled)
                    VALUES (:code, :name, :description, :data_scope, :is_enabled)
                    """
                ),
                {
                    "code": code,
                    "name": name,
                    "description": description,
                    "data_scope": data_scope,
                    "is_enabled": is_enabled,
                },
            )
            role_id = result.lastrowid
            action = "create"

    log_audit("system", f"role_{action}", "role", int(role_id), operator, role, {"code": code})
    return {"id": role_id}


def set_role_permissions(role_id: int, perms: List[str], operator: str, role: str) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sys_role_permissions WHERE role_id=:id"), {"id": role_id})
        for p in perms:
            if not p:
                continue
            conn.execute(
                text("INSERT INTO sys_role_permissions (role_id, perm_key) VALUES (:rid, :perm)"),
                {"rid": role_id, "perm": p},
            )

    log_audit("system", "role_permissions", "role", role_id, operator, role, {"permissions": perms})
    return {"id": role_id, "permissions": perms}


def list_rules(params: Dict[str, str]) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, rule_key, rule_value, description FROM sys_rules ORDER BY id DESC")
        ).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "rule_key": r.rule_key,
                "rule_value": r.rule_value or "",
                "description": r.description or "",
            }
        )
    return {"items": items}


def upsert_rule(payload: Dict[str, object], operator: str, role: str) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    rule_key = (payload.get("rule_key") or "").strip()
    rule_value = payload.get("rule_value")
    description = (payload.get("description") or "").strip()

    _require(rule_key, errors, "rule_key", "必填")
    if errors:
        raise SystemError("validation_error", errors)

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM sys_rules WHERE rule_key=:key"),
            {"key": rule_key},
        ).fetchone()
        if row:
            conn.execute(
                text(
                    """
                    UPDATE sys_rules
                    SET rule_value=:rule_value, description=:description, updated_at=NOW()
                    WHERE rule_key=:rule_key
                    """
                ),
                {
                    "rule_key": rule_key,
                    "rule_value": rule_value,
                    "description": description,
                },
            )
            rule_id = row.id
            action = "update"
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO sys_rules (rule_key, rule_value, description)
                    VALUES (:rule_key, :rule_value, :description)
                    """
                ),
                {
                    "rule_key": rule_key,
                    "rule_value": rule_value,
                    "description": description,
                },
            )
            rule_id = result.lastrowid
            action = "create"

    log_audit("system", f"rule_{action}", "rule", int(rule_id), operator, role, {"rule_key": rule_key})
    return {"id": rule_id}


def list_audit_logs(params: Dict[str, str]) -> Dict[str, object]:
    module = (params.get("module") or "").strip()
    action = (params.get("action") or "").strip()
    operator = (params.get("operator") or "").strip()
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    sql = "SELECT id, module, action, entity_type, entity_id, operator, operator_role, detail, created_at FROM audit_logs WHERE 1=1"
    params_sql: Dict[str, object] = {}

    if module:
        sql += " AND module=:module"
        params_sql["module"] = module
    if action:
        sql += " AND action=:action"
        params_sql["action"] = action
    if operator:
        sql += " AND operator=:operator"
        params_sql["operator"] = operator
    if start_date:
        sql += " AND created_at >= :start_date"
        params_sql["start_date"] = start_date
    if end_date:
        sql += " AND created_at <= :end_date"
        params_sql["end_date"] = end_date

    sql += " ORDER BY id DESC LIMIT 200"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params_sql).fetchall()

    items = []
    for r in rows:
        try:
            detail = json.loads(r.detail or "{}")
        except Exception:
            detail = {}
        items.append(
            {
                "id": r.id,
                "module": r.module,
                "action": r.action,
                "entity_type": r.entity_type or "",
                "entity_id": r.entity_id or "",
                "operator": r.operator or "",
                "operator_role": r.operator_role or "",
                "detail": detail,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
        )

    return {"items": items}
