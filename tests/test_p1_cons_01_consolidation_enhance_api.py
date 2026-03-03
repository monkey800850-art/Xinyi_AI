import json
import os
import runpy
import sys
import time
import unittest
from pathlib import Path

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app.db import get_engine


class P1Cons01ConsolidationEnhanceApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"
        os.environ["SECRET_KEY"] = "test-secret-for-p1-cons-01"
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        ns = runpy.run_path(str(repo_root / "app.py"))
        cls.app = ns["create_app"]()
        cls.client = cls.app.test_client()
        cls.engine = get_engine()
        cls.sid = str(int(time.time()))[-6:]
        cls._ensure_tables()

    @classmethod
    def _ensure_tables(cls):
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sys_users (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        username VARCHAR(64) NOT NULL UNIQUE,
                        display_name VARCHAR(64) NULL,
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        password_hash VARCHAR(255) NULL,
                        failed_attempts INT NOT NULL DEFAULT 0,
                        locked_until DATETIME NULL,
                        last_login_at DATETIME NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sys_roles (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        code VARCHAR(64) NOT NULL UNIQUE,
                        name VARCHAR(64) NOT NULL,
                        is_enabled TINYINT NOT NULL DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sys_user_roles (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        user_id BIGINT NOT NULL,
                        role_id BIGINT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_authorizations (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_subject_id BIGINT NOT NULL,
                        approval_document_number VARCHAR(255) NOT NULL,
                        approval_document_name VARCHAR(255) NOT NULL,
                        effective_start DATE NOT NULL,
                        effective_end DATE NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(text("DELETE FROM sys_user_roles WHERE user_id=900001"))
            conn.execute(text("DELETE FROM sys_users WHERE id=900001"))
            conn.execute(
                text(
                    """
                    INSERT INTO sys_users (
                        id, username, display_name, is_enabled, password_hash, failed_attempts, locked_until
                    ) VALUES (
                        900001, 'p1c01_admin', 'P1C01 Admin', 1, :password_hash, 0, NULL
                    )
                    """
                ),
                {"password_hash": generate_password_hash("P1C01@123")},
            )
            role = conn.execute(text("SELECT id FROM sys_roles WHERE code='admin' LIMIT 1")).fetchone()
            if not role:
                conn.execute(text("INSERT INTO sys_roles (code, name, is_enabled) VALUES ('admin', '管理员', 1)"))
                role = conn.execute(text("SELECT id FROM sys_roles WHERE code='admin' LIMIT 1")).fetchone()
            conn.execute(text("DELETE FROM sys_user_roles WHERE user_id=900001"))
            conn.execute(text("INSERT INTO sys_user_roles (user_id, role_id) VALUES (900001, :rid)"), {"rid": int(role.id)})

    def _login(self):
        # Bypass auth endpoint dependency; seed a valid session context directly.
        with self.client.session_transaction() as sess:
            sess["auth_ctx"] = {"user_id": 900001, "username": "p1c01_admin", "role": "admin"}
            sess["auth_expires_at"] = "2099-12-31T23:59:59+00:00"

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"P1C01-{self.sid}-{self._testMethodName[-2:]}", "group_name": "P1C01 Group"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"),
                {"gid": group_id},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id, approval_document_number, approval_document_name,
                        effective_start, effective_end, status, operator_id
                    ) VALUES (
                        :gid, :doc_no, 'P1-CONS-01 AUTH', '2020-01-01', '2099-12-31', 'active', 1
                    )
                    """
                ),
                {"gid": group_id, "doc_no": f"AUTH-{group_id}"},
            )

    def _seed_source(self, gid: int):
        reports = ["BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW", "EQUITY_CHANGE"]
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM consolidation_adjustments WHERE group_id=:gid AND period='2026-03'"), {"gid": gid})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_adjustments (group_id, period, status, operator_id, lines_json, source, rule_code, evidence_ref, batch_id)
                    VALUES (:gid, '2026-03', 'draft', 1, :lines_json, 'generated', 'P1C01', 'E-P1C01', 'ADJ-P1C01')
                    """
                ),
                {
                    "gid": gid,
                    "lines_json": json.dumps(
                        [{"subject_code": "1001", "debit": "100", "credit": "0"}, {"subject_code": "2201", "debit": "0", "credit": "100"}],
                        ensure_ascii=False,
                    ),
                },
            )
            conn.execute(text("DELETE FROM consolidation_report_snapshots WHERE group_id=:gid AND period='2026-03'"), {"gid": gid})
            for code in reports:
                conn.execute(
                    text(
                        """
                        INSERT INTO consolidation_report_snapshots (
                            group_id, period, report_code, template_code, source, rule_code, batch_id, status,
                            template_json, report_json, operator_id
                        ) VALUES (
                            :gid, '2026-03', :code, :code, 'generated', 'CONS_REPORTS_GEN', 'RPT-P1C01', 'draft',
                            '{}', :report_json, 1
                        )
                        """
                    ),
                    {
                        "gid": gid,
                        "code": code,
                        "report_json": json.dumps({"items": [{"item_code": f"{code}_1", "label": "L1", "amount": 10}]}, ensure_ascii=False),
                    },
                )
            conn.execute(text("DELETE FROM consolidation_approval_flows WHERE group_id=:gid AND period='2026-03'"), {"gid": gid})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_approval_flows (
                        group_id, period, batch_id, check_result, approval_status, approver_id, operator_id
                    ) VALUES (
                        :gid, '2026-03', 'FINAL-P1C01', 'passed', 'approved', 99, 1
                    )
                    """
                ),
                {"gid": gid},
            )
            conn.execute(text("DELETE FROM consolidation_audit_packages WHERE group_id=:gid AND period='2026-03'"), {"gid": gid})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_audit_packages (
                        group_id, period, batch_id, file_name, source, rule_code, status, package_meta_json, package_blob, operator_id
                    ) VALUES (
                        :gid, '2026-03', 'AUDPKG-P1C01', 'a.xlsx', 'generated', 'CONS30_DISCLOSURE_AUDIT_PACKAGE', 'draft', '{}', :blob, 1
                    )
                    """
                ),
                {"gid": gid, "blob": b"X"},
            )

    def test_enhancement_api(self):
        self._login()
        gid = self._create_group()
        self._grant(gid)
        self._seed_source(gid)

        resp = self.client.post(
            "/api/consolidation/enhancements",
            json={"consolidation_group_id": gid, "period": "2026-03", "operator_id": 1},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(int((body.get("disclosure_notes") or {}).get("check_count") or 0), 3)
        self.assertGreaterEqual(int((body.get("audit_index") or {}).get("indexed_count") or 0), 4)
        self.assertGreaterEqual(int((body.get("batch_trace") or {}).get("trace_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
