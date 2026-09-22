import unittest
from pathlib import Path

from team_review import parse_input_markdown, review_handoff_node, review_agent_node, read_report_input
from team_review.demo import make_input
from team_review.tests.test_synthesize import fake_generator, fake_auditor
from team_review.markdown import summary_materials


class SummaryConsistencyTests(unittest.TestCase):
    def test_all_perspectives_and_integrated_risks_reach_summary(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["items"][0]["counter_evidence"] = ["기술적 한계 테스트"]
        state["assessments"]["market"]["results"]["HW-01"]["items"][0]["gaps"] = ["가격 공백 테스트"]
        result = review_agent_node(state, fake_generator, fake_auditor)
        summary = result["report_input_md"].split("## 4. 관점별 평가")[0]
        self.assertIn("기술적 한계 테스트", summary)
        self.assertIn("가격 공백 테스트", summary)
        self.assertIn("통합 부담", summary)
        self.assertNotIn("- 주요 위험: 없음", summary)
        self.assertNotIn("- 핵심 제약: 없음", summary)

    def test_missing_risk_fields_do_not_mean_no_risk(self):
        result = review_handoff_node(make_input())
        self.assertIn("미평가·미확인 (위험·제약이 없다는 뜻이 아님)", result["report_input_md"])

    def test_no_quantitative_pairs_does_not_mean_identical_conditions(self):
        state = make_input()
        for cell in state["assessments"]["technical"]["results"].values():
            for item in cell["items"]:
                item["metrics"] = []
        md = review_handoff_node(state)["report_input_md"]
        self.assertIn("실험 조건이 같다는 뜻은 아니다", md)
        self.assertNotIn("### 실험 조건 차이\n\n- 없음", md)

    def test_unlinked_perspective_is_not_reported_as_absent(self):
        md = review_agent_node(make_input(), fake_generator, fake_auditor)["report_input_md"]
        self.assertIn("기술 성숙도 관점: 이 의견에 연결된 평가 없음", md)
        self.assertNotIn("- 기술 성숙도 관점: 없음", md)

    def test_no_additional_risk_and_editorial_review_are_explicit(self):
        from team_review import render_review_markdown

        state = make_input()
        result = review_agent_node(state, fake_generator, fake_auditor)
        result["synthesis"]["integrated"]["opinions"][0]["risks"] = []
        result["synthesis"]["integrated"]["editorial_review"] = "AI 보조 검수; 사람 검수 별도"
        md = render_review_markdown(state, result)
        self.assertIn("추가 위험: 별도 기재 없음; 위험이 없다는 뜻이 아님", md)
        self.assertIn("종합 문장 검수: AI 보조 검수; 사람 검수 별도", md)
        with self.assertRaises(ValueError):
            read_report_input(md)  # 의미 검사 후 편집된 의견은 재검사 전 전달 금지

    def test_joint_risk_is_not_attributed_to_each_technology_alone(self):
        def generate(payload):
            result = fake_generator(payload)
            next(o for o in result["opinions"] if o["kind"] == "joint")["risks"] = ["DUMMY 공동 구성에서만 생기는 위험"]
            return result
        result = review_agent_node(make_input(), generate, fake_auditor)
        for tech in ("SW-01", "HW-01"):
            self.assertNotIn("DUMMY 공동 구성", " ".join(summary_materials(result["synthesis"], tech)["risks"]))
        self.assertIn("DUMMY 공동 구성에서만 생기는 위험", result["report_input_md"])
        self.assertIn("병행 해석은 입력 평가에 기반한 가설", result["report_input_md"])

    def test_paper_fixture_preserves_specific_limits_without_llm(self):
        state = parse_input_markdown(Path(__file__).parents[1].joinpath("examples/paper.input.md").read_text())
        result = review_handoff_node(state)
        sw = summary_materials(result["synthesis"], "SW-01")
        hw = summary_materials(result["synthesis"], "HW-01")
        self.assertIn("attention 변화", " ".join(sw["risks"]))
        self.assertIn("TriZone", " ".join(sw["risks"]))
        self.assertIn("품질 손실", " ".join(sw["risks"]))
        self.assertIn("물리 PF 장비", " ".join(hw["risks"]))
        self.assertIn("CXL 호스트", " ".join(hw["risks"]))
        self.assertIn("비용 편익", " ".join(hw["gaps"]))
        header, _ = read_report_input(result["report_input_md"], require_allowed=False)
        self.assertEqual(header["unknown_count"], 10)
        self.assertEqual(header["reference_candidate_count"], 2)

    def test_demo_and_partial_are_drafts_not_final_submission(self):
        md = review_agent_node(make_input(), fake_generator, fake_auditor)["report_input_md"]
        read_report_input(md)
        with self.assertRaises(ValueError):
            read_report_input(md, for_submission=True)
        with self.assertRaises(ValueError):
            read_report_input(md.replace("모의 Agent 입력을 포함", "표시 삭제"))
