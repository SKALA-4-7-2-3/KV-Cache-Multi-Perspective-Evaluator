import unittest
from copy import deepcopy

from team_review import parse_input_markdown, render_input_markdown, review_handoff_node, read_report_input
from team_review.demo import make_input
from team_review.schema import merge_assessments, merge_by_id
from team_review import review_agent_node
from team_review.tests.test_synthesize import fake_generator, fake_auditor


class ContractTests(unittest.TestCase):
    def output(self, state):
        md = review_handoff_node(state)["report_input_md"]
        return read_report_input(md, require_allowed=False)[0], md

    def test_md_input_exact_round_trip(self):
        for case in ("normal", "tool_failure", "retry_limit", "fatal_error"):
            state = make_input(case)
            self.assertEqual(parse_input_markdown(render_input_markdown(state)), state)

    def test_md_input_rejects_freeform_and_duplicate_keys(self):
        for md in ("# 그냥 평가 의견", "~~~yaml\nschema_version: review-input-v1\nstate: {}\nstate: {}\n~~~\n",
                   "~~~yaml\nschema_version: review-input-v1\nstate: &a {child: *a}\n~~~\n"):
            with self.assertRaises(ValueError):
                parse_input_markdown(md)

    def test_failed_count_is_criteria_not_agents(self):
        header, _ = self.output(make_input("tool_failure"))
        self.assertEqual(header["failed_count"], 12)
        self.assertEqual(header["valid_criterion_blocks"], "34/46")
        self.assertEqual(header["valid_perspective_cells"], "8/8")
        self.assertEqual(header["report_generation"], "blocked")

    def test_unknown_count_is_all_46_blocks(self):
        header, _ = self.output(make_input("no_evidence"))
        self.assertEqual(header["unknown_count"], 46)
        self.assertEqual(header["failed_count"], 0)
        self.assertEqual(header["valid_criterion_blocks"], "46/46")

    def test_individual_failure_still_allows_partial_report(self):
        state = make_input()
        state["assessments"]["market"]["results"]["SW-01"]["items"][0].update(
            judgment="failed", conclusion="실행 실패", basis="unknown", evidence_ids=[], metrics=[], gaps=["도구 실패"])
        header, _ = read_report_input(review_agent_node(state, fake_generator, fake_auditor)["report_input_md"])
        self.assertEqual(header["failed_count"], 1)
        self.assertEqual(header["report_generation"], "allowed_with_gaps")

    def test_missing_domain_and_whole_role_are_blocked(self):
        for case in ("domain", "role", "tech"):
            state = make_input()
            if case == "domain":
                state["config"].pop("normalized_domain")
            elif case == "role":
                state["assessments"].pop("market")
            else:
                for role in state["assessments"].values():
                    role["results"].pop("HW-01")
            header, md = self.output(state)
            self.assertEqual(header["report_generation"], "blocked")
            with self.assertRaises(ValueError):
                read_report_input(md)

    def test_partial_citation_failure_is_not_structural_failure(self):
        header, md = self.output(make_input("bad_citation"))
        self.assertEqual(header["report_generation"], "blocked")
        self.assertEqual(header["failed_count"], 0)
        with self.assertRaises(ValueError):
            read_report_input(md)  # 1회 보완 요청이 진행 중인 중간 결과

    def test_frontmatter_and_reference_fields_exist(self):
        header, md = self.output(make_input())
        self.assertEqual(header["rubric_version"], "kv-cache-rubric-v1")
        self.assertEqual(header["reference_schema_version"], "reference-v1")
        self.assertEqual(md.count("- criterion_id:"), 46)
        self.assertIn("citation_key: SW01_RDKV", md)
        self.assertIn("## 12. SELF VALIDATION", md)

    def test_bad_header_counts_reference_keys_and_placeholders_rejected(self):
        _, md = self.output(make_input())
        bad = [md.replace("unknown_count: 0", "unknown_count: 99"),
               md.replace("citation_key: SW01_RDKV", "citation_key: HW01_PHOTONIC_CXL"),
               md.replace("- 연결 Reference ID: SW-01", "- 연결 Reference ID: WEB-NOT-FOUND"),
               md + "\n<내용>\n", md + "\n\\section{Report}\n",
               md.replace("- 분석 범위: mixed", "- 분석 범위: fake", 1)]
        for invalid in bad:
            with self.assertRaises(ValueError):
                read_report_input(invalid)

    def test_reducers_preserve_inputs_and_reject_collisions(self):
        old = {"one": {"value": 1}}
        self.assertEqual(merge_by_id(old, {"two": 2}), {"one": {"value": 1}, "two": 2})
        self.assertEqual(old, {"one": {"value": 1}})
        with self.assertRaises(ValueError):
            merge_by_id(old, {"one": {"value": 2}})
        role = make_input()["assessments"]["market"]
        changed = deepcopy(role)
        changed["status"] = "unknown"
        with self.assertRaises(ValueError):
            merge_assessments({"market": role}, {"market": changed})
        changed["round"] = 1
        self.assertEqual(merge_assessments({"market": role}, {"market": changed})["market"], changed)
        self.assertEqual(merge_assessments({"market": changed}, {"market": role})["market"], changed)
