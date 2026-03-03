import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from app.services.reimbursement_service import (
    ReimbursementError,
    list_reimbursement_sla_reminders,
    submit_reimbursement,
)


class _Row:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Result:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, reimbursement_row, budget_rule=None, occupied=Decimal("0"), reminders=None):
        self.reimbursement_row = reimbursement_row
        self.budget_rule = budget_rule
        self.occupied = occupied
        self.reminders = reminders or []
        self.last_update = None
        self.logs = 0

    def execute(self, stmt, params=None):
        sql = str(stmt).lower()
        params = params or {}
        if "information_schema.columns" in sql and "reimbursements" in sql:
            return _Result(
                [
                    _Row(column_name="budget_check"),
                    _Row(column_name="attachment_check"),
                    _Row(column_name="approval_sla"),
                ]
            )
        if "select * from reimbursements" in sql:
            return _Result([self.reimbursement_row] if self.reimbursement_row else [])
        if "select rule_value from sys_rules" in sql:
            if self.budget_rule is None:
                return _Result([])
            return _Result([_Row(rule_value=str(self.budget_rule))])
        if "sum(total_amount)" in sql:
            return _Result([_Row(occupied=self.occupied)])
        if "update reimbursements set" in sql and "status='in_review'" in sql:
            self.last_update = params
            return _Result([])
        if "insert into reimbursement_logs" in sql:
            self.logs += 1
            return _Result([])
        if "from reimbursements" in sql and "approval_sla" in sql and "in_review" in sql:
            return _Result(self.reminders)
        return _Result([])


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        return _Ctx(self.conn)

    def connect(self):
        return _Ctx(self.conn)


class Fin01ReimbursementEnhanceUnitTest(unittest.TestCase):
    def test_submit_requires_attachment(self):
        row = _Row(
            id=1,
            status="draft",
            book_id=1,
            department="FIN",
            total_amount=Decimal("10"),
            attachment_count=0,
            attachments="",
            approval_sla=None,
        )
        conn = _FakeConn(reimbursement_row=row)
        with patch("app.services.reimbursement_service.get_engine", return_value=_FakeEngine(conn)):
            with self.assertRaises(ReimbursementError) as ctx:
                submit_reimbursement(1, "u1", "maker")
        self.assertEqual(str(ctx.exception), "attachment_required")

    def test_submit_budget_exceeded(self):
        row = _Row(
            id=2,
            status="draft",
            book_id=1,
            department="FIN",
            total_amount=Decimal("60"),
            attachment_count=1,
            attachments="[a]",
            approval_sla=None,
        )
        conn = _FakeConn(reimbursement_row=row, budget_rule=Decimal("100"), occupied=Decimal("50"))
        with patch("app.services.reimbursement_service.get_engine", return_value=_FakeEngine(conn)):
            with self.assertRaises(ReimbursementError) as ctx:
                submit_reimbursement(2, "u1", "maker")
        self.assertEqual(str(ctx.exception), "budget_exceeded")

    def test_submit_success_sets_checks(self):
        row = _Row(
            id=3,
            status="draft",
            book_id=1,
            department="FIN",
            total_amount=Decimal("60"),
            attachment_count=2,
            attachments="[a,b]",
            approval_sla=None,
        )
        conn = _FakeConn(reimbursement_row=row, budget_rule=Decimal("200"), occupied=Decimal("20"))
        with patch("app.services.reimbursement_service.get_engine", return_value=_FakeEngine(conn)), patch(
            "app.services.reimbursement_service._table_columns",
            return_value={"budget_check", "attachment_check", "approval_sla"},
        ):
            out = submit_reimbursement(3, "u1", "maker")
        self.assertEqual(out["status"], "in_review")
        self.assertIsNotNone(conn.last_update)
        self.assertEqual(int(conn.last_update["attachment_check"]), 1)
        self.assertEqual(int(conn.last_update["budget_check"]), 1)
        self.assertEqual(conn.logs, 1)

    def test_list_sla_reminders(self):
        now = datetime.now()
        reminders = [
            _Row(
                id=9,
                title="R1",
                applicant="A",
                department="FIN",
                status="in_review",
                approval_sla=now - timedelta(hours=5),
            )
        ]
        conn = _FakeConn(reimbursement_row=None, reminders=reminders)
        with patch("app.services.reimbursement_service.get_engine", return_value=_FakeEngine(conn)), patch(
            "app.services.reimbursement_service._table_columns",
            return_value={"approval_sla"},
        ):
            out = list_reimbursement_sla_reminders({"book_id": "1"})
        self.assertEqual(len(out["items"]), 1)
        self.assertGreater(out["items"][0]["overdue_hours"], 0)


if __name__ == "__main__":
    unittest.main()
