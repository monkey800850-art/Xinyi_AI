import json
import re
from typing import Dict, List

from sqlalchemy import bindparam, text

from app.db import get_engine


class MasterDataError(RuntimeError):
    pass


MASTER_TABLES = {
    "departments": "departments",
    "persons": "persons",
    "entities": "entities",
    "projects": "projects",
    "bank_accounts": "bank_accounts",
}

ALLOWED_AUX_TYPES = {"", "department", "person", "entity", "project", "bank_account"}
MASTER_META_PREFIX = "master_meta:"

MASTER_EXTRA_FIELDS = {
    "departments": ["parent_code", "is_independent_accounting"],
    "persons": ["department_code", "id_no"],
    "entities": [
        "entity_type",
        "unified_social_credit_code",
        "contact_name",
        "contact_phone",
        "address",
    ],
    "projects": ["start_date", "end_date"],
    "bank_accounts": ["bank_name", "account_no"],
}

MASTER_CODE_RULES = {
    "departments": (re.compile(r"^D[0-9]{3,}$"), "部门编码格式不符合规则（示例：D001）"),
    "persons": (re.compile(r"^(P|PS)[0-9]{3,}$"), "个人编码格式不符合规则（示例：P001 或 PS001）"),
    "entities": (re.compile(r"^E[0-9]{3,}$"), "单位编码格式不符合规则（示例：E001）"),
    "projects": (re.compile(r"^PJ[0-9]{3,}$"), "项目编码格式不符合规则（示例：PJ001）"),
    "bank_accounts": (re.compile(r"^BA[0-9]{3,}$"), "银行账户编码格式不符合规则（示例：BA001）"),
}


def _parse_book_id(value) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise MasterDataError("book_id required")
    try:
        book_id = int(raw)
    except Exception as err:
        raise MasterDataError("book_id must be integer") from err
    if book_id <= 0:
        raise MasterDataError("book_id must be positive")
    return book_id


def _resolve_master_table(kind: str) -> str:
    key = (kind or "").strip().lower()
    table = MASTER_TABLES.get(key)
    if not table:
        raise MasterDataError("master_kind_unsupported")
    return table


def _meta_rule_key(kind: str, item_id: int) -> str:
    return f"{MASTER_META_PREFIX}{kind}:{item_id}"


def _normalize_code(code: str) -> str:
    return str(code or "").strip().rstrip(".")


def _find_parent_by_prefix(code: str, existing_codes: set) -> str:
    c = _normalize_code(code)
    if not c:
        return ""
    if "." in c:
        parts = [p for p in c.split(".") if p]
        while len(parts) > 1:
            parts = parts[:-1]
            p = ".".join(parts)
            if p in existing_codes:
                return p
    for cut in range(len(c) - 2, 1, -2):
        p = c[:cut]
        if p in existing_codes:
            return p
    return ""


def _parse_aux_type_values(raw) -> List[str]:
    if isinstance(raw, list):
        values = [str(v or "").strip().lower() for v in raw]
    else:
        text_value = str(raw or "").strip()
        if not text_value:
            return []
        text_value = text_value.replace("，", ",").replace(";", ",").replace("|", ",")
        values = [v.strip().lower() for v in text_value.split(",")]
    out: List[str] = []
    for value in values:
        if value in ALLOWED_AUX_TYPES and value and value not in out:
            out.append(value)
    return out


def _join_aux_types(values: List[str]) -> str:
    normalized = []
    for value in values or []:
        v = str(value or "").strip().lower()
        if v in ALLOWED_AUX_TYPES and v and v not in normalized:
            normalized.append(v)
    return ",".join(normalized)


def _load_subject_aux_nodes(conn, book_id: int) -> Dict[str, Dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT s.code, s.parent_code, s.is_enabled, s.requires_auxiliary, s.requires_bank_account_aux,
                   COALESCE(r.rule_value, '') AS aux_type,
                   COALESCE(rm.rule_value, '') AS aux_types
            FROM subjects s
            LEFT JOIN sys_rules r ON r.rule_key = CONCAT('subject_aux_type:', s.code)
            LEFT JOIN sys_rules rm ON rm.rule_key = CONCAT('subject_aux_types:', s.code)
            WHERE s.book_id=:book_id
            """
        ),
        {"book_id": book_id},
    ).fetchall()
    by_code: Dict[str, Dict[str, object]] = {}
    for row in rows:
        code = _normalize_code(row.code)
        if not code:
            continue
        own_aux_types = _parse_aux_type_values(row.aux_types)
        if not own_aux_types:
            own_aux_types = _parse_aux_type_values(row.aux_type)
        by_code[code] = {
            "code": code,
            "parent_code": _normalize_code(row.parent_code),
            "is_enabled": int(row.is_enabled or 0),
            "requires_auxiliary": int(row.requires_auxiliary or 0),
            "requires_bank_account_aux": int(row.requires_bank_account_aux or 0),
            "aux_types": own_aux_types,
        }
    return by_code


def _build_subject_children_map(by_code: Dict[str, Dict[str, object]]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {}
    all_codes = set(by_code.keys())
    for code, node in by_code.items():
        parent = str(node.get("parent_code") or "").strip()
        if not parent:
            parent = _find_parent_by_prefix(code, all_codes)
        if not parent or parent not in all_codes:
            continue
        children.setdefault(parent, []).append(code)
    return children


def _parent_effective(code: str, by_code: Dict[str, Dict[str, object]]):
    code_n = _normalize_code(code)
    current = by_code.get(code_n) or {}
    parent = str(current.get("parent_code") or "").strip()
    if not parent:
        parent = _find_parent_by_prefix(code_n, set(by_code.keys()))
    while parent:
        node = by_code.get(parent)
        if not node:
            break
        node_aux_types = list(node.get("aux_types") or [])
        if int(node.get("requires_auxiliary") or 0) == 1 and node_aux_types:
            return node
        parent = str(node.get("parent_code") or "").strip()
    return None


def _subject_effective_payload(code: str, by_code: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    code_n = _normalize_code(code)
    node = by_code.get(code_n)
    if not node:
        raise MasterDataError("subject_not_found")

    own_aux_types = list(node.get("aux_types") or [])
    effective_aux_types = list(own_aux_types)
    inherited_from = ""
    parent_cfg = _parent_effective(code_n, by_code)
    if not effective_aux_types and parent_cfg:
        effective_aux_types = list(parent_cfg.get("aux_types") or [])
        inherited_from = str(parent_cfg.get("code") or "")

    consistency = "ok"
    consistency_message = ""
    if parent_cfg:
        if int(node.get("requires_auxiliary") or 0) != 1:
            consistency = "mismatch"
            consistency_message = "父级科目已启用辅助核算，下级科目需保持一致"
        elif set(own_aux_types) != set(parent_cfg.get("aux_types") or []):
            consistency = "mismatch"
            consistency_message = (
                "父级科目已启用辅助核算，下级科目辅助维度需保持一致："
                + _join_aux_types(list(parent_cfg.get("aux_types") or []))
            )

    return {
        "code": code_n,
        "parent_code": str(node.get("parent_code") or ""),
        "requires_auxiliary": int(node.get("requires_auxiliary") or 0),
        "requires_bank_account_aux": int(node.get("requires_bank_account_aux") or 0),
        "aux_type": (own_aux_types[0] if own_aux_types else ""),
        "aux_types": own_aux_types,
        "aux_types_text": _join_aux_types(own_aux_types),
        "effective_aux_type": (effective_aux_types[0] if effective_aux_types else ""),
        "effective_aux_types": effective_aux_types,
        "effective_aux_types_text": _join_aux_types(effective_aux_types),
        "inherited_from": inherited_from,
        "consistency": consistency,
        "consistency_message": consistency_message,
    }


def _sanitize_extra(kind: str, payload: Dict[str, object]) -> Dict[str, object]:
    allow = MASTER_EXTRA_FIELDS.get(kind, [])
    out: Dict[str, object] = {}
    for key in allow:
        out[key] = str(payload.get(key) or "").strip()

    if kind == "bank_accounts":
        # Backward compatibility: accept legacy bank_no input.
        legacy_no = str(payload.get("bank_no") or "").strip()
        if not out.get("account_no") and legacy_no:
            out["account_no"] = legacy_no

    if kind == "entities":
        et = str(out.get("entity_type") or "").strip().lower()
        if et and et not in ("customer", "supplier", "other"):
            raise MasterDataError("entity_type unsupported")
        if not et:
            raise MasterDataError("单位类型必填")
        out["entity_type"] = et
    if kind == "departments":
        out["is_independent_accounting"] = (
            1 if str(payload.get("is_independent_accounting", "0")).strip() in ("1", "true", "True") else 0
        )
    if kind == "persons":
        out["id_no"] = str(out.get("id_no") or "").strip()
    if kind == "projects":
        start_date = str(out.get("start_date") or "").strip()
        end_date = str(out.get("end_date") or "").strip()
        if start_date:
            try:
                from datetime import date
                date.fromisoformat(start_date)
            except Exception as err:
                raise MasterDataError("项目开始日期格式非法，应为YYYY-MM-DD") from err
        if end_date:
            try:
                from datetime import date
                date.fromisoformat(end_date)
            except Exception as err:
                raise MasterDataError("项目结束日期格式非法，应为YYYY-MM-DD") from err
        if start_date and end_date and end_date < start_date:
            raise MasterDataError("项目结束日期不能早于开始日期")
    if kind == "bank_accounts":
        if not str(out.get("bank_name") or "").strip():
            raise MasterDataError("开户行必填")
        if not str(out.get("account_no") or "").strip():
            raise MasterDataError("银行账号必填")
    return out


def _table_columns(conn, table: str) -> set:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table
            """
        ),
        {"table": table},
    ).fetchall()
    return {str(r[0] or "").strip().lower() for r in rows}


def _load_meta_map(conn, kind: str, item_ids: List[int]) -> Dict[int, Dict[str, object]]:
    if not item_ids:
        return {}
    keys = [_meta_rule_key(kind, item_id) for item_id in item_ids]
    rows = conn.execute(
        text(
            """
            SELECT rule_key, rule_value
            FROM sys_rules
            WHERE rule_key IN :keys
            """
        ).bindparams(bindparam("keys", expanding=True)),
        {"keys": keys},
    ).fetchall()
    out: Dict[int, Dict[str, object]] = {}
    for row in rows:
        rule_key = str(row.rule_key or "")
        try:
            item_id = int(rule_key.split(":")[-1])
        except Exception:
            continue
        try:
            meta = json.loads(row.rule_value or "{}")
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        out[item_id] = meta
    return out


def _save_meta(conn, kind: str, item_id: int, extra: Dict[str, object]):
    rule_key = _meta_rule_key(kind, item_id)
    if not extra:
        conn.execute(text("DELETE FROM sys_rules WHERE rule_key=:rule_key"), {"rule_key": rule_key})
        return
    conn.execute(
        text(
            """
            INSERT INTO sys_rules (rule_key, rule_value, description)
            VALUES (:rule_key, :rule_value, :description)
            ON DUPLICATE KEY UPDATE
                rule_value=VALUES(rule_value),
                description=VALUES(description),
                updated_at=NOW()
            """
        ),
        {
            "rule_key": rule_key,
            "rule_value": json.dumps(extra, ensure_ascii=False),
            "description": f"基础资料扩展字段:{kind}",
        },
    )


def list_master_items(kind: str, params: Dict[str, str]) -> Dict[str, object]:
    table = _resolve_master_table(kind)
    book_id = _parse_book_id(params.get("book_id"))
    q = (params.get("q") or "").strip()
    include_hidden = str(params.get("include_hidden", "0")).strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
    )

    engine = get_engine()
    with engine.connect() as conn:
        table_cols = _table_columns(conn, table)
        extra_fields = MASTER_EXTRA_FIELDS.get(kind, [])
        select_cols = ["id", "code", "name", "is_enabled"]
        for base_flag in ("is_system_seeded", "is_hidden", "seed_batch_code"):
            if base_flag in table_cols:
                select_cols.append(base_flag)
        for f in extra_fields:
            if f in table_cols:
                select_cols.append(f)
        sql = f"""
            SELECT {", ".join(select_cols)}
            FROM {table}
            WHERE book_id=:book_id
        """
        sql_params = {"book_id": book_id}
        if q:
            sql += " AND (code LIKE :q OR name LIKE :q)"
            sql_params["q"] = f"%{q}%"
        if "is_hidden" in table_cols and not include_hidden:
            sql += " AND COALESCE(is_hidden, 0)=0"
        sql += " ORDER BY code ASC LIMIT 300"
        rows = conn.execute(text(sql), sql_params).fetchall()
        item_ids = [int(row.id) for row in rows]
        meta_map = _load_meta_map(conn, kind, item_ids)

    items: List[Dict[str, object]] = []
    for row in rows:
        meta = meta_map.get(int(row.id), {})
        items.append(
            {
                "id": row.id,
                "code": row.code or "",
                "name": row.name or "",
                "is_enabled": int(row.is_enabled or 0),
                "extra": meta,
                "parent_code": str(
                    getattr(row, "parent_code", None) if hasattr(row, "parent_code") else (meta.get("parent_code") or "")
                ),
                "is_independent_accounting": int(
                    getattr(row, "is_independent_accounting", None)
                    if hasattr(row, "is_independent_accounting")
                    else (meta.get("is_independent_accounting") or 0)
                ),
                "department_code": str(
                    getattr(row, "department_code", None) if hasattr(row, "department_code") else (meta.get("department_code") or "")
                ),
                "id_no": str(getattr(row, "id_no", None) if hasattr(row, "id_no") else (meta.get("id_no") or "")),
                "entity_type": str(
                    getattr(row, "entity_type", None) if hasattr(row, "entity_type") else (meta.get("entity_type") or "")
                ),
                "unified_social_credit_code": str(
                    getattr(row, "unified_social_credit_code", None)
                    if hasattr(row, "unified_social_credit_code")
                    else (meta.get("unified_social_credit_code") or "")
                ),
                "contact_name": str(
                    getattr(row, "contact_name", None) if hasattr(row, "contact_name") else (meta.get("contact_name") or "")
                ),
                "contact_phone": str(
                    getattr(row, "contact_phone", None) if hasattr(row, "contact_phone") else (meta.get("contact_phone") or "")
                ),
                "address": str(getattr(row, "address", None) if hasattr(row, "address") else (meta.get("address") or "")),
                "start_date": str(
                    getattr(row, "start_date", None).isoformat()
                    if hasattr(row, "start_date") and getattr(row, "start_date", None)
                    else (meta.get("start_date") or "")
                ),
                "end_date": str(
                    getattr(row, "end_date", None).isoformat()
                    if hasattr(row, "end_date") and getattr(row, "end_date", None)
                    else (meta.get("end_date") or "")
                ),
                "bank_name": str(
                    getattr(row, "bank_name", None) if hasattr(row, "bank_name") else (meta.get("bank_name") or "")
                ),
                "account_no": str(
                    getattr(row, "account_no", None)
                    if hasattr(row, "account_no")
                    else (meta.get("account_no") or meta.get("bank_no") or "")
                ),
                "bank_no": str(
                    getattr(row, "account_no", None)
                    if hasattr(row, "account_no")
                    else (meta.get("account_no") or meta.get("bank_no") or "")
                ),
                "is_system_seeded": int(
                    getattr(row, "is_system_seeded", None)
                    if hasattr(row, "is_system_seeded")
                    else (meta.get("is_system_seeded") or 0)
                ),
                "is_hidden": int(
                    getattr(row, "is_hidden", None)
                    if hasattr(row, "is_hidden")
                    else (meta.get("is_hidden") or 0)
                ),
                "seed_batch_code": str(
                    getattr(row, "seed_batch_code", None)
                    if hasattr(row, "seed_batch_code")
                    else (meta.get("seed_batch_code") or "")
                ),
            }
        )
    return {
        "kind": kind,
        "book_id": book_id,
        "include_hidden": 1 if include_hidden else 0,
        "items": items,
        "extra_fields": MASTER_EXTRA_FIELDS.get(kind, []),
    }


def upsert_master_item(kind: str, payload: Dict[str, object]) -> Dict[str, object]:
    table = _resolve_master_table(kind)
    book_id = _parse_book_id(payload.get("book_id"))
    code = str(payload.get("code") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not code:
        raise MasterDataError("code required")
    if not name:
        raise MasterDataError("name required")
    rule = MASTER_CODE_RULES.get(kind)
    if rule and not rule[0].match(code):
        raise MasterDataError(rule[1])
    is_enabled = 1 if str(payload.get("is_enabled", "1")).strip() in ("1", "true", "True") else 0
    is_system_seeded = (
        1 if str(payload.get("is_system_seeded", "0")).strip() in ("1", "true", "True") else 0
    )
    is_hidden = 1 if str(payload.get("is_hidden", "0")).strip() in ("1", "true", "True") else 0
    seed_batch_code = str(payload.get("seed_batch_code") or "").strip()
    extra = _sanitize_extra(kind, payload)

    item_id = payload.get("id")
    engine = get_engine()
    with engine.begin() as conn:
        table_cols = _table_columns(conn, table)
        check_sql = f"SELECT id FROM {table} WHERE book_id=:book_id AND code=:code"
        check_params = {"book_id": book_id, "code": code}
        if item_id:
            check_sql += " AND id<>:id"
            check_params["id"] = int(item_id)
        dup = conn.execute(text(check_sql + " LIMIT 1"), check_params).fetchone()
        if dup:
            raise MasterDataError("编码已存在")

        if kind == "departments":
            parent_code = str(extra.get("parent_code") or "").strip()
            if parent_code:
                parent = conn.execute(
                    text(
                        "SELECT id FROM departments WHERE book_id=:book_id AND code=:code LIMIT 1"
                    ),
                    {"book_id": book_id, "code": parent_code},
                ).fetchone()
                if not parent:
                    raise MasterDataError("上级部门不存在")
                if item_id:
                    self_row = conn.execute(
                        text(
                            "SELECT code FROM departments WHERE id=:id AND book_id=:book_id LIMIT 1"
                        ),
                        {"id": int(item_id), "book_id": book_id},
                    ).fetchone()
                    if self_row and str(self_row.code or "").strip() == parent_code:
                        raise MasterDataError("上级部门不能为自身")
        if kind == "persons":
            dep_code = str(extra.get("department_code") or "").strip()
            if dep_code:
                dep = conn.execute(
                    text(
                        "SELECT id FROM departments WHERE book_id=:book_id AND code=:code LIMIT 1"
                    ),
                    {"book_id": book_id, "code": dep_code},
                ).fetchone()
                if not dep:
                    raise MasterDataError("所属部门不存在")

        if item_id:
            update_parts = ["code=:code", "name=:name", "is_enabled=:is_enabled", "updated_at=NOW()"]
            update_params = {
                "id": int(item_id),
                "book_id": book_id,
                "code": code,
                "name": name,
                "is_enabled": is_enabled,
            }
            if "is_system_seeded" in table_cols:
                update_parts.append("is_system_seeded=:is_system_seeded")
                update_params["is_system_seeded"] = is_system_seeded
            if "is_hidden" in table_cols:
                update_parts.append("is_hidden=:is_hidden")
                update_params["is_hidden"] = is_hidden
            if "seed_batch_code" in table_cols:
                update_parts.append("seed_batch_code=:seed_batch_code")
                update_params["seed_batch_code"] = seed_batch_code or None
            for key, value in extra.items():
                if key in table_cols:
                    update_parts.append(f"{key}=:{key}")
                    update_params[key] = value
            conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET {", ".join(update_parts)}
                    WHERE id=:id AND book_id=:book_id
                    """
                ),
                update_params,
            )
            saved_id = int(item_id)
        else:
            insert_cols = ["book_id", "code", "name", "is_enabled"]
            insert_vals = [":book_id", ":code", ":name", ":is_enabled"]
            insert_params = {
                "book_id": book_id,
                "code": code,
                "name": name,
                "is_enabled": is_enabled,
            }
            if "is_system_seeded" in table_cols:
                insert_cols.append("is_system_seeded")
                insert_vals.append(":is_system_seeded")
                insert_params["is_system_seeded"] = is_system_seeded
            if "is_hidden" in table_cols:
                insert_cols.append("is_hidden")
                insert_vals.append(":is_hidden")
                insert_params["is_hidden"] = is_hidden
            if "seed_batch_code" in table_cols:
                insert_cols.append("seed_batch_code")
                insert_vals.append(":seed_batch_code")
                insert_params["seed_batch_code"] = seed_batch_code or None
            for key, value in extra.items():
                if key in table_cols:
                    insert_cols.append(key)
                    insert_vals.append(f":{key}")
                    insert_params[key] = value
            result = conn.execute(
                text(
                    f"""
                    INSERT INTO {table} ({", ".join(insert_cols)})
                    VALUES ({", ".join(insert_vals)})
                    """
                ),
                insert_params,
            )
            saved_id = int(result.lastrowid)

        _save_meta(conn, kind, saved_id, extra)

    return {
        "id": saved_id,
        "kind": kind,
        "book_id": book_id,
        "code": code,
        "name": name,
        "is_enabled": is_enabled,
        "extra": extra,
        "parent_code": str(extra.get("parent_code") or ""),
        "is_independent_accounting": int(extra.get("is_independent_accounting") or 0),
        "department_code": str(extra.get("department_code") or ""),
        "id_no": str(extra.get("id_no") or ""),
        "entity_type": str(extra.get("entity_type") or ""),
        "unified_social_credit_code": str(extra.get("unified_social_credit_code") or ""),
        "contact_name": str(extra.get("contact_name") or ""),
        "contact_phone": str(extra.get("contact_phone") or ""),
        "address": str(extra.get("address") or ""),
        "start_date": str(extra.get("start_date") or ""),
        "end_date": str(extra.get("end_date") or ""),
        "bank_name": str(extra.get("bank_name") or ""),
        "account_no": str(extra.get("account_no") or extra.get("bank_no") or ""),
        "bank_no": str(extra.get("account_no") or extra.get("bank_no") or ""),
        "is_system_seeded": is_system_seeded,
        "is_hidden": is_hidden,
        "seed_batch_code": seed_batch_code,
    }


def list_subject_aux_configs(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _parse_book_id(params.get("book_id"))
    q = (params.get("q") or "").strip()

    sql = """
        SELECT s.code, s.name, s.is_enabled, s.level, s.parent_code,
               s.requires_auxiliary, s.requires_bank_account_aux,
               COALESCE(r.rule_value, '') AS aux_type,
               COALESCE(rm.rule_value, '') AS aux_types
        FROM subjects s
        LEFT JOIN sys_rules r ON r.rule_key = CONCAT('subject_aux_type:', s.code)
        LEFT JOIN sys_rules rm ON rm.rule_key = CONCAT('subject_aux_types:', s.code)
        WHERE s.book_id=:book_id
    """
    sql_params = {"book_id": book_id}
    if q:
        sql += " AND (s.code LIKE :q OR s.name LIKE :q)"
        sql_params["q"] = f"%{q}%"
    sql += " ORDER BY s.code ASC LIMIT 500"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), sql_params).fetchall()
        by_code = _load_subject_aux_nodes(conn, book_id)

    items: List[Dict[str, object]] = []
    for row in rows:
        code = _normalize_code(row.code)
        subject_payload = _subject_effective_payload(code, by_code)

        items.append(
            {
                "code": code,
                "name": row.name or "",
                "is_enabled": int(row.is_enabled or 0),
                "level": int(row.level or 0),
                "parent_code": _normalize_code(row.parent_code),
                "requires_auxiliary": int(row.requires_auxiliary or 0),
                "requires_bank_account_aux": int(row.requires_bank_account_aux or 0),
                "aux_type": subject_payload["aux_type"],
                "aux_types": subject_payload["aux_types"],
                "aux_types_text": subject_payload["aux_types_text"],
                "effective_aux_type": subject_payload["effective_aux_type"],
                "effective_aux_types": subject_payload["effective_aux_types"],
                "effective_aux_types_text": subject_payload["effective_aux_types_text"],
                "inherited_from": subject_payload["inherited_from"],
                "consistency": subject_payload["consistency"],
                "consistency_message": subject_payload["consistency_message"],
            }
        )
    return {"book_id": book_id, "items": items}


def get_subject_aux_effective(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _parse_book_id(params.get("book_id"))
    subject_code = _normalize_code(params.get("subject_code") or "")
    if not subject_code:
        raise MasterDataError("subject_code required")
    engine = get_engine()
    with engine.connect() as conn:
        by_code = _load_subject_aux_nodes(conn, book_id)
    payload = _subject_effective_payload(subject_code, by_code)
    payload["book_id"] = book_id
    return payload


def save_subject_aux_config(payload: Dict[str, object]) -> Dict[str, object]:
    book_id = _parse_book_id(payload.get("book_id"))
    subject_code = _normalize_code(payload.get("subject_code") or "")
    if not subject_code:
        raise MasterDataError("subject_code required")

    requires_auxiliary = (
        1 if str(payload.get("requires_auxiliary", "0")).strip() in ("1", "true", "True") else 0
    )
    requires_bank_account_aux = (
        1
        if str(payload.get("requires_bank_account_aux", "0")).strip() in ("1", "true", "True")
        else 0
    )
    aux_types = _parse_aux_type_values(payload.get("aux_types"))
    if not aux_types:
        aux_types = _parse_aux_type_values(payload.get("aux_type"))
    if requires_bank_account_aux == 1 and "bank_account" not in aux_types:
        aux_types.append("bank_account")
    aux_types_text = _join_aux_types(aux_types)
    if requires_auxiliary == 1 and not aux_types:
        raise MasterDataError("aux_type required when requires_auxiliary=1")
    if requires_auxiliary != 1:
        aux_types = []
        aux_types_text = ""
    aux_type = aux_types[0] if aux_types else ""

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, parent_code FROM subjects WHERE book_id=:book_id AND code=:code LIMIT 1"),
            {"book_id": book_id, "code": subject_code},
        ).fetchone()
        if not row:
            raise MasterDataError("subject_not_found")

        by_code = _load_subject_aux_nodes(conn, book_id)
        if subject_code not in by_code:
            raise MasterDataError("subject_not_found")

        # Apply editing value to an in-memory view for full-chain consistency checks.
        by_code[subject_code]["requires_auxiliary"] = requires_auxiliary
        by_code[subject_code]["requires_bank_account_aux"] = requires_bank_account_aux
        by_code[subject_code]["aux_types"] = list(aux_types)

        parent_cfg = _parent_effective(subject_code, by_code)
        if parent_cfg:
            parent_aux_types = list(parent_cfg.get("aux_types") or [])
            if requires_auxiliary != 1:
                raise MasterDataError("父级科目已启用辅助核算，下级科目不得关闭辅助核算")
            if set(aux_types) != set(parent_aux_types):
                raise MasterDataError(
                    "父级科目已启用辅助核算，下级科目辅助维度必须一致（父级维度："
                    + _join_aux_types(parent_aux_types)
                    + "）"
                )

        # Downward strong consistency: if current subject enables aux with dimensions,
        # all descendants must keep enabled and identical dimensions.
        if requires_auxiliary == 1 and aux_types:
            children_map = _build_subject_children_map(by_code)
            stack = list(children_map.get(subject_code, []))
            seen = set()
            while stack:
                child_code = stack.pop()
                if child_code in seen:
                    continue
                seen.add(child_code)
                stack.extend(children_map.get(child_code, []))

                child = by_code.get(child_code) or {}
                child_requires = int(child.get("requires_auxiliary") or 0)
                child_aux_types = list(child.get("aux_types") or [])
                if child_requires != 1:
                    raise MasterDataError(
                        f"下级科目[{child_code}]未启用辅助核算；父级已启用时下级必须一致"
                    )
                if set(child_aux_types) != set(aux_types):
                    raise MasterDataError(
                        f"下级科目[{child_code}]辅助维度冲突（期望：{_join_aux_types(aux_types)}，实际：{_join_aux_types(child_aux_types)}）"
                    )

        conn.execute(
            text(
                """
                UPDATE subjects
                SET requires_auxiliary=:requires_auxiliary,
                    requires_bank_account_aux=:requires_bank_account_aux,
                    updated_at=NOW()
                WHERE book_id=:book_id AND code=:code
                """
            ),
            {
                "book_id": book_id,
                "code": subject_code,
                "requires_auxiliary": requires_auxiliary,
                "requires_bank_account_aux": requires_bank_account_aux,
            },
        )

        rule_key = f"subject_aux_type:{subject_code}"
        rule_key_multi = f"subject_aux_types:{subject_code}"
        if aux_type:
            conn.execute(
                text(
                    """
                    INSERT INTO sys_rules (rule_key, rule_value, description)
                    VALUES (:rule_key, :rule_value, :description)
                    ON DUPLICATE KEY UPDATE
                        rule_value=VALUES(rule_value),
                        description=VALUES(description),
                        updated_at=NOW()
                    """
                ),
                {
                    "rule_key": rule_key,
                    "rule_value": aux_type,
                    "description": "科目辅助核算维度挂接",
                },
            )
        else:
            conn.execute(text("DELETE FROM sys_rules WHERE rule_key=:rule_key"), {"rule_key": rule_key})
        if aux_types_text:
            conn.execute(
                text(
                    """
                    INSERT INTO sys_rules (rule_key, rule_value, description)
                    VALUES (:rule_key, :rule_value, :description)
                    ON DUPLICATE KEY UPDATE
                        rule_value=VALUES(rule_value),
                        description=VALUES(description),
                        updated_at=NOW()
                    """
                ),
                {
                    "rule_key": rule_key_multi,
                    "rule_value": aux_types_text,
                    "description": "科目辅助核算维度挂接(多维)",
                },
            )
        else:
            conn.execute(text("DELETE FROM sys_rules WHERE rule_key=:rule_key"), {"rule_key": rule_key_multi})

    return {
        "book_id": book_id,
        "subject_code": subject_code,
        "requires_auxiliary": requires_auxiliary,
        "requires_bank_account_aux": requires_bank_account_aux,
        "aux_type": aux_type,
        "aux_types": aux_types,
        "aux_types_text": aux_types_text,
    }
