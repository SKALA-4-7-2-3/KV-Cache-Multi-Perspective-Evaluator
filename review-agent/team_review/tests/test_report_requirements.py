"""Report 담당자의 전달 요청 회귀 검사. 모든 입력·생성기는 테스트 전용이다."""
import unittest
from unittest.mock import patch

from team_review import review_node, review_handoff_node, review_agent_node, read_report_input
from team_review.contract import REQUIREMENTS, SECTIONS
from team_review.demo import make_input
from team_review.tests.test_synthesize import fake_generator, fake_auditor


class ReportRequirementsTests(unittest.TestCase):
    def output(self, state=None):
        return review_handoff_node(state or make_input())["report_input_md"]

    def test_all_sections_remain_ordered(self):
        md = self.output()
        self.assertEqual([md.index(f"## {n}. {title}\n") for n, title in enumerate(SECTIONS, 1)],
                         sorted(md.index(f"## {n}. {title}\n") for n, title in enumerate(SECTIONS, 1)))

    def test_target_zero_ranges_and_scenarios_are_preserved(self):
        state = make_input()
        state["config"]["domain_requirements"] = {
            "quality": 0, "prefix_cache_hit_rate": 0, "gpu_model": "팀 지정 GPU",
            "context_tokens": "32K~128K", "concurrency": "낮음/중간/높음",
            "input_output_token_ratio": "10:1", "energy": "unknown",
        }
        md = self.output(state)
        section = md.split("## 8. 도메인 요구조건\n")[1].split("## 9.")[0]
        for key, value in state["config"]["domain_requirements"].items():
            self.assertIn(f"- {REQUIREMENTS[key]}: {value}\n", section)
        self.assertIn("- TTFT 목표: TBD", section)

    def test_unknown_source_metadata_is_never_invented(self):
        state = make_input()
        source = state["evidence"]["DUMMY-SW-01-p1"]
        source.update(independence="unknown", method="unspecified")
        md = self.output(state)
        section = md.split("## 9. 근거 인덱스\n")[1].split("## 10.")[0]
        self.assertIn("- 독립성: unknown", section)
        self.assertIn("- 검증 방식: unknown", section)
        self.assertNotIn("- 독립성: author", section)
        self.assertIn("주장의 독립 재현", section)

    def test_all_requested_methods_survive_separately(self):
        for method in ("gpu_experiment", "hardware_measurement", "emulation", "simulation", "analysis", "statement"):
            with self.subTest(method=method):
                state = make_input()
                state["evidence"]["DUMMY-SW-01-p1"].update(method=method, independence="independent")
                self.assertIn(f"- 검증 방식: {method}", self.output(state))
                self.assertIn("- 독립성: independent", self.output(state))

    def test_unknown_web_independence_does_not_erase_source(self):
        state = make_input()
        state["documents"]["WEB-1"] = {**state["documents"]["SW-01"], "kind": "web", "source_type": "official_product", "title": "테스트 기업 발표"}
        state["evidence"]["WEB-E1"] = {**state["evidence"]["DUMMY-SW-01-p1"], "id": "WEB-E1", "doc_id": "WEB-1", "page": None,
                                        "location": "본문 문단 3", "independence": "unknown", "technology_relevance": "indirect"}
        item = state["assessments"]["market"]["results"]["SW-01"]["items"][0]
        item.update(evidence_ids=["WEB-E1"], technology_relevance="indirect")
        md = self.output(state)
        self.assertIn("### [WEB-E1]", md)
        self.assertIn("- 해당 기술과의 관련성: indirect", md)
        self.assertIn("- 위치: 본문 문단 3", md)
        self.assertNotIn("p.None", md)

    def test_opinion_requires_speaker_and_is_not_inference(self):
        state = make_input()
        item = state["assessments"]["stakeholders"]["results"]["SW-01"]["items"][0]
        item.update(basis="opinion", attributed_to="테스트 발언자", stakeholder_group="개발자", technology_relevance="direct")
        md = self.output(state)
        self.assertIn("- 사실·추론: opinion", md)
        self.assertIn("- 발언 주체: 테스트 발언자", md)
        item.pop("attributed_to")
        output = review_node(state)
        self.assertEqual(output["synthesis"]["comparison_matrix"][2]["SW-01"]["items"][0]["judgment"], "unknown")

    def test_incomplete_metric_is_delivered_with_unknown_fields(self):
        state = make_input()
        metric = state["assessments"]["technical"]["results"]["SW-01"]["items"][1]["metrics"][0]
        metric.update(baseline=None, context_tokens="32K~128K", hardware="unknown")
        md = self.output(state)
        self.assertIn("- 값: 2.0", md)
        self.assertIn("- 비교 기준: unknown", md)
        self.assertIn("- 문맥 길이: 32K~128K", md)
        self.assertIn("- 하드웨어: unknown", md)
        self.assertIn("- Evidence ID: [DUMMY-SW-01-p1]", md)
        self.assertIn("직접 수치 비교 불가", md)

    def test_unknown_assessment_retains_valid_reported_metric(self):
        state = make_input()
        item = state["assessments"]["technical"]["results"]["SW-01"]["items"][1]
        item.update(judgment="unknown", basis="unknown", gaps=["도입 환경 미확인"])
        output = review_node(state)
        clean = output["synthesis"]["comparison_matrix"][0]["SW-01"]["items"][1]
        self.assertEqual(clean["judgment"], "unknown")
        self.assertEqual(clean["metrics"][0]["value"], 2.0)
        self.assertEqual(clean["conclusion"], "판단 보류")

    def test_self_validation_names_concrete_gaps(self):
        md = self.output()
        section = md.split("## 12. SELF VALIDATION\n")[1]
        self.assertIn("gpu_model", section)
        self.assertIn("DUMMY-SW-01-p1", section)
        self.assertNotIn("affected_items: 전체 해당 항목", section)
        self.assertIn("실행 중 승인·수정 대기는 없다", section)

    def test_nested_or_incomplete_frontmatter_is_rejected(self):
        md = self.output()
        for bad in (md.replace("demo: true\n", ""), md.replace("demo: true", 'demo: "true"'),
                    md.replace("demo: true", "demo: true\nextra:\n  child: value"),
                    md.replace("unknown_count: 0", "unknown_count: false")):
            with self.assertRaises(ValueError):
                read_report_input(bad, require_allowed=False)

    def test_synthetic_and_upstream_demo_flags_cannot_be_hidden(self):
        state = make_input()
        state["config"]["demo"] = False
        self.assertTrue(review_node(state)["synthesis"]["demo"])
        for e in state["evidence"].values():
            e["synthetic"] = False
        state["assessments"]["market"]["demo"] = True
        self.assertTrue(review_node(state)["synthesis"]["demo"])
        del state["config"]["demo"]
        self.assertTrue(review_node(state)["synthesis"]["demo"])

    def test_real_declared_partial_is_allowed_with_gaps(self):
        # 플래그 처리의 단위 테스트일 뿐 실제 실행 결과를 생성하지 않는다.
        state = make_input()
        state["config"]["demo"] = False
        for e in state["evidence"].values():
            e["synthetic"] = False
        # 실제 API에 해당하는 분기를 mock으로 검사하며 이 결과는 파일로 배포하지 않는다.
        with patch("team_review.synthesize.call_openai", side_effect=lambda p, **kw: fake_generator(p)), \
             patch("team_review.synthesize.call_grounding", side_effect=lambda p, **kw: fake_auditor(p)):
            md = review_agent_node(state)["report_input_md"]
        header, _ = read_report_input(md, for_submission=True)
        self.assertEqual(header["report_generation"], "allowed_with_gaps")
        state["config"]["demo"] = True
        with self.assertRaises(ValueError):
            read_report_input(review_agent_node(state, fake_generator, fake_auditor)["report_input_md"], for_submission=True)

    def test_injected_test_generator_always_marks_demo(self):
        state = make_input()
        state["config"]["demo"] = False
        for e in state["evidence"].values():
            e["synthetic"] = False
        header, _ = read_report_input(review_agent_node(state, fake_generator, fake_auditor)["report_input_md"])
        self.assertTrue(header["demo"])

    def test_metric_conditions_and_evidence_fields_are_required(self):
        md = self.output()
        for bad in (md.replace("- 비교 기준: DUMMY-BASELINE", "- 비교 기준:"),
                    md.replace("- 검증 상태: verified", "- 검증 상태:"),
                    md.replace("- 독립성: unknown", "- 독립성: unavailable")):
            with self.assertRaises(ValueError):
                read_report_input(bad, require_allowed=False)

    def test_emulation_cannot_be_relabelled_as_hardware_measurement(self):
        state = make_input()
        state["evidence"]["DUMMY-HW-01-p1"]["method"] = "emulation"
        state["assessments"]["technical"]["results"]["HW-01"]["items"][1]["metrics"][0]["method"] = "hardware_measurement"
        result = review_node(state)
        self.assertEqual(result["review"]["next"], "repair")
        self.assertEqual(result["synthesis"]["comparison_matrix"][0]["HW-01"]["items"][1]["judgment"], "unknown")

    def test_reference_key_may_start_with_number(self):
        state = make_input()
        state["documents"]["SW-01"]["citation_key"] = "2026_RDKV"
        self.assertIn("- citation_key: 2026_RDKV", self.output(state))


if __name__ == "__main__":
    unittest.main()
