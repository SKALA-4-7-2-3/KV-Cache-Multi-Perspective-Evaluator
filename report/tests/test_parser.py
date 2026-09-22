import unittest

from report_agent.parser import InputContractError, parse_report_input
from tests.helpers import sample_input


class ParserTests(unittest.TestCase):
    def test_parse_valid_input(self) -> None:
        parsed = parse_report_input(sample_input())
        self.assertEqual(parsed.metadata["report_generation"], "allowed_with_gaps")
        self.assertEqual(
            parsed.allowed_citation_keys,
            {"SW01_RDKV", "HW01_PHOTONIC_CXL"},
        )
        self.assertEqual(len(parsed.warnings), 3)

    def test_blocked_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(InputContractError, "blocked"):
            parse_report_input(sample_input("blocked"))

    def test_latest_review_contract_fields_are_enforced(self) -> None:
        for key in (
            "human_review_scope",
            "semantic_validation_status",
            "demo",
            "next",
            "synthesis_status",
        ):
            with self.subTest(key=key):
                lines = [
                    line
                    for line in sample_input().splitlines()
                    if not line.startswith(f"{key}:")
                ]
                with self.assertRaisesRegex(InputContractError, "필수 metadata 누락"):
                    parse_report_input("\n".join(lines) + "\n")

    def test_numeric_citation_key_is_allowed(self) -> None:
        parsed = parse_report_input(
            sample_input().replace("SW01_RDKV", "2026_RDKV")
        )
        self.assertIn("2026_RDKV", parsed.allowed_citation_keys)

    def test_unvalidated_synthesis_is_rejected(self) -> None:
        with self.assertRaisesRegex(InputContractError, "의미 검사"):
            parse_report_input(
                sample_input().replace(
                    "semantic_validation_status: passed",
                    "semantic_validation_status: rejected",
                )
            )


if __name__ == "__main__":
    unittest.main()
