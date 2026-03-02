from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationManageError(RuntimeError):
    pass


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {str(r[0]).strip().lower() for r in rows if r and r[0]}


def _normalize_bool(value) -> int:
    return 0 if str(value or "").strip().lower() in ("0", "false", "no") else 1


def _parse_int(value, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationManageError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationManageError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationManageError(f"{field}_invalid")
    return parsed


def _upsert_sys_rule(conn, key: str, value: str, description: str):
    cols = _table_columns(conn, "sys_rules")
    if not cols:
        raise ConsolidationManageError("sys_rules_not_ready")
    if "updated_at" in cols:
        conn.execute(
            text(
                """
                INSERT INTO sys_rules (rule_key, rule_value, description)
                VALUES (:rule_key, :rule_value, :description)
                ON DUPLICATE KEY UPDATE
                  rule_value=VALUES(rule_value),
                  description=VALUES(description),
                  updated_at=CURRENT_TIMESTAMP
                """
            ),
            {"rule_key": key, "rule_value": value, "description": description},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO sys_rules (rule_key, rule_value, description)
                VALUES (:rule_key, :rule_value, :description)
                ON DUPLICATE KEY UPDATE
                  rule_value=VALUES(rule_value),
                  description=VALUES(description)
                """
            ),
            {"rule_key": key, "rule_value": value, "description": description},
        )


def _book_map(conn) -> Dict[int, Dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT b.id, b.name, b.accounting_standard, b.is_enabled,
                   COALESCE(rc.rule_value, CONCAT('BOOK-', LPAD(b.id, 4, '0'))) AS book_code
            FROM books b
            LEFT JOIN sys_rules rc ON rc.rule_key=CONCAT('book_meta:code:', b.id)
            ORDER BY b.id ASC
            """
        )
    ).fetchall()
    out: Dict[int, Dict[str, object]] = {}
    for r in rows:
        bid = int(r.id)
        out[bid] = {
            "book_id": bid,
            "book_name": str(r.name or f"账套{bid}"),
            "book_code": str(r.book_code or f"BOOK-{bid:04d}"),
            "accounting_standard": str(r.accounting_standard or ""),
            "is_enabled": int(r.is_enabled or 0),
        }
    return out


def _legal_entity_map(conn) -> Dict[int, Dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT id, entity_code, entity_name, entity_kind, book_id, status, is_enabled
            FROM legal_entities
            WHERE status='active' AND is_enabled=1
            ORDER BY id ASC
            """
        )
    ).fetchall()
    out: Dict[int, Dict[str, object]] = {}
    for r in rows:
        eid = int(r.id)
        out[eid] = {
            "entity_id": eid,
            "entity_code": str(r.entity_code or ""),
            "entity_name": str(r.entity_name or ""),
            "entity_kind": str(r.entity_kind or "").strip().lower(),
            "book_id": int(r.book_id) if r.book_id is not None else None,
            "status": str(r.status or ""),
            "is_enabled": int(r.is_enabled or 0),
        }
    return out


def _ensure_legal_entity(conn, book_id: int, entity_kind: str) -> Dict[str, object]:
    row = conn.execute(
        text(
            """
            SELECT id, entity_code, entity_name, entity_kind, book_id
            FROM legal_entities
            WHERE book_id=:book_id
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    ).fetchone()
    if row:
        kind = str(row.entity_kind or "").strip().lower()
        if kind and kind != entity_kind:
            raise ConsolidationManageError("book_entity_kind_mismatch")
        return {
            "entity_id": int(row.id),
            "entity_code": str(row.entity_code or ""),
            "entity_name": str(row.entity_name or ""),
            "entity_kind": entity_kind,
            "book_id": int(row.book_id),
        }

    b = conn.execute(
        text("SELECT id, name FROM books WHERE id=:book_id LIMIT 1"),
        {"book_id": book_id},
    ).fetchone()
    if not b:
        raise ConsolidationManageError("book_not_found")

    prefix = "LE" if entity_kind == "legal" else "NLE"
    entity_code = f"{prefix}-{book_id}"
    entity_name = str(b.name or f"账套{book_id}")
    try:
        result = conn.execute(
            text(
                """
                INSERT INTO legal_entities (entity_code, entity_name, entity_kind, book_id, status, is_enabled)
                VALUES (:entity_code, :entity_name, :entity_kind, :book_id, 'active', 1)
                """
            ),
            {
                "entity_code": entity_code,
                "entity_name": entity_name,
                "entity_kind": entity_kind,
                "book_id": book_id,
            },
        )
        entity_id = int(result.lastrowid)
    except Exception:
        row2 = conn.execute(
            text("SELECT id, entity_code, entity_name, entity_kind, book_id FROM legal_entities WHERE book_id=:book_id LIMIT 1"),
            {"book_id": book_id},
        ).fetchone()
        if not row2:
            raise
        entity_id = int(row2.id)
        entity_code = str(row2.entity_code or entity_code)
        entity_name = str(row2.entity_name or entity_name)
    return {
        "entity_id": entity_id,
        "entity_code": entity_code,
        "entity_name": entity_name,
        "entity_kind": entity_kind,
        "book_id": int(book_id),
    }


def _ensure_natural_group(conn, legal_entity: Dict[str, object]) -> int:
    gcols = _table_columns(conn, "consolidation_groups")
    mcols = _table_columns(conn, "consolidation_group_members")
    if not gcols or not mcols:
        raise ConsolidationManageError("consolidation_model_not_ready")

    row = conn.execute(
        text(
            """
            SELECT cg.id
            FROM consolidation_groups cg
            JOIN consolidation_group_members m ON m.group_id=cg.id
            WHERE cg.group_type='natural_legal'
              AND cg.status='active'
              AND cg.is_enabled=1
              AND m.member_type='LEGAL'
              AND m.member_entity_id=:legal_entity_id
              AND m.is_enabled=1
              AND m.status='active'
            LIMIT 1
            """
        ),
        {"legal_entity_id": int(legal_entity["entity_id"])},
    ).fetchone()
    if row:
        return int(row.id)

    code = f"NATURAL-LEGAL-{int(legal_entity['book_id'])}"
    name = f"天然合并-{legal_entity.get('entity_name') or legal_entity.get('book_id')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cols = ["group_code", "group_name"]
        vals = [":group_code", ":group_name"]
        params = {"group_code": code, "group_name": name}
        if "group_type" in gcols:
            cols.append("group_type")
            vals.append("'natural_legal'")
        if "status" in gcols:
            cols.append("status")
            vals.append("'active'")
        if "is_enabled" in gcols:
            cols.append("is_enabled")
            vals.append("1")
        if "note" in gcols:
            cols.append("note")
            vals.append(":note")
            params["note"] = "非法人归属法人真源组"
        if "created_at" in gcols:
            cols.append("created_at")
            vals.append(":now")
            params["now"] = now
        if "updated_at" in gcols:
            cols.append("updated_at")
            vals.append(":now")
            params["now"] = now
        result = conn.execute(
            text(f"INSERT INTO consolidation_groups ({', '.join(cols)}) VALUES ({', '.join(vals)})"),
            params,
        )
        group_id = int(result.lastrowid)
    except Exception:
        row2 = conn.execute(
            text("SELECT id FROM consolidation_groups WHERE group_code=:code LIMIT 1"),
            {"code": code},
        ).fetchone()
        if not row2:
            raise
        group_id = int(row2.id)

    exists = conn.execute(
        text(
            """
            SELECT id FROM consolidation_group_members
            WHERE group_id=:group_id AND member_type='LEGAL' AND member_entity_id=:entity_id AND is_enabled=1 AND status='active'
            LIMIT 1
            """
        ),
        {"group_id": group_id, "entity_id": int(legal_entity["entity_id"])},
    ).fetchone()
    if not exists:
        cols = ["group_id", "member_type"]
        vals = [":group_id", "'LEGAL'"]
        params = {"group_id": group_id}
        if "member_book_id" in mcols:
            cols.append("member_book_id")
            vals.append(":member_book_id")
            params["member_book_id"] = int(legal_entity["book_id"])
        if "book_id" in mcols:
            cols.append("book_id")
            vals.append(":book_id")
            params["book_id"] = int(legal_entity["book_id"])
        if "member_entity_id" in mcols:
            cols.append("member_entity_id")
            vals.append(":member_entity_id")
            params["member_entity_id"] = int(legal_entity["entity_id"])
        if "effective_from" in mcols:
            cols.append("effective_from")
            vals.append("NULL")
        if "effective_to" in mcols:
            cols.append("effective_to")
            vals.append("NULL")
        if "valid_from" in mcols:
            cols.append("valid_from")
            vals.append("NULL")
        if "valid_to" in mcols:
            cols.append("valid_to")
            vals.append("NULL")
        if "status" in mcols:
            cols.append("status")
            vals.append("'active'")
        if "is_enabled" in mcols:
            cols.append("is_enabled")
            vals.append("1")
        if "note" in mcols:
            cols.append("note")
            vals.append(":note")
            params["note"] = "法人主账套"
        if "created_at" in mcols:
            cols.append("created_at")
            vals.append(":now")
            params["now"] = now
        if "updated_at" in mcols:
            cols.append("updated_at")
            vals.append(":now")
            params["now"] = now
        conn.execute(
            text(f"INSERT INTO consolidation_group_members ({', '.join(cols)}) VALUES ({', '.join(vals)})"),
            params,
        )
    return group_id


def list_relation_overview(_params: Dict[str, object]) -> Dict[str, object]:
    provider = get_connection_provider()
    with provider.connect() as conn:
        books = _book_map(conn)
        legal_entities = _legal_entity_map(conn)

        group_legal: Dict[int, int] = {}
        rows_legal = conn.execute(
            text(
                """
                SELECT m.group_id, m.member_entity_id
                FROM consolidation_group_members m
                JOIN consolidation_groups g ON g.id=m.group_id
                WHERE g.group_type='natural_legal'
                  AND g.status='active'
                  AND g.is_enabled=1
                  AND m.member_type='LEGAL'
                  AND m.status='active'
                  AND m.is_enabled=1
                """
            )
        ).fetchall()
        for r in rows_legal:
            group_legal[int(r.group_id)] = int(r.member_entity_id)

        nonlegal_parent: Dict[int, Dict[str, object]] = {}
        rows_nonlegal = conn.execute(
            text(
                """
                SELECT m.id AS member_id, m.group_id, m.member_entity_id, m.member_book_id
                FROM consolidation_group_members m
                JOIN consolidation_groups g ON g.id=m.group_id
                WHERE g.group_type='natural_legal'
                  AND g.status='active'
                  AND g.is_enabled=1
                  AND m.member_type='NON_LEGAL'
                  AND m.status='active'
                  AND m.is_enabled=1
                """
            )
        ).fetchall()
        for r in rows_nonlegal:
            entity_id = int(r.member_entity_id) if r.member_entity_id is not None else 0
            if not entity_id:
                continue
            nonlegal_parent[entity_id] = {
                "group_id": int(r.group_id),
                "member_id": int(r.member_id),
                "parent_legal_entity_id": group_legal.get(int(r.group_id)),
            }

        legal_books: List[Dict[str, object]] = []
        non_legal_books: List[Dict[str, object]] = []
        children_by_legal_book: Dict[int, List[int]] = {}
        legal_book_ids: set[int] = set()
        non_legal_book_ids: set[int] = set()
        for entity in legal_entities.values():
            if not entity.get("book_id"):
                continue
            b = books.get(int(entity["book_id"]))
            if not b:
                continue
            if entity["entity_kind"] == "legal":
                legal_book_ids.add(int(b["book_id"]))
                legal_books.append(
                    {
                        "book_id": int(b["book_id"]),
                        "book_code": b["book_code"],
                        "book_name": b["book_name"],
                        "entity_id": int(entity["entity_id"]),
                        "entity_code": entity["entity_code"],
                    }
                )
            elif entity["entity_kind"] == "non_legal":
                non_legal_book_ids.add(int(b["book_id"]))
                rel = nonlegal_parent.get(int(entity["entity_id"])) or {}
                parent_entity_id = rel.get("parent_legal_entity_id")
                parent_book_id = None
                parent_book_name = ""
                if parent_entity_id and int(parent_entity_id) in legal_entities:
                    parent_ent = legal_entities[int(parent_entity_id)]
                    parent_book_id = parent_ent.get("book_id")
                    pb = books.get(int(parent_book_id or 0))
                    parent_book_name = str((pb or {}).get("book_name") or "")
                if parent_book_id:
                    children_by_legal_book.setdefault(int(parent_book_id), []).append(int(b["book_id"]))
                non_legal_books.append(
                    {
                        "book_id": int(b["book_id"]),
                        "book_code": b["book_code"],
                        "book_name": b["book_name"],
                        "entity_id": int(entity["entity_id"]),
                        "entity_code": entity["entity_code"],
                        "parent_legal_book_id": int(parent_book_id) if parent_book_id else None,
                        "parent_legal_book_name": parent_book_name,
                    }
                )

        # Backward-compatible fallback:
        # some legacy books may not yet have legal_entities rows; expose them as legal candidates
        # unless they are already identified as non_legal books.
        for b in books.values():
            book_id = int(b["book_id"])
            if book_id in legal_book_ids:
                continue
            if book_id in non_legal_book_ids:
                continue
            if int(b.get("is_enabled") or 0) != 1:
                continue
            legal_books.append(
                {
                    "book_id": book_id,
                    "book_code": b["book_code"],
                    "book_name": b["book_name"],
                    "entity_id": None,
                    "entity_code": "",
                }
            )
            legal_book_ids.add(book_id)

        for it in legal_books:
            children = children_by_legal_book.get(int(it["book_id"])) or []
            it["non_legal_children_count"] = len(children)
            it["non_legal_children_book_ids"] = children

        virtual_rows = conn.execute(
            text(
                """
                SELECT v.id, v.virtual_code, v.virtual_name, v.status, v.is_enabled,
                       COALESCE(r.rule_value, '') AS group_id
                FROM virtual_entities v
                LEFT JOIN sys_rules r ON r.rule_key=CONCAT('virtual_group:', v.id)
                ORDER BY v.id ASC
                """
            )
        ).fetchall()
        virtual_entities: List[Dict[str, object]] = []
        for v in virtual_rows:
            gid = int(v.group_id) if str(v.group_id or "").strip().isdigit() else None
            member_count = 0
            if gid:
                c = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS c
                        FROM consolidation_group_members
                        WHERE group_id=:group_id
                          AND member_type='LEGAL'
                          AND is_enabled=1
                          AND status='active'
                        """
                    ),
                    {"group_id": gid},
                ).fetchone()
                member_count = int(c.c or 0) if c else 0
            virtual_entities.append(
                {
                    "id": int(v.id),
                    "virtual_code": str(v.virtual_code or ""),
                    "virtual_name": str(v.virtual_name or ""),
                    "status": str(v.status or ""),
                    "is_enabled": int(v.is_enabled or 0),
                    "group_id": gid,
                    "member_count": member_count,
                }
            )

        return {
            "legal_books": legal_books,
            "non_legal_books": non_legal_books,
            "virtual_entities": virtual_entities,
        }


def bind_non_legal_to_legal(payload: Dict[str, object]) -> Dict[str, object]:
    non_legal_book_id = _parse_int(payload.get("non_legal_book_id"), "non_legal_book_id")
    legal_book_id = _parse_int(payload.get("legal_book_id"), "legal_book_id")
    if non_legal_book_id == legal_book_id:
        raise ConsolidationManageError("non_legal_and_legal_book_cannot_same")

    provider = get_connection_provider()
    with provider.begin() as conn:
        mcols = _table_columns(conn, "consolidation_group_members")
        if not mcols:
            raise ConsolidationManageError("consolidation_model_not_ready")

        non_legal_entity = _ensure_legal_entity(conn, non_legal_book_id, "non_legal")
        legal_entity = _ensure_legal_entity(conn, legal_book_id, "legal")
        group_id = _ensure_natural_group(conn, legal_entity)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        set_items = ["m.is_enabled=0", "m.status='inactive'"]
        if "updated_at" in mcols:
            set_items.append("m.updated_at=:now")
        set_clause = ", ".join(set_items)
        conn.execute(
            text(
                f"""
                UPDATE consolidation_group_members m
                JOIN consolidation_groups g ON g.id=m.group_id
                SET {set_clause}
                WHERE g.group_type='natural_legal'
                  AND m.member_type='NON_LEGAL'
                  AND m.member_entity_id=:non_legal_entity_id
                  AND m.is_enabled=1
                  AND m.status='active'
                """
            ),
            {"now": now, "non_legal_entity_id": int(non_legal_entity["entity_id"])},
        )

        exists = conn.execute(
            text(
                """
                SELECT id
                FROM consolidation_group_members
                WHERE group_id=:group_id
                  AND member_type='NON_LEGAL'
                  AND member_entity_id=:entity_id
                  AND is_enabled=1
                  AND status='active'
                LIMIT 1
                """
            ),
            {"group_id": group_id, "entity_id": int(non_legal_entity["entity_id"])},
        ).fetchone()
        if not exists:
            cols = ["group_id", "member_type"]
            vals = [":group_id", "'NON_LEGAL'"]
            params = {"group_id": group_id}
            if "member_book_id" in mcols:
                cols.append("member_book_id")
                vals.append(":member_book_id")
                params["member_book_id"] = non_legal_book_id
            if "book_id" in mcols:
                cols.append("book_id")
                vals.append(":book_id")
                params["book_id"] = non_legal_book_id
            if "member_entity_id" in mcols:
                cols.append("member_entity_id")
                vals.append(":member_entity_id")
                params["member_entity_id"] = int(non_legal_entity["entity_id"])
            if "effective_from" in mcols:
                cols.append("effective_from")
                vals.append("NULL")
            if "effective_to" in mcols:
                cols.append("effective_to")
                vals.append("NULL")
            if "valid_from" in mcols:
                cols.append("valid_from")
                vals.append("NULL")
            if "valid_to" in mcols:
                cols.append("valid_to")
                vals.append("NULL")
            if "status" in mcols:
                cols.append("status")
                vals.append("'active'")
            if "is_enabled" in mcols:
                cols.append("is_enabled")
                vals.append("1")
            if "note" in mcols:
                cols.append("note")
                vals.append(":note")
                params["note"] = "非法人归属法人"
            if "created_at" in mcols:
                cols.append("created_at")
                vals.append(":now")
                params["now"] = now
            if "updated_at" in mcols:
                cols.append("updated_at")
                vals.append(":now")
                params["now"] = now
            conn.execute(
                text(f"INSERT INTO consolidation_group_members ({', '.join(cols)}) VALUES ({', '.join(vals)})"),
                params,
            )

    return {
        "non_legal_book_id": non_legal_book_id,
        "legal_book_id": legal_book_id,
        "natural_group_id": group_id,
        "status": "ok",
    }


def _ensure_virtual_group_ready(
    conn,
    *,
    virtual_id: int,
    virtual_code: str,
    virtual_name: str,
    is_enabled: int,
) -> int:
    gcols = _table_columns(conn, "consolidation_groups")
    if not gcols:
        raise ConsolidationManageError("consolidation_model_not_ready")

    rule_key = f"virtual_group:{int(virtual_id)}"
    rule_row = conn.execute(
        text("SELECT rule_value FROM sys_rules WHERE rule_key=:rule_key LIMIT 1"),
        {"rule_key": rule_key},
    ).fetchone()
    group_id = int(rule_row.rule_value) if rule_row and str(rule_row.rule_value or "").strip().isdigit() else None

    if group_id:
        group_row = conn.execute(
            text("SELECT id FROM consolidation_groups WHERE id=:id LIMIT 1"),
            {"id": int(group_id)},
        ).fetchone()
        if group_row:
            _upsert_sys_rule(conn, rule_key, str(int(group_id)), "virtual entity default consolidation group")
            return int(group_id)

    group_code = f"VIRTUAL-{virtual_code}"
    by_code = conn.execute(
        text("SELECT id FROM consolidation_groups WHERE group_code=:group_code LIMIT 1"),
        {"group_code": group_code},
    ).fetchone()
    if by_code:
        group_id = int(by_code.id)
        set_items: List[str] = []
        if "group_type" in gcols:
            set_items.append("group_type='virtual_entity'")
        if "status" in gcols:
            set_items.append("status='active'")
        if "is_enabled" in gcols:
            set_items.append("is_enabled=1")
        if set_items:
            conn.execute(
                text(
                    f"""
                    UPDATE consolidation_groups
                    SET {", ".join(set_items)}
                    WHERE id=:group_id
                    """
                ),
                {"group_id": int(group_id)},
            )
        _upsert_sys_rule(conn, rule_key, str(int(group_id)), "virtual entity default consolidation group")
        return int(group_id)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    g_insert_cols = ["group_code", "group_name"]
    g_insert_vals = [":group_code", ":group_name"]
    g_params: Dict[str, object] = {
        "group_code": group_code,
        "group_name": f"虚拟合并-{virtual_name}",
    }
    if "group_type" in gcols:
        g_insert_cols.append("group_type")
        g_insert_vals.append("'virtual_entity'")
    if "status" in gcols:
        g_insert_cols.append("status")
        g_insert_vals.append("'active'")
    if "is_enabled" in gcols:
        g_insert_cols.append("is_enabled")
        g_insert_vals.append(":is_enabled")
        g_params["is_enabled"] = is_enabled
    if "note" in gcols:
        g_insert_cols.append("note")
        g_insert_vals.append(":note")
        g_params["note"] = "虚拟主体默认合并组"
    if "created_at" in gcols:
        g_insert_cols.append("created_at")
        g_insert_vals.append(":now")
        g_params["now"] = now
    if "updated_at" in gcols:
        g_insert_cols.append("updated_at")
        g_insert_vals.append(":now")
        g_params["now"] = now
    gres = conn.execute(
        text(
            f"""
            INSERT INTO consolidation_groups ({', '.join(g_insert_cols)})
            VALUES ({', '.join(g_insert_vals)})
            """
        ),
        g_params,
    )
    group_id = int(gres.lastrowid)
    _upsert_sys_rule(conn, rule_key, str(int(group_id)), "virtual entity default consolidation group")
    return int(group_id)


def create_virtual_entity(payload: Dict[str, object]) -> Dict[str, object]:
    virtual_code = str(payload.get("virtual_code") or "").strip()
    virtual_name = str(payload.get("virtual_name") or "").strip()
    note = str(payload.get("note") or "").strip() or None
    is_enabled = _normalize_bool(payload.get("is_enabled", 1))
    if not virtual_code:
        raise ConsolidationManageError("virtual_code_required")
    if not virtual_name:
        raise ConsolidationManageError("virtual_name_required")

    provider = get_connection_provider()
    with provider.begin() as conn:
        vcols = _table_columns(conn, "virtual_entities")
        if not vcols:
            raise ConsolidationManageError("consolidation_model_not_ready")

        exists = conn.execute(
            text("SELECT id FROM virtual_entities WHERE virtual_code=:code LIMIT 1"),
            {"code": virtual_code},
        ).fetchone()
        if exists:
            raise ConsolidationManageError("virtual_code_duplicated")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        v_insert_cols = ["virtual_code", "virtual_name"]
        v_insert_vals = [":code", ":name"]
        v_params: Dict[str, object] = {"code": virtual_code, "name": virtual_name}
        if "status" in vcols:
            v_insert_cols.append("status")
            v_insert_vals.append("'active'")
        if "is_enabled" in vcols:
            v_insert_cols.append("is_enabled")
            v_insert_vals.append(":is_enabled")
            v_params["is_enabled"] = is_enabled
        if "note" in vcols:
            v_insert_cols.append("note")
            v_insert_vals.append(":note")
            v_params["note"] = note
        if "created_at" in vcols:
            v_insert_cols.append("created_at")
            v_insert_vals.append(":now")
            v_params["now"] = now
        if "updated_at" in vcols:
            v_insert_cols.append("updated_at")
            v_insert_vals.append(":now")
            v_params["now"] = now
        vres = conn.execute(
            text(
                f"""
                INSERT INTO virtual_entities ({', '.join(v_insert_cols)})
                VALUES ({', '.join(v_insert_vals)})
                """
            ),
            v_params,
        )
        virtual_id = int(vres.lastrowid)
        group_id = _ensure_virtual_group_ready(
            conn,
            virtual_id=int(virtual_id),
            virtual_code=virtual_code,
            virtual_name=virtual_name,
            is_enabled=is_enabled,
        )

    return {
        "id": virtual_id,
        "virtual_code": virtual_code,
        "virtual_name": virtual_name,
        "is_enabled": is_enabled,
        "group_id": group_id,
    }


def _virtual_entity_with_group(conn, virtual_id: int) -> Dict[str, object]:
    row = conn.execute(
        text(
            """
            SELECT v.id, v.virtual_code, v.virtual_name, v.status, v.is_enabled, v.note,
                   COALESCE(r.rule_value, '') AS group_id
            FROM virtual_entities v
            LEFT JOIN sys_rules r ON r.rule_key=CONCAT('virtual_group:', v.id)
            WHERE v.id=:id
            LIMIT 1
            """
        ),
        {"id": virtual_id},
    ).fetchone()
    if not row:
        raise ConsolidationManageError("virtual_entity_not_found")
    gid = int(row.group_id) if str(row.group_id or "").strip().isdigit() else None
    if not gid:
        gid = _ensure_virtual_group_ready(
            conn,
            virtual_id=int(row.id),
            virtual_code=str(row.virtual_code or ""),
            virtual_name=str(row.virtual_name or f"虚拟主体{int(row.id)}"),
            is_enabled=int(row.is_enabled or 0) or 1,
        )
    return {
        "id": int(row.id),
        "virtual_code": str(row.virtual_code or ""),
        "virtual_name": str(row.virtual_name or ""),
        "status": str(row.status or ""),
        "is_enabled": int(row.is_enabled or 0),
        "note": str(row.note or ""),
        "group_id": gid,
    }


def get_virtual_entity_detail(virtual_id: int) -> Dict[str, object]:
    provider = get_connection_provider()
    with provider.connect() as conn:
        entity = _virtual_entity_with_group(conn, virtual_id)
        return entity


def list_virtual_entity_members(virtual_id: int) -> Dict[str, object]:
    provider = get_connection_provider()
    with provider.connect() as conn:
        mcols = _table_columns(conn, "consolidation_group_members")
        member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
        if not member_book_col:
            raise ConsolidationManageError("consolidation_model_not_ready")
        member_note_select = "m.note" if "note" in mcols else "''"
        entity = _virtual_entity_with_group(conn, virtual_id)
        group_id = entity.get("group_id")
        if not group_id:
            return {"virtual_entity": entity, "items": []}
        rows = conn.execute(
            text(
                f"""
                SELECT m.id, m.group_id, m.{member_book_col} AS member_book_id, m.member_entity_id, m.member_type, m.status, m.is_enabled, {member_note_select} AS note,
                       le.entity_name, le.entity_code,
                       b.name AS book_name,
                       COALESCE(rc.rule_value, CONCAT('BOOK-', LPAD(b.id, 4, '0'))) AS book_code
                FROM consolidation_group_members m
                LEFT JOIN legal_entities le ON le.id=m.member_entity_id
                LEFT JOIN books b ON b.id=m.{member_book_col}
                LEFT JOIN sys_rules rc ON rc.rule_key=CONCAT('book_meta:code:', b.id)
                WHERE m.group_id=:group_id
                  AND m.member_type='LEGAL'
                ORDER BY m.id ASC
                """
            ),
            {"group_id": int(group_id)},
        ).fetchall()
        items = []
        for r in rows:
            items.append(
                {
                    "id": int(r.id),
                    "member_book_id": int(r.member_book_id) if r.member_book_id is not None else None,
                    "member_entity_id": int(r.member_entity_id) if r.member_entity_id is not None else None,
                    "member_type": str(r.member_type or ""),
                    "status": str(r.status or ""),
                    "is_enabled": int(r.is_enabled or 0),
                    "note": str(r.note or ""),
                    "book_name": str(r.book_name or ""),
                    "book_code": str(r.book_code or ""),
                    "entity_name": str(r.entity_name or ""),
                    "entity_code": str(r.entity_code or ""),
                }
            )
        return {"virtual_entity": entity, "items": items}


def add_virtual_entity_member(virtual_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    legal_book_id = _parse_int(payload.get("legal_book_id"), "legal_book_id")
    provider = get_connection_provider()
    with provider.begin() as conn:
        mcols = _table_columns(conn, "consolidation_group_members")
        member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
        if not member_book_col:
            raise ConsolidationManageError("consolidation_model_not_ready")
        entity = _virtual_entity_with_group(conn, virtual_id)
        group_id = entity.get("group_id")
        if not group_id:
            raise ConsolidationManageError("virtual_group_not_ready")
        legal_entity = _ensure_legal_entity(conn, legal_book_id, "legal")

        exists = conn.execute(
            text(
                """
                SELECT id
                FROM consolidation_group_members
                WHERE group_id=:group_id
                  AND member_type='LEGAL'
                  AND member_entity_id=:member_entity_id
                  AND is_enabled=1
                  AND status='active'
                LIMIT 1
                """
            ),
            {"group_id": int(group_id), "member_entity_id": int(legal_entity["entity_id"])},
        ).fetchone()
        if exists:
            raise ConsolidationManageError("virtual_member_duplicated")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols = ["group_id", member_book_col]
        vals = [":group_id", ":member_book_id"]
        params: Dict[str, object] = {
            "group_id": int(group_id),
            "member_book_id": legal_book_id,
        }
        if "book_id" in mcols and member_book_col != "book_id":
            cols.append("book_id")
            vals.append(":legacy_book_id")
            params["legacy_book_id"] = legal_book_id
        if "member_entity_id" in mcols:
            cols.append("member_entity_id")
            vals.append(":member_entity_id")
            params["member_entity_id"] = int(legal_entity["entity_id"])
        if "member_type" in mcols:
            cols.append("member_type")
            vals.append("'LEGAL'")
        if "effective_from" in mcols:
            cols.append("effective_from")
            vals.append("NULL")
        elif "valid_from" in mcols:
            cols.append("valid_from")
            vals.append("NULL")
        if "effective_to" in mcols:
            cols.append("effective_to")
            vals.append("NULL")
        elif "valid_to" in mcols:
            cols.append("valid_to")
            vals.append("NULL")
        if "status" in mcols:
            cols.append("status")
            vals.append("'active'")
        if "is_enabled" in mcols:
            cols.append("is_enabled")
            vals.append("1")
        if "note" in mcols:
            cols.append("note")
            vals.append(":note")
            params["note"] = "虚拟主体法人成员"
        if "created_at" in mcols:
            cols.append("created_at")
            vals.append(":now")
            params["now"] = now
        if "updated_at" in mcols:
            cols.append("updated_at")
            vals.append(":now")
            params["now"] = now
        res = conn.execute(
            text(
                f"""
                INSERT INTO consolidation_group_members ({', '.join(cols)})
                VALUES ({', '.join(vals)})
                """
            ),
            params,
        )
        member_id = int(res.lastrowid)
    return {"id": member_id, "virtual_id": virtual_id, "legal_book_id": legal_book_id, "status": "active"}


def disable_virtual_entity_member(member_id: int) -> Dict[str, object]:
    mid = _parse_int(member_id, "member_id")
    provider = get_connection_provider()
    with provider.begin() as conn:
        row = conn.execute(
            text("SELECT id, member_type FROM consolidation_group_members WHERE id=:id LIMIT 1"),
            {"id": mid},
        ).fetchone()
        if not row:
            raise ConsolidationManageError("member_not_found")
        if str(row.member_type or "").strip().upper() != "LEGAL":
            raise ConsolidationManageError("member_type_not_supported")
        conn.execute(
            text(
                """
                UPDATE consolidation_group_members
                SET is_enabled=0, status='inactive', updated_at=CURRENT_TIMESTAMP
                WHERE id=:id
                """
            ),
            {"id": mid},
        )
    return {"id": mid, "status": "inactive"}
