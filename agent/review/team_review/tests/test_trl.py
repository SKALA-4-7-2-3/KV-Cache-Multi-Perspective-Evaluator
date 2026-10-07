"""실제 기술 등급이 아닌 더미 입력으로 TRL 판정과 후단 전달을 검증한다."""

import unittest
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from team_review import read_report_input, review_agent_node, review_handoff_node, review_node
from team_review.demo import make_input
from team_review.tests.test_synthesize import fake_generator, fake_auditor


def selected_web_state():
    state = make_input()
    state["config"]["trl_evidence_policy"] = "selected_implementation"
    state["documents"]["selected-web"] = {
        "title": "Selected implementation qualification", "url": "https://example.invalid/selected",
        "version": "v1", "sha256": "a" * 64, "kind": "web", "retrieved_at": "2026-10-07",
        "source_type": "official_product",
    }
    state["evidence"]["selected-web-1"] = {
        "id": "selected-web-1", "doc_id": "selected-web", "technology_ids": ["HW-01"],
        "excerpt": "Selected HW-01 v1 completed system qualification and sustained field operation.",
        "location": "Qualification and operations", "method": "operational", "verified_source": True,
        "collected_at": "2026-10-07", "technology_relevance": "direct",
        "provenance": {"target_technology_id": "HW-01", "target_version": "v1",
                       "target_identity_verified": True},
    }
    state["assessments"]["technical"]["results"]["HW-01"]["trl_checks"] = {
        n: {"status": "met", "reason": f"Selected implementation supports stage {n}",
            "evidence_ids": ["selected-web-1"]} for n in range(1, 10)
    }
    return state


class SelectedImplementationTRLTests(unittest.TestCase):
    def test_web_evidence_requires_explicit_policy_and_identity(self):
        state = selected_web_state()
        self.assertEqual(review_node(state)["synthesis"]["trl"]["HW-01"]["level"], 9)
        del state["config"]["trl_evidence_policy"]
        self.assertIsNone(review_node(state)["synthesis"]["trl"]["HW-01"]["level"])

    def test_web_evidence_must_match_selected_technology_and_known_version(self):
        for field, value in (("target_technology_id", "SW-01"), ("target_version", "v2"),
                             ("target_version", "unknown"), ("target_identity_verified", False)):
            with self.subTest(field=field, value=value):
                state = selected_web_state()
                state["evidence"]["selected-web-1"]["provenance"][field] = value
                self.assertIsNone(review_node(state)["synthesis"]["trl"]["HW-01"]["level"])
        state = selected_web_state()
        state["config"]["source_reuse"] = True
        state["documents"]["HW-01"]["version"] = "unknown"
        self.assertIsNone(review_node(state)["synthesis"]["trl"]["HW-01"]["level"])

    def test_general_cxl_adjacent_product_and_unavailable_sources_are_rejected(self):
        for update in ({"technology_relevance": "indirect"}, {"technology_relevance": "unknown"},
                       {"verified_source": False}, {"technology_ids": ["SW-01"]}):
            with self.subTest(update=update):
                state = selected_web_state()
                state["evidence"]["selected-web-1"].update(update)
                self.assertIsNone(review_node(state)["synthesis"]["trl"]["HW-01"]["level"])

    def test_selected_web_source_still_needs_operational_stage_evidence(self):
        state = selected_web_state()
        state["evidence"]["selected-web-1"]["method"] = "emulation"
        self.assertEqual(review_node(state)["synthesis"]["trl"]["HW-01"]["level"], 6)

    def test_model_draft_requires_semantic_support_and_is_audited_once(self):
        state = make_input()
        for tech in ("SW-01", "HW-01"):
            state["assessments"]["technical"]["results"][tech]["trl_checks"][1]["generation_method"] = "model"
        self.assertIsNone(review_node(state)["synthesis"]["trl"]["SW-01"]["level"])
        received = []

        def auditor(payload):
            received.append(deepcopy(payload))
            return fake_auditor(payload)

        output = review_handoff_node(state, trl_auditor=auditor)
        self.assertEqual(len(received), 1)
        self.assertEqual({i["item_id"] for i in received[0]["items"]}, {"SW-01/trl/1", "HW-01/trl/1"})
        self.assertEqual(output["synthesis"]["trl"]["SW-01"]["level"], 1)
        self.assertEqual(output["synthesis"]["trl"]["SW-01"]["checks"][0]["semantic_validation_status"], "supported")

    def test_unsupported_or_invalid_semantic_response_cannot_raise_trl(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["trl_checks"][1]["generation_method"] = "model"
        for verdict, ids in (("unsupported", ["DUMMY-SW-01-p1"]), ("uncertain", []),
                             ("supported", ["invented"]), ("supported", [])):
            with self.subTest(verdict=verdict, ids=ids):
                def auditor(payload):
                    return {"checks": [{"item_id": "SW-01/trl/1", "verdict": verdict,
                                        "reason": "test audit", "evidence_ids": ids}]}
                self.assertIsNone(review_node(state, trl_auditor=auditor)["synthesis"]["trl"]["SW-01"]["level"])

    def test_semantic_response_missing_duplicate_and_exception_fail_closed(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["trl_checks"][1]["generation_method"] = "model"
        check = {"item_id": "SW-01/trl/1", "verdict": "supported", "reason": "audit test",
                 "evidence_ids": ["DUMMY-SW-01-p1"]}
        for response in ({"checks": []}, {"checks": [check, check]}, {"checks": [{**check, "item_id": "HW-01/trl/1"}]}):
            with self.subTest(response=response):
                output = review_node(state, trl_auditor=lambda _: response)
                self.assertIsNone(output["synthesis"]["trl"]["SW-01"]["level"])
        def broken(_):
            raise RuntimeError("private external error")
        output = review_node(state, trl_auditor=broken)
        self.assertIsNone(output["synthesis"]["trl"]["SW-01"]["level"])
        self.assertNotIn("private external error", json.dumps(output))

    def test_semantic_gap_reaches_report_without_requesting_role_repair(self):
        for fifth, sixth in (("unsupported", "unsupported"), ("uncertain", "uncertain"),
                             ("unsupported", "supported"), ("unknown", "supported")):
            with self.subTest(fifth=fifth, sixth=sixth):
                state = make_input()
                for tech in ("SW-01", "HW-01"):
                    checks = state["assessments"]["technical"]["results"][tech]["trl_checks"]
                    for n in range(1, 7):
                        checks[n] = {"status": "met", "reason": f"stage {n} draft",
                                     "evidence_ids": [f"DUMMY-{tech}-p1"], "generation_method": "model"}
                if fifth == "unknown":
                    state["assessments"]["technical"]["results"]["HW-01"]["trl_checks"][5].update(
                        status="unknown", evidence_ids=[], reason="stage support incomplete")

                def auditor(payload):
                    results = []
                    for item in payload["items"]:
                        verdict = ({5: fifth, 6: sixth}.get(item["level"], "supported")
                                   if item["technology_id"] == "HW-01" else "supported")
                        results.append({"item_id": item["item_id"], "verdict": verdict,
                                        "reason": "stage support incomplete" if verdict != "supported" else "test support",
                                        "evidence_ids": list(item["evidence"]) if verdict != "uncertain" else []})
                    return {"checks": results}

                output = review_agent_node(state, fake_generator, fake_auditor, trl_auditor=auditor)
                self.assertEqual(output["review"]["next"], "render")
                self.assertEqual(output["review"]["dirty_roles"], [])
                self.assertEqual(output["review"]["status"], "partial")
                self.assertEqual(output["synthesis"]["trl"]["SW-01"]["level"], 6)
                self.assertEqual(output["synthesis"]["trl"]["HW-01"]["level"], 4)
                pending = output["synthesis"]["trl"]["HW-01"]["next_unconfirmed"]
                self.assertEqual((pending["level"], pending["status"]), (5, "unknown"))
                self.assertEqual(pending["reason"], "stage support incomplete")
                header, _ = read_report_input(output["report_input_md"])
                self.assertEqual(header["report_generation"], "allowed_with_gaps")

    def test_semantic_checker_failure_keeps_repair_and_unknown_diagnostic(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["trl_checks"][1]["generation_method"] = "model"
        def broken(_):
            raise RuntimeError("private failure")
        output = review_agent_node(state, fake_generator, fake_auditor, trl_auditor=broken)
        self.assertEqual(output["review"]["next"], "repair")
        pending = output["synthesis"]["trl"]["SW-01"]["next_unconfirmed"]
        self.assertEqual(pending["semantic_validation_status"], "failed")
        self.assertEqual(pending["status"], "unknown")
        self.assertTrue(any(check["code"] == "trl_semantic" for check in output["review"]["checks"]))
        self.assertNotIn("private failure", output["report_input_md"])
        header, _ = read_report_input(output["report_input_md"], require_allowed=False)
        self.assertEqual(header["report_generation"], "blocked")

    def test_non_trl_citation_error_still_requests_repair(self):
        state = make_input()
        state["assessments"]["technical"]["results"]["SW-01"]["items"][0]["evidence_ids"] = ["invented"]
        output = review_node(state)
        self.assertEqual(output["review"]["next"], "repair")
        self.assertIn("technical", output["review"]["dirty_roles"])

    def test_provided_jump_after_model_semantic_gap_still_requests_repair(self):
        for verdict in ("unsupported", "uncertain"):
            with self.subTest(verdict=verdict):
                state = make_input()
                checks = state["assessments"]["technical"]["results"]["HW-01"]["trl_checks"]
                for n in range(1, 7):
                    checks[n] = {"status": "met", "reason": f"provided stage {n}",
                                 "evidence_ids": ["DUMMY-HW-01-p1"]}
                checks[5]["generation_method"] = "model"
                def auditor(_):
                    return {"checks": [{"item_id": "HW-01/trl/5", "verdict": verdict,
                                        "reason": "stage support incomplete", "evidence_ids": []}]}
                output = review_node(state, trl_auditor=auditor)
                self.assertEqual(output["synthesis"]["trl"]["HW-01"]["level"], 4)
                self.assertEqual(output["review"]["next"], "repair")
                gap = next(check for check in output["review"]["checks"] if check["code"] == "trl_gap")
                self.assertTrue(gap["repairable"])
                semantic = next(check for check in output["review"]["checks"] if check["code"] == "trl_semantic")
                self.assertFalse(semantic["repairable"])

    def test_discarded_failed_or_stale_role_does_not_call_semantic_checker(self):
        for failed in (True, False):
            with self.subTest(failed=failed):
                state = make_input()
                state["assessments"]["technical"]["results"]["SW-01"]["trl_checks"][1]["generation_method"] = "model"
                if failed:
                    state["assessments"]["technical"]["status"] = "failed"
                else:
                    state["review"] = {"round": 1, "dirty_roles": ["technical"]}
                received = []
                review_node(state, trl_auditor=lambda payload: received.append(payload))
                self.assertEqual(received, [])


class TRLHandoffTests(unittest.TestCase):
    def test_evidence_index_preserves_technology_ownership(self):
        state = selected_web_state()
        state["evidence"]["selected-web-1"]["technology_ids"] = ["SW-01", "HW-01"]
        body = review_handoff_node(state)["report_input_md"]
        entry = body.split("### [selected-web-1]\n", 1)[1].split("## 10.", 1)[0]
        self.assertIn("- 관련 기술: SW-01 / HW-01", entry)
        self.assertIn("- 해당 기술과의 관련성: direct", entry)

    def test_handoff_preserves_final_trl_json_and_team_estimate(self):
        output = review_handoff_node(selected_web_state())
        body = output["report_input_md"]
        raw = body.split("<!-- REVIEW_TRL_JSON\n", 1)[1].split("\nEND_REVIEW_TRL_JSON -->", 1)[0]
        self.assertEqual(json.loads(raw), output["synthesis"]["trl"])
        self.assertIn("공개 정보 기반 팀 추정", body)
        self.assertIn("- 판정 기준 버전: v1", body)
        self.assertEqual(len(json.loads(raw)["HW-01"]["checks"]), 9)

    def test_production_semantic_checker_only_audits_supplied_stages(self):
        from team_review.review import call_trl_grounding
        parsed = SimpleNamespace(model_dump=lambda **_: {"checks": []})
        response = SimpleNamespace(status="completed", output_parsed=parsed)
        with patch("openai.OpenAI") as client:
            client.return_value.__enter__.return_value.responses.parse.return_value = response
            self.assertEqual(call_trl_grounding({"items": []}, model="test-model"), {"checks": []})
            args = client.return_value.__enter__.return_value.responses.parse.call_args.kwargs
            self.assertIn("최종 TRL 숫자를 계산하지 않는다", args["instructions"])
            self.assertEqual(json.loads(args["input"]), {"items": []})
            self.assertFalse(args["store"])
            self.assertEqual(client.call_args.kwargs["max_retries"], 0)

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
