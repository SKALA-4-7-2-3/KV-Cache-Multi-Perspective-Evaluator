import json
import unittest
from copy import deepcopy

from team_review import prepare_repair, review_node, route_after_review
from team_review.demo import make_input
from team_review.rubric import ROLES


class ReviewTests(unittest.TestCase):
    def test_normal_is_eight_cells_with_used_references_only(self):
        state = make_input()
        state["documents"]["unused"] = deepcopy(state["documents"]["SW-01"])
        before = deepcopy(state)
        output = review_node(state)
        self.assertEqual(output["review"]["status"], "completed")
        self.assertEqual(output["review"]["input_cells"], 8)
        self.assertEqual(output["review"]["next"], "render")
        self.assertEqual(len(output["synthesis"]["comparison_matrix"]), 4)
        self.assertEqual(len(output["synthesis"]["references"]), 2)
        self.assertEqual(state, before)
        self.assertEqual(set(output), {"review", "synthesis"})

    def test_no_evidence_means_unknown_not_failure_or_zero(self):
        output = review_node(make_input("no_evidence"))
        self.assertEqual(output["review"]["status"], "partial")
        self.assertEqual(output["review"]["next"], "render")
        self.assertIsNone(output["synthesis"]["trl"]["SW-01"]["level"])
        self.assertEqual(output["synthesis"]["references"], [])

    def test_tool_failure_requests_only_affected_role(self):
        output = review_node(make_input("tool_failure"))
        self.assertEqual(output["review"]["status"], "partial")
        self.assertEqual(output["review"]["dirty_roles"], ["market"])
        self.assertEqual(output["review"]["input_cells"], 6)

    def test_invented_citation_is_removed_from_final_conclusion(self):
        output = review_node(make_input("bad_citation"))
        item = output["synthesis"]["comparison_matrix"][1]["SW-01"]["items"][0]
        self.assertEqual(item["judgment"], "unknown")
        self.assertEqual(item["evidence_ids"], [])
        self.assertEqual(item["conclusion"], "판단 보류")
        self.assertNotIn("invented-id", output["synthesis"]["used_evidence_ids"])

    def test_repair_limit_always_exits(self):
        output = review_node(make_input("retry_limit"))
        self.assertEqual(output["review"]["next"], "render")
        self.assertEqual(output["review"]["dirty_roles"], [])
        self.assertEqual(output["review"]["status"], "partial")
        with self.assertRaises(ValueError):
            prepare_repair(output)

    def test_fatal_authentication_is_not_success(self):
        output = review_node(make_input("fatal_error"))
        self.assertEqual(output["review"]["status"], "failed")
        self.assertEqual(output["review"]["next"], "render")
        self.assertEqual(output["synthesis"]["used_evidence_ids"], [])

    def test_different_metrics_and_methods_are_not_ranked(self):
        output = review_node(make_input())
        pair = output["synthesis"]["metric_comparisons"][0]
        self.assertFalse(pair["conditions_match"])
        self.assertIn("name", pair["different_fields"])
        self.assertIn("method", pair["different_fields"])
        self.assertNotIn("winner", json.dumps(output))

    def test_trl_cannot_jump_over_missing_stages(self):
        state = make_input()
        checks = state["assessments"]["technical"]["results"]["SW-01"]["trl_checks"]
        checks[5] = {"status": "met", "reason": "검증 불충분한 상향 주장", "evidence_ids": ["DUMMY-SW-01-p1"]}
        output = review_node(state)
        self.assertEqual(output["synthesis"]["trl"]["SW-01"]["level"], 1)
        self.assertEqual(output["review"]["dirty_roles"], list(ROLES))
        self.assertTrue(any(c["code"] == "trl_gap" for c in output["review"]["checks"]))

    def test_emulation_alone_cannot_prove_operational_trl(self):
        state = make_input()
        cell = state["assessments"]["technical"]["results"]["HW-01"]
        state["evidence"]["DUMMY-HW-01-p1"]["method"] = "emulation"
        for n in range(1, 8):
            cell["trl_checks"][n] = {"status": "met", "reason": "[DUMMY] 근거", "evidence_ids": ["DUMMY-HW-01-p1"]}
        output = review_node(state)
        self.assertEqual(output["synthesis"]["trl"]["HW-01"]["level"], 6)
        self.assertTrue(any(c["code"] == "trl_environment" for c in output["review"]["checks"]))

    def test_domain_cannot_claim_met_without_requirement(self):
        state = make_input()
        state["assessments"]["domain"]["results"]["SW-01"]["items"][0]["judgment"] = "met"
        output = review_node(state)
        item = output["synthesis"]["comparison_matrix"][3]["SW-01"]["items"][0]
        self.assertEqual(item["judgment"], "unknown")

    def test_production_rejects_synthetic_evidence(self):
        state = make_input()
        state["config"]["demo"] = False
        output = review_node(state)
        self.assertEqual(output["synthesis"]["used_evidence_ids"], [])
        self.assertEqual(output["review"]["status"], "partial")

    def test_wrong_technology_citation_is_rejected(self):
        state = make_input()
        state["assessments"]["market"]["results"]["SW-01"]["items"][0]["evidence_ids"] = ["DUMMY-HW-01-p1"]
        output = review_node(state)
        self.assertEqual(output["synthesis"]["comparison_matrix"][1]["SW-01"]["items"][0]["judgment"], "unknown")

    def test_page_outside_document_is_rejected(self):
        state = make_input()
        state["evidence"]["DUMMY-SW-01-p1"]["page"] = 999
        output = review_node(state)
        self.assertNotIn("DUMMY-SW-01-p1", output["synthesis"]["used_evidence_ids"])

    def test_missing_metric_context_is_not_reported_as_verified(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["items"][1]["metrics"][0]["baseline"] = None
        output = review_node(state)
        item = output["synthesis"]["comparison_matrix"][0]["SW-01"]["items"][1]
        self.assertEqual(item["metrics"], [])
        self.assertEqual(item["judgment"], "unknown")

    def test_missing_cell_is_explicit_and_schema_errors_do_not_leak_values(self):
        state = make_input()
        del state["assessments"]["domain"]["results"]["HW-01"]
        state["assessments"]["market"]["private_key"] = "do-not-print-this-value"
        output = review_node(state)
        self.assertNotIn("do-not-print-this-value", json.dumps(output))
        self.assertEqual(output["review"]["status"], "partial")

    def test_empty_config_or_wrong_version_fails(self):
        for config in ({}, {**make_input()["config"], "rubric_version": "old"}):
            state = make_input()
            state["config"] = config
            self.assertEqual(review_node(state)["review"]["status"], "failed")

    def test_page_budget(self):
        state = make_input()
        state["documents"]["SW-01"]["pages"] = 200
        output = review_node(state)
        self.assertEqual(output["review"]["status"], "failed")

    def test_partial_repair_does_not_require_rerunning_cached_roles(self):
        state = make_input("bad_citation")
        state.update(review_node(state))
        state.update(prepare_repair(state))
        state["assessments"]["market"] = make_input()["assessments"]["market"]
        state["assessments"]["market"]["round"] = 1
        output = review_node(state)
        self.assertEqual(output["review"]["status"], "completed")
        self.assertEqual(route_after_review(output), "render")

    def test_previous_error_history_does_not_fail_successful_repair(self):
        state = make_input("tool_failure")
        state.update(review_node(state))
        state.update(prepare_repair(state))
        state["assessments"]["market"] = make_input()["assessments"]["market"]
        state["assessments"]["market"]["round"] = 1
        self.assertEqual(review_node(state)["review"]["status"], "completed")

    def test_non_retryable_error_does_not_request_retry(self):
        state = make_input("tool_failure")
        state["errors"]["market-timeout"]["retryable"] = False
        self.assertEqual(review_node(state)["review"]["next"], "render")

    def test_unknown_trl_check_cannot_include_invented_reference(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["trl_checks"][5]["evidence_ids"] = ["invented-id"]
        output = review_node(state)
        self.assertNotIn("invented-id", json.dumps(output["synthesis"]))

    def test_json_round_trip_keeps_trl_keys_working(self):
        state = json.loads(json.dumps(make_input()))
        self.assertEqual(review_node(state)["synthesis"]["trl"]["SW-01"]["level"], 1)


if __name__ == "__main__":
    unittest.main()
