"""실제 기술 등급이 아닌 더미 입력으로 TRL 판정과 후단 전달을 검증한다."""

import unittest

from team_review import read_report_input, review_agent_node, review_handoff_node, review_node
from team_review.demo import make_input
from team_review.tests.test_synthesize import fake_generator, fake_auditor


class TRLHandoffTests(unittest.TestCase):
    def test_reviewer_marks_derived_trl_as_inference(self):
        state = make_input()
        cell = state["assessments"]["technical"]["results"]["SW-01"]
        maturity = next(i for i in cell["items"] if i["criterion_id"] == "maturity")
        maturity.update(judgment="unknown", basis="unknown", conclusion="최종 판정은 review 담당")
        output = review_node(state)
        item = next(i for i in output["synthesis"]["comparison_matrix"][0]["SW-01"]["items"]
                    if i["criterion_id"] == "maturity")
        self.assertEqual(output["synthesis"]["trl"]["SW-01"]["level"], 1)
        self.assertEqual(item["basis"], "inference")
        self.assertEqual(item["evidence_ids"], ["DUMMY-SW-01-p1"])

    def test_missing_technical_cannot_borrow_other_perspectives_for_trl(self):
        state = make_input()
        del state["assessments"]["technical"]
        output = review_handoff_node(state)
        self.assertEqual(output["synthesis"]["trl"], {})
        section = output["report_input_md"].split("## 5. TRL 판정 결과\n")[1].split("## 6.")[0]
        self.assertEqual(section.count("- 추정 TRL: unknown"), 2)
        self.assertIn("다른 관점의 의견으로 대체하지 않는다", section)

    def test_missing_cost_and_independent_replication_keep_confirmed_level(self):
        state = make_input()
        for role, cid in (("market", "cost"), ("technical", "validation_scope")):
            item = next(i for i in state["assessments"][role]["results"]["SW-01"]["items"]
                        if i["criterion_id"] == cid)
            item.update(judgment="unknown", evidence_ids=[], metrics=[], gaps=["비용·독립 재현 자료 미확인"])
        self.assertEqual(review_node(state)["synthesis"]["trl"]["SW-01"]["level"], 1)

    def test_all_stages_reach_md_with_reasons_and_sources(self):
        state = make_input()
        output = review_handoff_node(state)
        _, body = read_report_input(output["report_input_md"], require_allowed=False)
        section = body.split("## 5. TRL 판정 결과\n")[1].split("## 6.")[0]
        for trl in output["synthesis"]["trl"].values():
            for check in trl["checks"]:
                self.assertIn(f"| {check['level']} | {check['status']} | {check['reason']} |", section)
                for eid in check["evidence_ids"]:
                    self.assertIn(f"[{eid}]", section)
        self.assertEqual(section.count("| 9 | unknown |"), 2)

    def test_invalid_stage_source_in_md_is_rejected(self):
        md = review_handoff_node(make_input())["report_input_md"]
        md = md.replace("| 1 | met | [DUMMY] 1단계 통과 사례 | [DUMMY-SW-01-p1] |",
                        "| 1 | met | [DUMMY] 1단계 통과 사례 | [invented-trl] |", 1)
        with self.assertRaisesRegex(ValueError, "TRL 단계별 Evidence"):
            read_report_input(md)

    def test_final_trl_reaches_synthesis_and_report_without_extra_call(self):
        received = []

        def generate(payload):
            received.append(payload["trl"])
            return fake_generator(payload)

        output = review_agent_node(make_input(), generate, fake_auditor)
        self.assertEqual(received, [output["synthesis"]["trl"]])
        self.assertEqual(received[0]["SW-01"]["level"], 1)
        self.assertEqual(output["synthesis"]["integrated"]["status"], "completed")
        self.assertEqual(output["synthesis"]["integrated"]["api_calls"], 0)
        read_report_input(output["report_input_md"])


if __name__ == "__main__":
    unittest.main()
