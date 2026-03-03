import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationError(RuntimeError):
    pass


MEMBER_TYPES = {"BOOK", "LEGAL", "NON_LEGAL", "VIRTUAL"}


def _parse_date(value: object, field: str) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception as err:
        raise ConsolidationError(f"{field}_invalid_date") from err


def _normalize_member_type(value: object) -> str:
    t = str(value or "").strip().upper()
    if t not in MEMBER_TYPES:
        raise ConsolidationError("member_type_invalid")
    return t


def _normalize_enable_flag(value: object) -> int:
    if str(value).strip().lower() in ("0", "false", "no"):
        return 0
    return 1


def _table_columns(conn, table_name: str) -> set:
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
    return {str(r[0] or "").strip().lower() for r in rows}


def _column_metadata(conn, table_name: str, column_name: str) -> Dict[str, object]:
    row = conn.execute(
        text(
            """
            SELECT is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    if not row:
        return {}
    is_nullable = row[0] if len(row) > 0 else None
    column_default = row[1] if len(row) > 1 else None
    return {
        "is_nullable": str(is_nullable or "").strip().upper() == "YES",
        "column_default": column_default,
    }


def _assert_consolidation_tables_ready(conn) -> None:
    rows = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name IN ('consolidation_groups', 'consolidation_group_members')
            """
        )
    ).fetchall()
    names = {str(r[0] or "").strip().lower() for r in rows}
    required = {"consolidation_groups", "consolidation_group_members"}
    if names != required:
        raise ConsolidationError("consolidation_model_not_ready")


def create_consolidation_group(payload: Dict[str, object]) -> Dict[str, object]:
    group_code = str(payload.get("group_code") or "").strip()
    group_name = str(payload.get("group_name") or "").strip()
    group_type = str(payload.get("group_type") or "standard").strip()
    note = str(payload.get("note") or "").strip() or None
    is_enabled = _normalize_enable_flag(payload.get("is_enabled", 1))

    if not group_code:
        raise ConsolidationError("group_code_required")
    if not group_name:
        raise ConsolidationError("group_name_required")

    provider = get_connection_provider()
    with provider.begin() as conn:
        _assert_consolidation_tables_ready(conn)
        gcols = _table_columns(conn, "consolidation_groups")
        exists = conn.execute(
            text("SELECT id FROM consolidation_groups WHERE group_code=:group_code LIMIT 1"),
            {"group_code": group_code},
        ).fetchone()
        if exists:
            raise ConsolidationError("group_code_duplicated")

        insert_cols = ["group_code", "group_name"]
        insert_vals = [":group_code", ":group_name"]
        insert_params = {"group_code": group_code, "group_name": group_name}
        if "group_type" in gcols:
            insert_cols.append("group_type")
            insert_vals.append(":group_type")
            insert_params["group_type"] = group_type
        if "note" in gcols:
            insert_cols.append("note")
            insert_vals.append(":note")
            insert_params["note"] = note
        if "status" in gcols:
            insert_cols.append("status")
            insert_vals.append("'active'")
        if "is_enabled" in gcols:
            insert_cols.append("is_enabled")
            insert_vals.append(":is_enabled")
            insert_params["is_enabled"] = is_enabled

        result = conn.execute(
            text(
                f"INSERT INTO consolidation_groups ({', '.join(insert_cols)}) VALUES ({', '.join(insert_vals)})"
            ),
            insert_params,
        )
        gid = int(result.lastrowid)

    return {
        "id": gid,
        "group_code": group_code,
        "group_name": group_name,
        "group_type": group_type,
        "is_enabled": is_enabled,
    }


def _check_member_overlap(
    conn,
    group_id: int,
    member_type: str,
    member_book_id: Optional[int],
    member_entity_id: Optional[int],
    effective_from: Optional[date],
    effective_to: Optional[date],
) -> None:
    mcols = _table_columns(conn, "consolidation_group_members")
    member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
    member_entity_col = "member_entity_id" if "member_entity_id" in mcols else ""
    member_type_col = "member_type" if "member_type" in mcols else ""
    effective_from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
    effective_to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
    if not member_book_col:
        raise ConsolidationError("consolidation_member_model_not_ready")

    select_entity = f", {member_entity_col}" if member_entity_col else ", NULL AS member_entity_id"
    where_entity = (
        f"AND COALESCE({member_entity_col}, 0) = COALESCE(:member_entity_id, 0)"
        if member_entity_col
        else ""
    )
    where_enabled = "AND is_enabled = 1" if "is_enabled" in mcols else ""
    where_member_type = f"AND {member_type_col}=:member_type" if member_type_col else ""

    rows = conn.execute(
        text(
            f"""
            SELECT id,
                   {effective_from_col if effective_from_col else 'NULL'} AS effective_from,
                   {effective_to_col if effective_to_col else 'NULL'} AS effective_to
                   {select_entity}
            FROM consolidation_group_members
            WHERE group_id=:group_id
              {where_member_type}
              AND COALESCE({member_book_col}, 0) = COALESCE(:member_book_id, 0)
              {where_entity}
              {where_enabled}
            """
        ),
        {
            "group_id": group_id,
            "member_type": member_type,
            "member_book_id": member_book_id,
            "member_entity_id": member_entity_id,
        },
    ).fetchall()

    new_start = effective_from or date(1900, 1, 1)
    new_end = effective_to or date(9999, 12, 31)
    for row in rows:
        old_start = row.effective_from
        old_end = row.effective_to
        if isinstance(old_start, datetime):
            old_start = old_start.date()
        if isinstance(old_end, datetime):
            old_end = old_end.date()
        old_start = old_start or date(1900, 1, 1)
        old_end = old_end or date(9999, 12, 31)
        if new_start <= old_end and old_start <= new_end:
            raise ConsolidationError("member_effective_period_overlap")


def _ensure_member_identity_exists(
    conn,
    member_type: str,
    member_book_id: Optional[int],
    member_entity_id: Optional[int],
) -> None:
    if member_type == "BOOK":
        if member_book_id is None:
            raise ConsolidationError("member_book_id_required")
        return

    if member_entity_id is None:
        raise ConsolidationError("member_entity_id_required")

    if member_type in ("LEGAL", "NON_LEGAL"):
        rows = conn.execute(
            text(
                """
                SELECT id, entity_kind, status, is_enabled
                FROM legal_entities
                WHERE id=:id
                """
            ),
            {"id": member_entity_id},
        ).fetchone()
        if not rows:
            raise ConsolidationError("member_legal_entity_not_found")
        kind = str(rows.entity_kind or "").strip().lower()
        expect_kind = "legal" if member_type == "LEGAL" else "non_legal"
        if kind and kind != expect_kind:
            raise ConsolidationError("member_entity_type_mismatch")
        if str(rows.status or "").strip().lower() != "active" or int(rows.is_enabled or 0) != 1:
            raise ConsolidationError("member_entity_not_active")
        return

    if member_type == "VIRTUAL":
        rows = conn.execute(
            text(
                """
                SELECT id, status, is_enabled
                FROM virtual_entities
                WHERE id=:id
                """
            ),
            {"id": member_entity_id},
        ).fetchone()
        if not rows:
            raise ConsolidationError("member_virtual_entity_not_found")
        if str(rows.status or "").strip().lower() != "active" or int(rows.is_enabled or 0) != 1:
            raise ConsolidationError("member_entity_not_active")
        return


def _resolve_member_book_id(
    conn,
    member_type: str,
    member_book_id: Optional[int],
    member_entity_id: Optional[int],
) -> Optional[int]:
    if member_book_id is not None:
        return member_book_id
    if member_entity_id is None:
        return None
    if member_type in ("LEGAL", "NON_LEGAL"):
        row = conn.execute(
            text(
                """
                SELECT book_id
                FROM legal_entities
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": int(member_entity_id)},
        ).fetchone()
        if row and row.book_id is not None:
            return int(row.book_id)
    if member_type == "VIRTUAL":
        row = conn.execute(
            text(
                """
                SELECT book_id
                FROM virtual_entities
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": int(member_entity_id)},
        ).fetchone()
        if row and row.book_id is not None:
            return int(row.book_id)
    return None


def add_consolidation_group_member(group_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    member_type = _normalize_member_type(payload.get("member_type"))
    member_book_id_raw = payload.get("member_book_id")
    member_entity_id_raw = payload.get("member_entity_id")
    note = str(payload.get("note") or "").strip() or None
    is_enabled = _normalize_enable_flag(payload.get("is_enabled", 1))
    effective_from = _parse_date(payload.get("effective_from"), "effective_from")
    effective_to = _parse_date(payload.get("effective_to"), "effective_to")

    member_book_id = None
    member_entity_id = None
    if member_book_id_raw not in (None, ""):
        try:
            member_book_id = int(member_book_id_raw)
        except Exception as err:
            raise ConsolidationError("member_book_id_invalid") from err
    if member_entity_id_raw not in (None, ""):
        try:
            member_entity_id = int(member_entity_id_raw)
        except Exception as err:
            raise ConsolidationError("member_entity_id_invalid") from err

    if effective_from and effective_to and effective_to < effective_from:
        raise ConsolidationError("effective_period_invalid")

    provider = get_connection_provider()
    with provider.begin() as conn:
        _assert_consolidation_tables_ready(conn)
        gcols = _table_columns(conn, "consolidation_groups")
        mcols = _table_columns(conn, "consolidation_group_members")
        member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
        member_entity_col = "member_entity_id" if "member_entity_id" in mcols else ""
        member_type_col = "member_type" if "member_type" in mcols else ""
        effective_from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
        effective_to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
        if not member_book_col:
            raise ConsolidationError("consolidation_member_model_not_ready")
        if member_type != "BOOK" and (not member_entity_col or not member_type_col):
            raise ConsolidationError("consolidation_member_model_not_ready")

        group_row = conn.execute(
            text(
                """
                SELECT id
                FROM consolidation_groups
                WHERE id=:group_id
                """
            ),
            {"group_id": group_id},
        ).fetchone()
        if not group_row:
            raise ConsolidationError("consolidation_group_not_found")
        if "status" in gcols:
            row = conn.execute(
                text("SELECT status, is_enabled FROM consolidation_groups WHERE id=:group_id"),
                {"group_id": group_id},
            ).fetchone()
            if row and str(row.status or "") != "active":
                raise ConsolidationError("consolidation_group_not_found")
            if row and "is_enabled" in gcols and int(row.is_enabled or 0) != 1:
                raise ConsolidationError("consolidation_group_not_found")

        _ensure_member_identity_exists(
            conn,
            member_type=member_type,
            member_book_id=member_book_id,
            member_entity_id=member_entity_id,
        )
        member_book_id = _resolve_member_book_id(
            conn,
            member_type=member_type,
            member_book_id=member_book_id,
            member_entity_id=member_entity_id,
        )

        _check_member_overlap(
            conn,
            group_id=group_id,
            member_type=member_type,
            member_book_id=member_book_id,
            member_entity_id=member_entity_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )

        cols = ["group_id", member_book_col]
        vals = [":group_id", ":member_book_id"]
        params = {"group_id": group_id, "member_book_id": member_book_id}
        if "book_id" in mcols and member_book_col != "book_id":
            legacy_book_meta = _column_metadata(conn, "consolidation_group_members", "book_id")
            legacy_required = bool(legacy_book_meta) and (
                legacy_book_meta.get("is_nullable") is False and legacy_book_meta.get("column_default") is None
            )
            if legacy_required and member_book_id is None:
                raise ConsolidationError("consolidation_member_model_not_ready")
            cols.append("book_id")
            vals.append(":legacy_book_id")
            params["legacy_book_id"] = member_book_id
        if member_type_col:
            cols.append(member_type_col)
            vals.append(":member_type")
            params["member_type"] = member_type
        if member_entity_col:
            cols.append(member_entity_col)
            vals.append(":member_entity_id")
            params["member_entity_id"] = member_entity_id
        if effective_from_col:
            cols.append(effective_from_col)
            vals.append(":effective_from")
            params["effective_from"] = effective_from
        if effective_to_col:
            cols.append(effective_to_col)
            vals.append(":effective_to")
            params["effective_to"] = effective_to
        if "status" in mcols:
            cols.append("status")
            vals.append("'active'")
        if "is_enabled" in mcols:
            cols.append("is_enabled")
            vals.append(":is_enabled")
            params["is_enabled"] = is_enabled
        if "note" in mcols:
            cols.append("note")
            vals.append(":note")
            params["note"] = note

        result = conn.execute(text(f"INSERT INTO consolidation_group_members ({', '.join(cols)}) VALUES ({', '.join(vals)})"), params)
        member_id = int(result.lastrowid)

    return {
        "id": member_id,
        "group_id": group_id,
        "member_type": member_type,
        "member_book_id": member_book_id,
        "member_entity_id": member_entity_id,
        "effective_from": effective_from.isoformat() if effective_from else "",
        "effective_to": effective_to.isoformat() if effective_to else "",
        "is_enabled": is_enabled,
    }


def _build_effective_group_members(conn, group_id: int, q_start: date, q_end: date) -> Dict[str, object]:
    gcols = _table_columns(conn, "consolidation_groups")
    mcols = _table_columns(conn, "consolidation_group_members")
    member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
    member_entity_col = "member_entity_id" if "member_entity_id" in mcols else ""
    member_type_col = "member_type" if "member_type" in mcols else ""
    effective_from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
    effective_to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
    if not member_book_col:
        raise ConsolidationError("consolidation_member_model_not_ready")

    group_type_col = "group_type" if "group_type" in gcols else "NULL"
    group_where = ""
    if "status" in gcols:
        group_where += " AND status='active'"
    if "is_enabled" in gcols:
        group_where += " AND is_enabled=1"
    group_row = conn.execute(
        text(
            f"""
            SELECT id, group_code, group_name, {group_type_col} AS group_type
            FROM consolidation_groups
            WHERE id=:group_id
              {group_where}
            """
        ),
        {"group_id": group_id},
    ).fetchone()
    if not group_row:
        raise ConsolidationError("consolidation_group_not_found")

    member_where = ""
    if "status" in mcols:
        member_where += " AND status='active'"
    if "is_enabled" in mcols:
        member_where += " AND is_enabled=1"
    if effective_from_col:
        member_where += f" AND ({effective_from_col} IS NULL OR {effective_from_col} <= :q_end)"
    if effective_to_col:
        member_where += f" AND ({effective_to_col} IS NULL OR {effective_to_col} >= :q_start)"

    member_entity_select = f"{member_entity_col}" if member_entity_col else "NULL"
    member_effective_from_select = effective_from_col if effective_from_col else "NULL"
    member_effective_to_select = effective_to_col if effective_to_col else "NULL"
    member_type_select = member_type_col if member_type_col else "'BOOK'"
    member_order_type = member_type_col if member_type_col else "'BOOK'"
    rows = conn.execute(
        text(
            f"""
            SELECT id, group_id, {member_book_col} AS member_book_id, {member_entity_select} AS member_entity_id, {member_type_select} AS member_type,
                   {member_effective_from_select} AS effective_from, {member_effective_to_select} AS effective_to,
                   {('is_enabled' if 'is_enabled' in mcols else '1')} AS is_enabled,
                   {('note' if 'note' in mcols else "''")} AS note
            FROM consolidation_group_members
            WHERE group_id=:group_id
              {member_where}
            ORDER BY {member_order_type} ASC, member_book_id ASC, member_entity_id ASC, id ASC
            """
        ),
        {"group_id": group_id, "q_start": q_start, "q_end": q_end},
    ).fetchall()

    members = []
    member_book_ids: List[int] = []
    for r in rows:
        book_id = int(r.member_book_id) if r.member_book_id is not None else None
        if book_id is not None:
            member_book_ids.append(book_id)
        members.append(
            {
                "id": int(r.id),
                "group_id": int(r.group_id),
                "member_type": str(r.member_type or ""),
                "member_book_id": book_id,
                "member_entity_id": int(r.member_entity_id) if r.member_entity_id is not None else None,
                "effective_from": r.effective_from.isoformat() if r.effective_from else "",
                "effective_to": r.effective_to.isoformat() if r.effective_to else "",
                "is_enabled": int(r.is_enabled or 0),
                "note": str(r.note or ""),
            }
        )

    return {
        "group_id": int(group_row.id),
        "group_code": str(group_row.group_code or ""),
        "group_name": str(group_row.group_name or ""),
        "group_type": str(group_row.group_type or ""),
        "query_start": q_start.isoformat(),
        "query_end": q_end.isoformat(),
        "members": members,
        "member_book_ids": sorted(set(member_book_ids)),
    }


def get_effective_group_members(group_id: int, params: Dict[str, object]) -> Dict[str, object]:
    as_of_date = _parse_date(params.get("as_of_date"), "as_of_date")
    period_start = _parse_date(params.get("period_start") or params.get("start_date"), "period_start")
    period_end = _parse_date(params.get("period_end") or params.get("end_date"), "period_end")

    if as_of_date:
        q_start = as_of_date
        q_end = as_of_date
    else:
        q_start = period_start or date.today()
        q_end = period_end or q_start
    if q_end < q_start:
        raise ConsolidationError("query_period_invalid")

    provider = get_connection_provider()
    with provider.connect() as conn:
        _assert_consolidation_tables_ready(conn)
        return _build_effective_group_members(conn, group_id=group_id, q_start=q_start, q_end=q_end)


def resolve_consolidation_group(conn, consolidation_group_id: int) -> Dict[str, object]:
    _assert_consolidation_tables_ready(conn)
    result = _build_effective_group_members(
        conn,
        group_id=consolidation_group_id,
        q_start=datetime.now().date(),
        q_end=datetime.now().date(),
    )
    if not result["member_book_ids"]:
        raise ConsolidationError("consolidation_group_empty")
    return {
        "consolidation_group_id": result["group_id"],
        "consolidation_group_code": result["group_code"],
        "consolidation_group_name": result["group_name"],
        "member_book_ids": result["member_book_ids"],
    }


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationError(f"{field}_invalid")
    return parsed


def _parse_period(value: object) -> str:
    raw = str(value or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ConsolidationError("period_invalid")
    yy = raw[:4]
    mm = raw[5:]
    if not yy.isdigit() or not mm.isdigit():
        raise ConsolidationError("period_invalid")
    m = int(mm)
    if m < 1 or m > 12:
        raise ConsolidationError("period_invalid")
    return f"{int(yy):04d}-{m:02d}"


def _as_of_to_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationError("as_of_required")
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationError("as_of_invalid") from err
    return parsed.strftime("%Y-%m")


def _as_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")


def _load_reports(conn, group_id: int, period: str) -> Dict[str, Dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT report_code, report_json, batch_id
            FROM consolidation_report_snapshots
            WHERE group_id=:group_id AND period=:period
            ORDER BY report_code ASC
            """
        ),
        {"group_id": group_id, "period": period},
    ).fetchall()
    reports: Dict[str, Dict[str, object]] = {}
    for row in rows:
        report_code = str(row.report_code or "").strip()
        if not report_code:
            continue
        try:
            payload = json.loads(str(row.report_json or "{}"))
        except Exception:
            payload = {}
        payload["_batch_id"] = str(row.batch_id or "")
        reports[report_code] = payload
    return reports


def _ensure_consolidation_enhance_tables(conn) -> None:
    try:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS consolidation_disclosure_checks (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    group_id BIGINT NOT NULL,
                    period VARCHAR(7) NOT NULL,
                    batch_id VARCHAR(64) NOT NULL,
                    check_code VARCHAR(64) NOT NULL,
                    check_result VARCHAR(16) NOT NULL,
                    check_value DECIMAL(18,2) NULL,
                    threshold_value DECIMAL(18,2) NULL,
                    note VARCHAR(255) NULL,
                    operator_id BIGINT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_conso_disclosure_check (group_id, period, batch_id, check_code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS consolidation_audit_indexes (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    group_id BIGINT NOT NULL,
                    period VARCHAR(7) NOT NULL,
                    batch_id VARCHAR(64) NOT NULL,
                    report_code VARCHAR(64) NOT NULL,
                    item_code VARCHAR(128) NOT NULL,
                    item_label VARCHAR(255) NULL,
                    amount DECIMAL(18,2) NOT NULL DEFAULT 0.00,
                    evidence_ref VARCHAR(255) NOT NULL,
                    source_batch_id VARCHAR(64) NULL,
                    operator_id BIGINT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    KEY ix_conso_audit_idx_gp_batch (group_id, period, batch_id)
                )
                """
            )
        )
    except Exception:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS consolidation_disclosure_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    check_code TEXT NOT NULL,
                    check_result TEXT NOT NULL,
                    check_value NUMERIC NULL,
                    threshold_value NUMERIC NULL,
                    note TEXT NULL,
                    operator_id INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (group_id, period, batch_id, check_code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS consolidation_audit_indexes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    report_code TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    item_label TEXT NULL,
                    amount NUMERIC NOT NULL DEFAULT 0,
                    evidence_ref TEXT NOT NULL,
                    source_batch_id TEXT NULL,
                    operator_id INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def generate_disclosure_notes(payload: Dict[str, object], operator_id: object = 0) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period_raw = str(payload.get("period") or "").strip()
    period = _parse_period(period_raw) if period_raw else _as_of_to_period(payload.get("as_of"))
    operator = _parse_positive_int(operator_id or 1, "operator_id")
    batch_id = f"DISCCHK-{group_id}-{period.replace('-', '')}"

    provider = get_connection_provider()
    with provider.begin() as conn:
        _ensure_consolidation_enhance_tables(conn)
        reports = _load_reports(conn, group_id, period)
        required = {"BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW", "EQUITY_CHANGE"}
        report_complete = 1 if required.issubset(set(reports.keys())) else 0

        adj_rows = conn.execute(
            text(
                """
                SELECT lines_json
                FROM consolidation_adjustments
                WHERE group_id=:group_id AND period=:period
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        debit_total = Decimal("0")
        credit_total = Decimal("0")
        for row in adj_rows:
            try:
                lines = json.loads(str(row.lines_json or "[]"))
            except Exception:
                lines = []
            if not isinstance(lines, list):
                continue
            for line in lines:
                if not isinstance(line, dict):
                    continue
                debit_total += _as_decimal(line.get("debit"))
                credit_total += _as_decimal(line.get("credit"))

        diff = abs(debit_total - credit_total)
        balanced = 1 if diff <= Decimal("0.01") else 0

        flow_row = conn.execute(
            text(
                """
                SELECT id, approval_status, check_result
                FROM consolidation_approval_flows
                WHERE group_id=:group_id AND period=:period
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchone()
        approved = 1 if flow_row and str(flow_row.check_result or "") == "passed" else 0

        checks = [
            {
                "check_code": "REPORT_SNAPSHOT_COMPLETE",
                "check_result": "pass" if report_complete else "fail",
                "check_value": Decimal(str(report_complete)),
                "threshold_value": Decimal("1"),
                "note": "四大报表快照齐备",
            },
            {
                "check_code": "ADJUSTMENT_DEBIT_CREDIT_BALANCED",
                "check_result": "pass" if balanced else "fail",
                "check_value": diff,
                "threshold_value": Decimal("0.01"),
                "note": "抵销分录借贷平衡",
            },
            {
                "check_code": "FINAL_APPROVAL_PASSED",
                "check_result": "pass" if approved else "fail",
                "check_value": Decimal(str(approved)),
                "threshold_value": Decimal("1"),
                "note": "最终校验审批通过",
            },
        ]

        conn.execute(
            text(
                """
                DELETE FROM consolidation_disclosure_checks
                WHERE group_id=:group_id AND period=:period AND batch_id=:batch_id
                """
            ),
            {"group_id": group_id, "period": period, "batch_id": batch_id},
        )
        for item in checks:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_disclosure_checks (
                        group_id, period, batch_id, check_code, check_result,
                        check_value, threshold_value, note, operator_id
                    ) VALUES (
                        :group_id, :period, :batch_id, :check_code, :check_result,
                        :check_value, :threshold_value, :note, :operator_id
                    )
                    """
                ),
                {
                    "group_id": group_id,
                    "period": period,
                    "batch_id": batch_id,
                    "check_code": item["check_code"],
                    "check_result": item["check_result"],
                    "check_value": str(item["check_value"]),
                    "threshold_value": str(item["threshold_value"]),
                    "note": item["note"],
                    "operator_id": operator,
                },
            )

    return {
        "group_id": group_id,
        "period": period,
        "batch_id": batch_id,
        "check_count": len(checks),
        "failed_count": len([c for c in checks if c["check_result"] != "pass"]),
        "checks": [
            {
                "check_code": c["check_code"],
                "check_result": c["check_result"],
                "check_value": float(c["check_value"]),
                "threshold_value": float(c["threshold_value"]),
                "note": c["note"],
            }
            for c in checks
        ],
    }


def create_audit_index(payload: Dict[str, object], operator_id: object = 0) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period_raw = str(payload.get("period") or "").strip()
    period = _parse_period(period_raw) if period_raw else _as_of_to_period(payload.get("as_of"))
    operator = _parse_positive_int(operator_id or 1, "operator_id")
    batch_id = f"AUDIDX-{group_id}-{period.replace('-', '')}"

    provider = get_connection_provider()
    with provider.begin() as conn:
        _ensure_consolidation_enhance_tables(conn)
        reports = _load_reports(conn, group_id, period)
        if not reports:
            raise ConsolidationError("report_snapshots_not_ready")

        conn.execute(
            text(
                """
                DELETE FROM consolidation_audit_indexes
                WHERE group_id=:group_id AND period=:period AND batch_id=:batch_id
                """
            ),
            {"group_id": group_id, "period": period, "batch_id": batch_id},
        )

        indexed = 0
        report_count = 0
        for report_code, report in reports.items():
            report_count += 1
            source_batch_id = str(report.get("_batch_id") or "")
            items = report.get("items") or []
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_code = str(item.get("item_code") or "").strip() or f"ROW{indexed+1}"
                item_label = str(item.get("label") or "").strip() or None
                amount = _as_decimal(item.get("amount"))
                evidence_ref = f"RPT-{group_id}-{period.replace('-', '')}-{report_code}-{item_code}"
                conn.execute(
                    text(
                        """
                        INSERT INTO consolidation_audit_indexes (
                            group_id, period, batch_id, report_code, item_code, item_label,
                            amount, evidence_ref, source_batch_id, operator_id
                        ) VALUES (
                            :group_id, :period, :batch_id, :report_code, :item_code, :item_label,
                            :amount, :evidence_ref, :source_batch_id, :operator_id
                        )
                        """
                    ),
                    {
                        "group_id": group_id,
                        "period": period,
                        "batch_id": batch_id,
                        "report_code": report_code,
                        "item_code": item_code,
                        "item_label": item_label,
                        "amount": str(amount),
                        "evidence_ref": evidence_ref,
                        "source_batch_id": source_batch_id or None,
                        "operator_id": operator,
                    },
                )
                indexed += 1

    return {
        "group_id": group_id,
        "period": period,
        "batch_id": batch_id,
        "report_count": report_count,
        "indexed_count": indexed,
    }


def trace_consolidation_batch(payload: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period_raw = str(payload.get("period") or "").strip()
    period = _parse_period(period_raw) if period_raw else _as_of_to_period(payload.get("as_of"))
    requested_batch = str(payload.get("batch_id") or "").strip()

    provider = get_connection_provider()
    with provider.connect() as conn:
        _ensure_consolidation_enhance_tables(conn)
        trace_items: List[Dict[str, object]] = []

        def _push(stage: str, batch_id: str, ref: str, status: str, created_at: object):
            if requested_batch and requested_batch != batch_id:
                return
            trace_items.append(
                {
                    "stage": stage,
                    "batch_id": str(batch_id or ""),
                    "ref": str(ref or ""),
                    "status": str(status or ""),
                    "created_at": str(created_at or ""),
                }
            )

        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, status, created_at
                FROM consolidation_adjustments
                WHERE group_id=:group_id AND period=:period AND COALESCE(batch_id,'')<>''
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        for row in rows:
            _push("adjustment", str(row.batch_id or ""), f"adj:{int(row.id)}", str(row.status or ""), row.created_at)

        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, report_code, status, created_at
                FROM consolidation_report_snapshots
                WHERE group_id=:group_id AND period=:period
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        for row in rows:
            _push("report_snapshot", str(row.batch_id or ""), str(row.report_code or ""), str(row.status or ""), row.created_at)

        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, approval_status, created_at
                FROM consolidation_approval_flows
                WHERE group_id=:group_id AND period=:period
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        for row in rows:
            _push("approval_flow", str(row.batch_id or ""), f"approval:{int(row.id)}", str(row.approval_status or ""), row.created_at)

        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, status, created_at
                FROM consolidation_audit_packages
                WHERE group_id=:group_id AND period=:period
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        for row in rows:
            _push("audit_package", str(row.batch_id or ""), f"package:{int(row.id)}", str(row.status or ""), row.created_at)

        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, check_code, check_result, created_at
                FROM consolidation_disclosure_checks
                WHERE group_id=:group_id AND period=:period
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        for row in rows:
            _push("disclosure_check", str(row.batch_id or ""), str(row.check_code or ""), str(row.check_result or ""), row.created_at)

        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, report_code, created_at
                FROM consolidation_audit_indexes
                WHERE group_id=:group_id AND period=:period
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        for row in rows:
            _push("audit_index", str(row.batch_id or ""), str(row.report_code or ""), "indexed", row.created_at)

    trace_items.sort(key=lambda x: (x.get("created_at") or "", x.get("stage") or "", x.get("ref") or ""))
    return {
        "group_id": group_id,
        "period": period,
        "requested_batch_id": requested_batch,
        "trace_count": len(trace_items),
        "items": trace_items,
    }
