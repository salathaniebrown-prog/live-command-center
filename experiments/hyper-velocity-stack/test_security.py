import unittest

from main import assert_observation_toolset, validate_and_mark_payload


class ObservationBoundaryTests(unittest.TestCase):
    def test_authority_cannot_be_overridden(self):
        secured = validate_and_mark_payload(
            {"authority": "command", "commandEligible": True, "provenance": {"source": "test"}},
            {"authority": "command", "commandEligible": True},
        )
        self.assertEqual(secured["authority"], "observation")
        self.assertIs(secured["commandEligible"], False)

    def test_unapproved_tool_is_rejected(self):
        with self.assertRaises(PermissionError):
            assert_observation_toolset(["status", "arm_vehicle"])


if __name__ == "__main__":
    unittest.main()
