from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import bindparam, text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import get_adjustment_totals_by_subject
from app.services.consolidation_authorization_service import (
    ConsolidationAuthorizationError,
    assert_virtual_authorized,
)
from app.services.consolidation_parameters_service import get_trial_balance_scope_config
from app.services.subject_category_service import resolve_subject_category


class TrialBalanceError(RuntimeError):
    pass


SCOPE_SINGLE = "single"
SCOPE_LEGAL_NATURAL = "legal_natural"
SCOPE_VIRTUAL = "virtual_consolidation"
SCOPE_LEGACY_GROUP = "consolidation_group"


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise TrialBalanceError("invalid_date") from err


def _sum_children(nodes_by_code: Dict[str, Dict[str, object]], order: List[str]):
    # Post-order aggregation by level descending
    for code in sorted(order, key=lambda c: nodes_by_code[c]["level"], reverse=True):
        node = nodes_by_code[code]
        parent_code = node.get("parent_code")
        if parent_code and parent_code in nodes_by_code:
            parent = nodes_by_code[parent_code]
            parent["period_debit"] += node["period_debit"]
            parent["period_credit"] += node["period_credit"]
            parent["opening_balance"] += node["opening_balance"]
            parent["ending_balance"] += node["ending_balance"]


def _find_parent_by_prefix(code: str, existing_codes: set) -> str:
    c = (code or "").strip()
    if len(c) <= 4:
        return ""

    # Dot-separated hierarchy, e.g. 1001.01.01 -> 1001.01 -> 1001
    if "." in c:
        parts = [p for p in c.split(".") if p]
        while len(parts) > 1:
            parts = parts[:-1]
            parent = ".".join(parts)
            if parent in existing_codes:
                return parent

    for cut in range(len(c) - 2, 3, -2):
        p = c[:cut]
        if p in existing_codes:
            return p
    return ""


def _table_columns(conn, table_name: str) -> Set[str]:
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
    out: Set[str] = set()
    for r in rows:
        value = None
        try:
            value = r[0]
        except Exception:
            value = getattr(r, "column_name", None)
        txt = str(value or "").strip().lower()
        if txt:
            out.add(txt)
    return out


def _book_info_map(conn, only_enabled: bool = True) -> Dict[int, Dict[str, object]]:
    where = "WHERE b.is_enabled=1" if only_enabled else ""
    rows = conn.execute(
        text(
            f"""
            SELECT b.id, b.name, b.is_enabled,
                   COALESCE(rc.rule_value, CONCAT('BOOK-', LPAD(b.id, 4, '0'))) AS book_code
            FROM books b
            LEFT JOIN sys_rules rc ON rc.rule_key=CONCAT('book_meta:code:', b.id)
            {where}
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
            "is_enabled": int(r.is_enabled or 0),
        }
    return out


def _legal_entities_by_book(conn) -> Dict[int, List[Dict[str, object]]]:
    rows = conn.execute(
        text(
            """
            SELECT id, entity_code, entity_name, entity_kind, book_id
            FROM legal_entities
            WHERE status='active' AND is_enabled=1
            ORDER BY id ASC
            """
        )
    ).fetchall()
    out: Dict[int, List[Dict[str, object]]] = {}
    for r in rows:
        if r.book_id is None:
            continue
        bid = int(r.book_id)
        out.setdefault(bid, []).append(
            {
                "entity_id": int(r.id),
                "entity_code": str(r.entity_code or ""),
                "entity_name": str(r.entity_name or ""),
                "entity_kind": str(r.entity_kind or "").strip().lower(),
                "book_id": bid,
            }
        )
    return out


def _active_natural_rows(conn) -> List[object]:
    return conn.execute(
        text(
            """
            SELECT g.id AS group_id,
                   m.id AS member_id,
                   m.member_type,
                   m.member_entity_id,
                   m.member_book_id
            FROM consolidation_group_members m
            JOIN consolidation_groups g ON g.id=m.group_id
            WHERE g.group_type='natural_legal'
              AND g.status='active'
              AND g.is_enabled=1
              AND m.status='active'
              AND m.is_enabled=1
            ORDER BY g.id ASC, m.id ASC
            """
        )
    ).fetchall()


def _active_virtual_entity(
    conn, virtual_entity_id: int
) -> Optional[Dict[str, object]]:
    row = conn.execute(
        text(
            """
            SELECT v.id, v.virtual_code, v.virtual_name, v.book_id,
                   COALESCE(r.rule_value, '') AS group_id
            FROM virtual_entities v
            LEFT JOIN sys_rules r ON r.rule_key=CONCAT('virtual_group:', v.id)
            WHERE v.id=:virtual_id
              AND v.status='active'
              AND v.is_enabled=1
            LIMIT 1
            """
        ),
        {"virtual_id": virtual_entity_id},
    ).fetchone()
    if not row:
        return None
    gid = int(row.group_id) if str(row.group_id or "").strip().isdigit() else None
    return {
        "virtual_id": int(row.id),
        "virtual_code": str(row.virtual_code or ""),
        "virtual_name": str(row.virtual_name or f"虚拟主体{int(row.id)}"),
        "book_id": int(row.book_id) if row.book_id is not None else None,
        "group_id": gid,
    }


def _virtual_entity_by_book(
    conn, book_id: int
) -> Optional[Dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT v.id
            FROM virtual_entities v
            WHERE v.book_id=:book_id
              AND v.status='active'
              AND v.is_enabled=1
            ORDER BY v.id ASC
            """
        ),
        {"book_id": book_id},
    ).fetchall()
    if not rows:
        return None
    return _active_virtual_entity(conn, int(rows[0].id))


def _build_scope_tree_node(
    node_type: str,
    title: str,
    book_id: Optional[int],
    entity_id: Optional[int],
    children: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    return {
        "node_type": node_type,
        "title": title,
        "book_id": int(book_id) if book_id else None,
        "entity_id": int(entity_id) if entity_id else None,
        "children": children or [],
    }


def _parse_positive_int(value: object, field: str) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except Exception as err:
        raise TrialBalanceError(f"{field} must be integer") from err
    if parsed <= 0:
        raise TrialBalanceError(f"{field} must be integer")
    return parsed


def _resolve_natural_children(
    legal_entity_id: int,
    natural_rows: List[object],
    legal_entities_by_book: Dict[int, List[Dict[str, object]]],
    books: Dict[int, Dict[str, object]],
) -> Tuple[List[Dict[str, object]], List[str]]:
    warnings: List[str] = []
    group_ids = sorted(
        {
            int(r.group_id)
            for r in natural_rows
            if str(r.member_type or "").upper() == "LEGAL"
            and r.member_entity_id is not None
            and int(r.member_entity_id) == int(legal_entity_id)
        }
    )
    if len(group_ids) > 1:
        warnings.append("天然合并关系异常：一个法人存在多个天然组，已自动合并其成员范围")

    entity_map: Dict[int, Dict[str, object]] = {}
    for entities in legal_entities_by_book.values():
        for entity in entities:
            entity_map[int(entity["entity_id"])] = entity

    children_by_book: Dict[int, Dict[str, object]] = {}
    invalid_member_count = 0
    for r in natural_rows:
        if int(r.group_id) not in group_ids:
            continue
        if str(r.member_type or "").upper() != "NON_LEGAL":
            continue
        eid = int(r.member_entity_id) if r.member_entity_id is not None else 0
        child_entity = entity_map.get(eid)
        if not child_entity or child_entity.get("entity_kind") != "non_legal":
            invalid_member_count += 1
            continue
        child_book_id = int(child_entity.get("book_id") or 0)
        if not child_book_id or child_book_id not in books:
            invalid_member_count += 1
            continue
        if child_book_id not in children_by_book:
            book_name = str(books[child_book_id]["book_name"])
            children_by_book[child_book_id] = {
                "book_id": child_book_id,
                "book_name": book_name,
                "entity_id": int(child_entity["entity_id"]),
                "title": f"{book_name}（非法人）",
            }
    if invalid_member_count > 0:
        warnings.append(f"天然合并关系存在脏数据，已忽略{invalid_member_count}条异常成员")

    children = [children_by_book[k] for k in sorted(children_by_book.keys())]
    return children, warnings


def _build_amount_node(
    node_id: str,
    node_type: str,
    title: str,
    view_kind: str,
    scope_book_ids: List[int],
    children: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    return {
        "node_id": node_id,
        "node_type": node_type,  # virtual_summary | legal_summary | book_single
        "title": title,
        "view_kind": view_kind,  # summary | single
        "scope_book_ids": sorted({int(x) for x in (scope_book_ids or []) if int(x) > 0}),
        "children": children or [],
    }


def _flatten_amount_tree(nodes: List[Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    out: Dict[str, Dict[str, object]] = {}

    def walk(node: Dict[str, object]):
        node_id = str(node.get("node_id") or "").strip()
        if node_id:
            out[node_id] = node
        for child in node.get("children") or []:
            walk(child)

    for n in nodes or []:
        walk(n)
    return out


def _resolve_scope(
    conn,
    *,
    book_id: Optional[int],
    virtual_entity_id: Optional[int],
    consolidation_group_id: Optional[int],
    start_date: date,
    end_date: date,
) -> Dict[str, object]:
    try:
        books = _book_info_map(conn, only_enabled=True)
        legal_entities_by_book = _legal_entities_by_book(conn)
        natural_rows = _active_natural_rows(conn)
    except Exception as err:
        raise TrialBalanceError("scope_relation_source_not_ready") from err
    warnings: List[str] = []

    if consolidation_group_id is not None:
        gcols = _table_columns(conn, "consolidation_groups")
        mcols = _table_columns(conn, "consolidation_group_members")
        member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
        effective_from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
        effective_to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
        if not gcols or not mcols or not member_book_col:
            raise TrialBalanceError("consolidation_member_model_not_ready")

        group_where_parts = ["id=:group_id"]
        if "status" in gcols:
            group_where_parts.append("status='active'")
        if "is_enabled" in gcols:
            group_where_parts.append("is_enabled=1")
        group_row = conn.execute(
            text(
                f"""
                SELECT id, group_code, group_name
                FROM consolidation_groups
                WHERE {' AND '.join(group_where_parts)}
                LIMIT 1
                """
            ),
            {"group_id": int(consolidation_group_id)},
        ).fetchone()
        if not group_row:
            raise TrialBalanceError("consolidation_group_not_found")

        member_where_parts = ["group_id=:group_id", f"{member_book_col} IS NOT NULL"]
        if "status" in mcols:
            member_where_parts.append("status='active'")
        if "is_enabled" in mcols:
            member_where_parts.append("is_enabled=1")
        if effective_from_col:
            member_where_parts.append(f"({effective_from_col} IS NULL OR {effective_from_col}<=:end_date)")
        if effective_to_col:
            member_where_parts.append(f"({effective_to_col} IS NULL OR {effective_to_col}>=:start_date)")
        member_rows = conn.execute(
            text(
                f"""
                SELECT {member_book_col} AS member_book_id
                FROM consolidation_group_members
                WHERE {' AND '.join(member_where_parts)}
                ORDER BY id ASC
                """
            ),
            {"group_id": int(consolidation_group_id), "start_date": start_date, "end_date": end_date},
        ).fetchall()
        scope_book_ids = sorted(
            {
                int(r.member_book_id)
                for r in member_rows
                if r.member_book_id is not None and int(r.member_book_id) in books
            }
        )
        effective_member_count = len(scope_book_ids)
        tree_children = []
        for bid in scope_book_ids:
            b = books.get(bid) or {"book_name": f"账套{bid}"}
            tree_children.append(
                _build_scope_tree_node("book", f"{b['book_name']}（账套）", bid, None, [])
            )
        scope_tree = [
            _build_scope_tree_node(
                "scope",
                f"合并组 {str(group_row.group_name or consolidation_group_id)}",
                None,
                None,
                tree_children,
            )
        ]
        return {
            "scope_type": SCOPE_LEGACY_GROUP,
            "scope_type_label": "合并组视角（兼容）",
            "scope_book_ids": scope_book_ids,
            "scope_tree": scope_tree,
            "current_subject_name": str(group_row.group_name or f"合并组{consolidation_group_id}"),
            "scope_notice": f"当前为合并组汇总口径（仅汇总未抵销）；有效成员 {effective_member_count}",
            "effective_member_count": effective_member_count,
            "is_eliminated": False,
            "query_mode": "consolidation_group",
            "query_mode_label": "合并组模式（成员汇总）",
            "consolidation_group_id": int(group_row.id),
            "consolidation_group_name": str(group_row.group_name or ""),
            "consolidation_group_code": str(group_row.group_code or ""),
            "virtual_entity_id": None,
            "virtual_entity_name": "",
            "scope_warnings": [],
            "amount_scope_tree": [
                _build_amount_node(
                    "legacy_group:summary",
                    "scope_summary",
                    "合并组汇总表",
                    "summary",
                    scope_book_ids,
                    [],
                )
            ],
            "default_amount_node_id": "legacy_group:summary",
        }

    resolved_virtual: Optional[Dict[str, object]] = None
    if virtual_entity_id is not None:
        resolved_virtual = _active_virtual_entity(conn, virtual_entity_id)
        if not resolved_virtual:
            raise TrialBalanceError("virtual_entity_not_found_or_inactive")
    elif book_id is not None:
        resolved_virtual = _virtual_entity_by_book(conn, book_id)

    if resolved_virtual:
        group_id = resolved_virtual.get("group_id")
        if not group_id:
            warnings.append("虚拟主体未绑定合并成员组，当前暂无法人成员")
            scope_notice = "当前为虚拟合并主体视角；当前为汇总口径，未做抵销处理；虚拟主体暂无法人成员"
            return {
                "scope_type": SCOPE_VIRTUAL,
                "scope_type_label": "虚拟合并主体视角",
                "scope_book_ids": [],
                "scope_tree": [
                    _build_scope_tree_node(
                        "virtual_summary",
                        str(resolved_virtual["virtual_name"]),
                        resolved_virtual.get("book_id"),
                        resolved_virtual.get("virtual_id"),
                        [],
                    )
                ],
                "current_subject_name": str(resolved_virtual["virtual_name"]),
                "scope_notice": scope_notice,
                "is_eliminated": False,
                "query_mode": "virtual_consolidation",
                "query_mode_label": "虚拟合并主体视角",
                "consolidation_group_id": None,
                "consolidation_group_name": "",
                "consolidation_group_code": "",
                "virtual_entity_id": int(resolved_virtual["virtual_id"]),
                "virtual_entity_name": str(resolved_virtual["virtual_name"]),
                "scope_warnings": warnings,
                "amount_scope_tree": [
                    _build_amount_node(
                        f"virtual:{int(resolved_virtual['virtual_id'])}:summary",
                        "virtual_summary",
                        f"{str(resolved_virtual['virtual_name'])}汇总表",
                        "summary",
                        [],
                        [],
                    )
                ],
                "default_amount_node_id": f"virtual:{int(resolved_virtual['virtual_id'])}:summary",
            }

        mcols = _table_columns(conn, "consolidation_group_members")
        member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
        if not member_book_col:
            raise TrialBalanceError("consolidation_member_model_not_ready")
        legal_rows = conn.execute(
            text(
                f"""
                SELECT id, member_entity_id, {member_book_col} AS member_book_id
                FROM consolidation_group_members
                WHERE group_id=:group_id
                  AND member_type='LEGAL'
                  AND status='active'
                  AND is_enabled=1
                ORDER BY id ASC
                """
            ),
            {"group_id": int(group_id)},
        ).fetchall()
        if not legal_rows:
            scope_notice = "当前为虚拟合并主体视角；当前为汇总口径，未做抵销处理；虚拟主体暂无法人成员"
            return {
                "scope_type": SCOPE_VIRTUAL,
                "scope_type_label": "虚拟合并主体视角",
                "scope_book_ids": [],
                "scope_tree": [
                    _build_scope_tree_node(
                        "virtual",
                        str(resolved_virtual["virtual_name"]),
                        resolved_virtual.get("book_id"),
                        resolved_virtual.get("virtual_id"),
                        [],
                    )
                ],
                "current_subject_name": str(resolved_virtual["virtual_name"]),
                "scope_notice": scope_notice,
                "is_eliminated": False,
                "query_mode": "virtual_consolidation",
                "query_mode_label": "虚拟合并主体视角",
                "consolidation_group_id": None,
                "consolidation_group_name": "",
                "consolidation_group_code": "",
                "virtual_entity_id": int(resolved_virtual["virtual_id"]),
                "virtual_entity_name": str(resolved_virtual["virtual_name"]),
                "scope_warnings": warnings,
                "amount_scope_tree": [
                    _build_amount_node(
                        f"virtual:{int(resolved_virtual['virtual_id'])}:summary",
                        "virtual",
                        f"{str(resolved_virtual['virtual_name'])}汇总表",
                        "summary",
                        [],
                        [],
                    )
                ],
                "default_amount_node_id": f"virtual:{int(resolved_virtual['virtual_id'])}:summary",
            }

        scope_book_ids: Set[int] = set()
        legal_nodes: List[Dict[str, object]] = []
        amount_children_nodes: List[Dict[str, object]] = []
        legal_entity_index: Dict[int, Dict[str, object]] = {}
        for entities in legal_entities_by_book.values():
            for entity in entities:
                if entity.get("entity_kind") == "legal":
                    legal_entity_index[int(entity["entity_id"])] = entity

        invalid_member_count = 0
        for row in legal_rows:
            legal_entity_id = int(row.member_entity_id) if row.member_entity_id is not None else 0
            legal_entity = legal_entity_index.get(legal_entity_id)
            legal_book_id = int(row.member_book_id) if row.member_book_id is not None else int((legal_entity or {}).get("book_id") or 0)
            if not legal_entity or not legal_book_id or legal_book_id not in books:
                invalid_member_count += 1
                continue
            scope_book_ids.add(legal_book_id)
            legal_book_name = str(books[legal_book_id]["book_name"])
            non_legal_children, child_warnings = _resolve_natural_children(
                legal_entity_id, natural_rows, legal_entities_by_book, books
            )
            warnings.extend(child_warnings)
            child_nodes = []
            for child in non_legal_children:
                scope_book_ids.add(int(child["book_id"]))
                child_nodes.append(
                    _build_scope_tree_node(
                        "non_legal",
                        str(child["title"]),
                        int(child["book_id"]),
                        int(child["entity_id"]),
                        [],
                    )
                )
            legal_nodes.append(
                _build_scope_tree_node(
                    "legal",
                    f"{legal_book_name}（法人）",
                    legal_book_id,
                    legal_entity_id,
                    child_nodes,
                )
            )
            legal_summary_scope = [legal_book_id] + [int(c["book_id"]) for c in non_legal_children]
            legal_summary_scope = sorted(set(legal_summary_scope))
            if non_legal_children:
                legal_amount_children = [
                    _build_amount_node(
                        f"virtual:{int(resolved_virtual['virtual_id'])}:legal:{legal_book_id}:single",
                        "book_single",
                        f"{legal_book_name}单账表",
                        "single",
                        [legal_book_id],
                        [],
                    )
                ]
                for child in non_legal_children:
                    legal_amount_children.append(
                        _build_amount_node(
                            f"virtual:{int(resolved_virtual['virtual_id'])}:non_legal:{int(child['book_id'])}:single",
                            "book_single",
                            f"{str(child['book_name'])}单账表",
                            "single",
                            [int(child["book_id"])],
                            [],
                        )
                    )
                amount_children_nodes.append(
                    _build_amount_node(
                        f"virtual:{int(resolved_virtual['virtual_id'])}:legal:{legal_book_id}:summary",
                        "legal_summary",
                        f"{legal_book_name}汇总表",
                        "summary",
                        legal_summary_scope,
                        legal_amount_children,
                    )
                )
            else:
                amount_children_nodes.append(
                    _build_amount_node(
                        f"virtual:{int(resolved_virtual['virtual_id'])}:legal:{legal_book_id}:single",
                        "book_single",
                        f"{legal_book_name}单账表",
                        "single",
                        [legal_book_id],
                        [],
                    )
                )
        if invalid_member_count > 0:
            warnings.append(f"虚拟主体成员存在脏数据，已忽略{invalid_member_count}条异常法人成员")

        scope_tree = [
            _build_scope_tree_node(
                "virtual_summary",
                str(resolved_virtual["virtual_name"]),
                resolved_virtual.get("book_id"),
                resolved_virtual.get("virtual_id"),
                legal_nodes,
            )
        ]
        root_amount_node_id = f"virtual:{int(resolved_virtual['virtual_id'])}:summary"
        amount_scope_tree = [
            _build_amount_node(
                root_amount_node_id,
                "virtual_summary",
                f"{str(resolved_virtual['virtual_name'])}汇总表",
                "summary",
                sorted(scope_book_ids),
                amount_children_nodes,
            )
        ]
        scope_notice_parts = ["当前为虚拟合并主体视角", "当前为汇总口径，未做抵销处理"]
        scope_notice_parts.extend(warnings)
        return {
            "scope_type": SCOPE_VIRTUAL,
            "scope_type_label": "虚拟合并主体视角",
            "scope_book_ids": sorted(scope_book_ids),
            "scope_tree": scope_tree,
            "current_subject_name": str(resolved_virtual["virtual_name"]),
            "scope_notice": "；".join(scope_notice_parts),
            "is_eliminated": False,
            "query_mode": "virtual_consolidation",
            "query_mode_label": "虚拟合并主体视角",
            "consolidation_group_id": None,
            "consolidation_group_name": "",
            "consolidation_group_code": "",
            "virtual_entity_id": int(resolved_virtual["virtual_id"]),
            "virtual_entity_name": str(resolved_virtual["virtual_name"]),
            "scope_warnings": warnings,
            "amount_scope_tree": amount_scope_tree,
            "default_amount_node_id": root_amount_node_id,
        }

    if book_id is None:
        raise TrialBalanceError("book_id required")
    if book_id not in books:
        raise TrialBalanceError("book_not_found_or_disabled")

    entities = legal_entities_by_book.get(book_id) or []
    legal_entity = next((x for x in entities if x.get("entity_kind") == "legal"), None)
    non_legal_entity = next((x for x in entities if x.get("entity_kind") == "non_legal"), None)
    if legal_entity and non_legal_entity:
        warnings.append("当前账套同时存在法人与非法人标识，已按法人视角解析")

    if legal_entity:
        non_legal_children, child_warnings = _resolve_natural_children(
            int(legal_entity["entity_id"]), natural_rows, legal_entities_by_book, books
        )
        warnings.extend(child_warnings)
        scope_book_ids = [book_id] + [int(c["book_id"]) for c in non_legal_children]
        scope_book_ids = sorted(set(scope_book_ids))
        legal_title = f"{books[book_id]['book_name']}（法人）"
        child_nodes = [
            _build_scope_tree_node(
                "non_legal",
                str(child["title"]),
                int(child["book_id"]),
                int(child["entity_id"]),
                [],
            )
            for child in non_legal_children
        ]
        scope_tree = [
            _build_scope_tree_node("legal", legal_title, book_id, int(legal_entity["entity_id"]), child_nodes)
        ]
        scope_notice_parts = ["当前为天然合并视角（法人+所属非法人）"]
        if not non_legal_children:
            scope_notice_parts.append("该法人当前无所属非法人，结果等同单账套")
        scope_notice_parts.extend(warnings)
        return {
            "scope_type": SCOPE_LEGAL_NATURAL,
            "scope_type_label": "天然合并视角（法人+非法人）",
            "scope_book_ids": scope_book_ids,
            "scope_tree": scope_tree,
            "current_subject_name": str(books[book_id]["book_name"]),
            "scope_notice": "；".join(scope_notice_parts),
            "is_eliminated": None,
            "query_mode": "legal_natural",
            "query_mode_label": "天然合并视角（法人+非法人）",
            "consolidation_group_id": None,
            "consolidation_group_name": "",
            "consolidation_group_code": "",
            "virtual_entity_id": None,
            "virtual_entity_name": "",
            "scope_warnings": warnings,
            "amount_scope_tree": [
                _build_amount_node(
                    (f"legal:{book_id}:summary" if non_legal_children else f"legal:{book_id}:single"),
                    (
                        "legal_summary"
                        if non_legal_children
                        else "book_single"
                    ),
                    (
                        f"{str(books[book_id]['book_name'])}汇总表"
                        if non_legal_children
                        else f"{str(books[book_id]['book_name'])}单账表"
                    ),
                    ("summary" if non_legal_children else "single"),
                    ([book_id] + [int(c["book_id"]) for c in non_legal_children]),
                    (
                        [
                            _build_amount_node(
                                f"legal:{book_id}:book:{book_id}:single",
                                "book_single",
                                f"{str(books[book_id]['book_name'])}单账表",
                                "single",
                                [book_id],
                                [],
                            )
                        ]
                        + [
                            _build_amount_node(
                                f"legal:{book_id}:book:{int(c['book_id'])}:single",
                                "book_single",
                                f"{str(c['book_name'])}单账表",
                                "single",
                                [int(c["book_id"])],
                                [],
                            )
                            for c in non_legal_children
                        ]
                        if non_legal_children
                        else []
                    ),
                )
            ],
            "default_amount_node_id": (
                f"legal:{book_id}:summary" if non_legal_children else f"legal:{book_id}:single"
            ),
        }

    scope_tree = [
        _build_scope_tree_node(
            "book",
            f"{books[book_id]['book_name']}（单账套）",
            book_id,
            int(non_legal_entity["entity_id"]) if non_legal_entity else None,
            [],
        )
    ]
    scope_notice = "当前为单账套视角"
    if non_legal_entity:
        scope_notice += "（非法人账套默认不自动上卷至法人）"
    return {
        "scope_type": SCOPE_SINGLE,
        "scope_type_label": "单账套视角",
        "scope_book_ids": [book_id],
        "scope_tree": scope_tree,
        "current_subject_name": str(books[book_id]["book_name"]),
        "scope_notice": scope_notice,
        "is_eliminated": None,
        "query_mode": "single_book",
        "query_mode_label": "单账套模式",
        "consolidation_group_id": None,
        "consolidation_group_name": "",
        "consolidation_group_code": "",
        "virtual_entity_id": None,
        "virtual_entity_name": "",
        "scope_warnings": warnings,
        "amount_scope_tree": [
            _build_amount_node(
                f"book:{book_id}:single",
                "book_single",
                f"{str(books[book_id]['book_name'])}单账表",
                "single",
                [book_id],
                [],
            )
        ],
        "default_amount_node_id": f"book:{book_id}:single",
    }


def get_trial_balance(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    consolidation_group_id_raw = (params.get("consolidation_group_id") or "").strip()
    virtual_entity_id_raw = (params.get("virtual_entity_id") or "").strip()
    amount_node_id = str(params.get("amount_node_id") or "").strip()
    scope_raw = str(params.get("scope") or "").strip().lower()
    scope_mode = scope_raw or "raw"
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()

    if not start_raw or not end_raw:
        raise TrialBalanceError("start_date/end_date required")
    if not book_id_raw and not consolidation_group_id_raw and not virtual_entity_id_raw:
        raise TrialBalanceError("book_id or consolidation_group_id or virtual_entity_id required")
    if scope_mode not in ("raw", "after_elim"):
        raise TrialBalanceError("scope_invalid")

    book_id = _parse_positive_int(book_id_raw, "book_id")
    consolidation_group_id = _parse_positive_int(consolidation_group_id_raw, "consolidation_group_id")
    virtual_entity_id = _parse_positive_int(virtual_entity_id_raw, "virtual_entity_id")

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)

    tenant_id = (params.get("tenant_id") or "").strip() or None
    provider = get_connection_provider()
    adjustment_totals: Dict[str, Dict[str, Decimal]] = {}
    method = "full"
    default_scope = "raw"
    with provider.connect(tenant_id=tenant_id, book_id=book_id) as conn:
        if consolidation_group_id is not None:
            assert_virtual_authorized(conn, int(consolidation_group_id), end_date)
            scope_cfg = get_trial_balance_scope_config(conn, int(consolidation_group_id), end_date)
            method = str(scope_cfg.get("consolidation_method") or "full")
            default_scope = str(scope_cfg.get("default_scope") or "raw")
            if not scope_raw:
                scope_mode = default_scope
        scope_data = _resolve_scope(
            conn,
            book_id=book_id,
            virtual_entity_id=virtual_entity_id,
            consolidation_group_id=consolidation_group_id,
            start_date=start_date,
            end_date=end_date,
        )
        if scope_data.get("scope_type") == SCOPE_VIRTUAL and scope_data.get("virtual_entity_id"):
            assert_virtual_authorized(conn, int(scope_data.get("virtual_entity_id")), end_date)

        scope_book_ids = list(scope_data.get("scope_book_ids") or [])
        amount_scope_tree = scope_data.get("amount_scope_tree") or []
        legacy_query_mode = str(scope_data.get("query_mode") or "single_book")
        if consolidation_group_id is not None:
            query_mode = "consolidation_group"
            query_mode_label = "合并组模式（成员汇总）"
        elif book_id is not None:
            query_mode = "single_book"
            query_mode_label = "单账套模式"
        else:
            query_mode = legacy_query_mode
            query_mode_label = str(scope_data.get("query_mode_label") or "单账套模式")
        amount_nodes_map = _flatten_amount_tree(amount_scope_tree)
        selected_amount_node_id = amount_node_id or str(scope_data.get("default_amount_node_id") or "")
        selected_amount_node = amount_nodes_map.get(selected_amount_node_id)
        if selected_amount_node:
            selected_ids = list(selected_amount_node.get("scope_book_ids") or [])
            if selected_ids:
                scope_book_ids = selected_ids
        elif amount_node_id:
            raise TrialBalanceError("amount_node_id_not_found")

        if not scope_book_ids:
            empty_scope_notice = scope_data.get("scope_notice") or "当前范围无可用主体"
            if consolidation_group_id is not None:
                effective_member_count = int(scope_data.get("effective_member_count") or 0)
                if scope_mode == "after_elim":
                    empty_scope_notice = (
                        f"当前为合并组汇总口径（汇总+抵销后）；有效成员 {effective_member_count}"
                        f"；method={method}；default_scope={default_scope}"
                    )
                else:
                    empty_scope_notice = (
                        f"当前为合并组汇总口径（仅汇总未抵销）；有效成员 {effective_member_count}"
                        f"；method={method}；default_scope={default_scope}"
                    )
            return {
                "book_id": book_id,
                "scope_type": scope_data.get("scope_type"),
                "scope_type_label": scope_data.get("scope_type_label"),
                "scope_book_ids": [],
                "scope_tree": scope_data.get("scope_tree") or [],
                "scope_warnings": scope_data.get("scope_warnings") or [],
                "amount_scope_tree": amount_scope_tree,
                "amount_node_id": selected_amount_node_id,
                "amount_node_title": (selected_amount_node or {}).get("title", ""),
                "amount_view_kind": (selected_amount_node or {}).get("view_kind", ""),
                "current_subject_name": scope_data.get("current_subject_name") or "",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "query_mode": query_mode,
                "query_mode_label": query_mode_label,
                "book_view_mode": legacy_query_mode,
                "consolidation_group_id": scope_data.get("consolidation_group_id"),
                "consolidation_group_name": scope_data.get("consolidation_group_name", ""),
                "consolidation_group_code": scope_data.get("consolidation_group_code", ""),
                "virtual_entity_id": scope_data.get("virtual_entity_id"),
                "virtual_entity_name": scope_data.get("virtual_entity_name", ""),
                "is_eliminated": scope_data.get("is_eliminated"),
                "scope": scope_mode,
                "scope_notice": empty_scope_notice,
                "items": [],
                "category_summary": [],
            }

        subjects = conn.execute(
            text(
                """
                SELECT code,
                       MAX(name) AS name,
                       MAX(category) AS category,
                       MIN(COALESCE(level, 1)) AS level,
                       MAX(parent_code) AS parent_code,
                       MAX(balance_direction) AS balance_direction
                FROM subjects
                WHERE book_id IN :book_ids
                GROUP BY code
                ORDER BY code ASC
                """
            ).bindparams(bindparam("book_ids", expanding=True)),
            {"book_ids": scope_book_ids},
        ).fetchall()

        sums = conn.execute(
            text(
                """
                SELECT vl.subject_code AS code,
                       SUM(vl.debit) AS debit_sum,
                       SUM(vl.credit) AS credit_sum
                FROM voucher_lines vl
                JOIN vouchers v ON v.id = vl.voucher_id
                WHERE v.book_id IN :book_ids
                  AND v.voucher_date BETWEEN :start_date AND :end_date
                  AND v.status = 'posted'
                GROUP BY vl.subject_code
                """
            ).bindparams(bindparam("book_ids", expanding=True)),
            {"book_ids": scope_book_ids, "start_date": start_date, "end_date": end_date},
        ).fetchall()
        if consolidation_group_id is not None and scope_mode == "after_elim":
            adjustment_totals = get_adjustment_totals_by_subject(
                conn,
                group_id=int(consolidation_group_id),
                period=end_date.strftime("%Y-%m"),
            )

    sum_map = {
        (row.code or "").strip(): {
            "debit": Decimal(str(row.debit_sum or 0)),
            "credit": Decimal(str(row.credit_sum or 0)),
        }
        for row in sums
    }
    if adjustment_totals:
        for code, delta in adjustment_totals.items():
            bucket = sum_map.setdefault(code, {"debit": Decimal("0"), "credit": Decimal("0")})
            bucket["debit"] += Decimal(str(delta.get("debit") or 0))
            bucket["credit"] += Decimal(str(delta.get("credit") or 0))

    nodes_by_code: Dict[str, Dict[str, object]] = {}
    order: List[str] = []
    existing_codes = {(s.code or "").strip() for s in subjects if (s.code or "").strip()}

    for s in subjects:
        code = (s.code or "").strip()
        if not code:
            continue
        parent_code = (s.parent_code or "").strip()
        if not parent_code or parent_code not in existing_codes:
            parent_code = _find_parent_by_prefix(code, existing_codes)
        sums_for = sum_map.get(code, {"debit": Decimal("0"), "credit": Decimal("0")})
        opening = Decimal("0")
        if (s.balance_direction or "").upper() == "CREDIT":
            ending = opening + sums_for["credit"] - sums_for["debit"]
        else:
            ending = opening + sums_for["debit"] - sums_for["credit"]

        node = {
            "code": code,
            "name": s.name,
            "category": s.category or "",
            "level": s.level,
            "parent_code": parent_code or None,
            "balance_direction": (s.balance_direction or "DEBIT").upper(),
            "opening_balance": opening,
            "raw_period_debit": sums_for["debit"],
            "raw_period_credit": sums_for["credit"],
            "raw_ending_balance": ending,
            "period_debit": sums_for["debit"],
            "period_credit": sums_for["credit"],
            "ending_balance": ending,
        }
        category_resolved = resolve_subject_category(code, s.category or "")
        node["category_code"] = category_resolved["category_code"]
        node["category_name"] = category_resolved["category_name"]
        node["category_source"] = category_resolved["category_source"]
        nodes_by_code[code] = node
        order.append(code)

    _sum_children(nodes_by_code, order)

    items = []
    category_summary: Dict[str, Dict[str, Decimal]] = {}
    for code in order:
        node = nodes_by_code[code]
        cat_code = node.get("category_code") or "UNKNOWN"
        cat_name = node.get("category_name") or "未分类"
        cat_key = f"{cat_code}|{cat_name}"
        if cat_key not in category_summary:
            category_summary[cat_key] = {
                "category_code": cat_code,
                "category_name": cat_name,
                "period_debit": Decimal("0"),
                "period_credit": Decimal("0"),
                "ending_balance": Decimal("0"),
            }
        category_summary[cat_key]["period_debit"] += node["raw_period_debit"]
        category_summary[cat_key]["period_credit"] += node["raw_period_credit"]
        category_summary[cat_key]["ending_balance"] += node["raw_ending_balance"]
        items.append(
            {
                "code": node["code"],
                "name": node["name"],
                "category": node["category_name"],
                "category_code": node["category_code"],
                "category_name": node["category_name"],
                "category_source": node["category_source"],
                "level": node["level"],
                "parent_code": node["parent_code"],
                "balance_direction": node["balance_direction"],
                "opening_balance": float(node["opening_balance"]),
                "period_debit": float(node["period_debit"]),
                "period_credit": float(node["period_credit"]),
                "ending_balance": float(node["ending_balance"]),
            }
        )

    scope_notice = scope_data.get("scope_notice") or "当前为单账套口径"
    if consolidation_group_id is not None:
        effective_member_count = int(scope_data.get("effective_member_count") or 0)
        if scope_mode == "after_elim":
            scope_notice = (
                f"当前为合并组汇总口径（汇总+抵销后）；有效成员 {effective_member_count}"
                f"；method={method}；default_scope={default_scope}"
            )
        else:
            scope_notice = (
                f"当前为合并组汇总口径（仅汇总未抵销）；有效成员 {effective_member_count}"
                f"；method={method}；default_scope={default_scope}"
            )

    return {
        "book_id": book_id,
        "scope_type": scope_data.get("scope_type"),
        "scope_type_label": scope_data.get("scope_type_label"),
        "scope_book_ids": scope_book_ids,
        "scope_tree": scope_data.get("scope_tree") or [],
        "scope_warnings": scope_data.get("scope_warnings") or [],
        "amount_scope_tree": amount_scope_tree,
        "amount_node_id": selected_amount_node_id,
        "amount_node_title": (selected_amount_node or {}).get("title", ""),
        "amount_view_kind": (selected_amount_node or {}).get("view_kind", ""),
        "current_subject_name": scope_data.get("current_subject_name") or "",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "query_mode": query_mode,
        "query_mode_label": query_mode_label,
        "book_view_mode": legacy_query_mode,
        "consolidation_group_id": scope_data.get("consolidation_group_id"),
        "consolidation_group_name": scope_data.get("consolidation_group_name", ""),
        "consolidation_group_code": scope_data.get("consolidation_group_code", ""),
        "virtual_entity_id": scope_data.get("virtual_entity_id"),
        "virtual_entity_name": scope_data.get("virtual_entity_name", ""),
        "is_eliminated": scope_data.get("is_eliminated"),
        "scope": scope_mode,
        "scope_notice": scope_notice,
        "items": items,
        "category_summary": [
            {
                "category": v["category_name"],
                "category_code": v["category_code"],
                "category_name": v["category_name"],
                "period_debit": float(v["period_debit"]),
                "period_credit": float(v["period_credit"]),
                "ending_balance": float(v["ending_balance"]),
            }
            for k, v in sorted(category_summary.items(), key=lambda x: x[0])
        ],
    }
