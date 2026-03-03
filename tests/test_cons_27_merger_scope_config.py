import os
import runpy
import sys
import time
import unittest
from datetime import date
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_engine
from app.services.consolidation_parameters_service import get_trial_balance_scope_config


class Cons27MergerScopeConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"

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
                    CREATE TABLE IF NOT EXISTS consolidation_groups (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_code VARCHAR(64) NOT NULL UNIQUE,
                        group_name VARCHAR(128) NOT NULL,
                        group_type VARCHAR(32) NOT NULL DEFAULT 'standard',
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        note VARCHAR(255) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_parameters (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_subject_id BIGINT NOT NULL,
                        parent_subject_type VARCHAR(64) NOT NULL DEFAULT '',
                        parent_subject_id BIGINT NOT NULL DEFAULT 0,
                        child_subject_type VARCHAR(64) NOT NULL DEFAULT '',
                        child_subject_id BIGINT NOT NULL DEFAULT 0,
                        ownership_ratio DECIMAL(9,6) NOT NULL DEFAULT 1.000000,
                        control_type VARCHAR(32) NOT NULL DEFAULT '',
                        include_in_consolidation TINYINT NOT NULL DEFAULT 1,
                        effective_start DATE NOT NULL DEFAULT '2000-01-01',
                        effective_end DATE NOT NULL DEFAULT '2099-12-31',
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        consolidation_method VARCHAR(16) NOT NULL DEFAULT 'full',
                        default_scope VARCHAR(16) NOT NULL DEFAULT 'raw',
                        effective_from DATE NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sys_rules (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        rule_key VARCHAR(128) NOT NULL UNIQUE,
                        rule_value VARCHAR(255) NOT NULL,
                        description VARCHAR(255) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={
                "group_code": f"CONS27-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS27组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def test_01_merger_scope_and_criteria_config(self):
        gid = self._create_group()
        payload = {
            "consolidation_group_id": gid,
            "start_period": "2025-04",
            "note": "cons27-test",
            "consolidation_method": "full",
            "default_scope": "after_elim",
            "currency": "CNY",
            "fx_rate_policy": "closing_rate",
            "accounting_policy": "cn_gaap",
            "period_elimination": True,
            "operator_id": 1,
        }
        first = self.client.post("/task/cons-27", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "合并范围与口径配置完成")
        scope_contract = body.get("scope_contract") or {}
        self.assertEqual(int(scope_contract.get("consolidation_group_id") or 0), gid)
        self.assertEqual(str(scope_contract.get("start_period") or ""), "2025-04")
        self.assertEqual(str(scope_contract.get("default_scope") or ""), "after_elim")
        self.assertEqual(str(scope_contract.get("consolidation_method") or ""), "full")
        criteria = body.get("criteria") or {}
        self.assertEqual(str(criteria.get("currency") or ""), "CNY")
        self.assertEqual(str(criteria.get("fx_rate_policy") or ""), "closing_rate")
        self.assertEqual(str(criteria.get("accounting_policy") or ""), "cn_gaap")
        self.assertTrue(bool(criteria.get("period_elimination")))

        # re-run with update to verify upsert
        payload2 = dict(payload)
        payload2["currency"] = "USD"
        payload2["period_elimination"] = False
        second = self.client.post("/task/cons-27", json=payload2)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        body2 = second.get_json() or {}
        self.assertEqual(str((body2.get("criteria") or {}).get("currency") or ""), "USD")
        self.assertFalse(bool((body2.get("criteria") or {}).get("period_elimination")))

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT virtual_subject_id, control_type, child_subject_type, consolidation_method, default_scope
                    FROM consolidation_parameters
                    WHERE virtual_subject_id=:gid
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row.virtual_subject_id or 0), gid)
            self.assertEqual(str(row.control_type or ""), "2025-04")
            self.assertEqual(str(row.child_subject_type or ""), "cons27-test")
            self.assertEqual(str(row.consolidation_method or ""), "full")
            self.assertEqual(str(row.default_scope or ""), "after_elim")

            rules = conn.execute(
                text(
                    """
                    SELECT rule_key, rule_value
                    FROM sys_rules
                    WHERE rule_key IN (
                        :k1, :k2, :k3, :k4
                    )
                    ORDER BY rule_key ASC
                    """
                ),
                {
                    "k1": f"consolidation:currency:{gid}",
                    "k2": f"consolidation:fx_rate_policy:{gid}",
                    "k3": f"consolidation:accounting_policy:{gid}",
                    "k4": f"consolidation:period_elimination:{gid}",
                },
            ).fetchall()
            kv = {str(r.rule_key): str(r.rule_value) for r in rules}
            self.assertEqual(kv.get(f"consolidation:currency:{gid}"), "USD")
            self.assertEqual(kv.get(f"consolidation:fx_rate_policy:{gid}"), "closing_rate")
            self.assertEqual(kv.get(f"consolidation:accounting_policy:{gid}"), "cn_gaap")
            self.assertEqual(kv.get(f"consolidation:period_elimination:{gid}"), "0")

            # effect check: default_scope/method should be effective in scope config
            scope_cfg = get_trial_balance_scope_config(conn, gid, date.fromisoformat("2025-04-30"))
        self.assertEqual(str(scope_cfg.get("consolidation_method") or ""), "full")
        self.assertEqual(str(scope_cfg.get("default_scope") or ""), "after_elim")


if __name__ == "__main__":
    unittest.main()
