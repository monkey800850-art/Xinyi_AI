import unittest

from app.services.user_experience_service import (
    UserExperienceError,
    guide_user_step,
    show_error_message,
    show_operation_guide,
)


class P1Ux01UnitTest(unittest.TestCase):
    def test_guide_user_step(self):
        result = guide_user_step("reimbursement")
        self.assertEqual(result["process_name"], "reimbursement")
        self.assertEqual(int(result["step_count"]), 3)
        self.assertEqual(result["steps"][0]["step_no"], 1)

    def test_show_error_message(self):
        msg = show_error_message("incorrect_amount")
        self.assertIn("金额", msg["message"])
        self.assertTrue(msg["action"])

        unknown = show_error_message("x-unknown")
        self.assertEqual(unknown["error_type"], "x-unknown")
        self.assertIn("未知错误", unknown["message"])

    def test_show_operation_guide(self):
        result = show_operation_guide("consolidation")
        self.assertEqual(result["process_name"], "consolidation")
        self.assertTrue(result["guide"])
        self.assertGreaterEqual(len(result["tips"]), 1)

    def test_invalid_process_name(self):
        with self.assertRaises(UserExperienceError):
            guide_user_step("invalid")
        with self.assertRaises(UserExperienceError):
            show_operation_guide("")


if __name__ == "__main__":
    unittest.main()
