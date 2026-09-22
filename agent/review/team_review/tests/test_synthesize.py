import unittest
from copy import deepcopy
from unittest.mock import patch

from team_review import review_agent_node, review_node, read_report_input
from team_review.demo import make_input
from team_review.synthesize import synthesize, validate_opinions, synthesis_payload, ModelSynthesis
from team_review.contract import REQUIREMENTS


def fake_generator(payload):
    """반환 형식만 시험하는 명시적 더미. 실제 의미 추론/모델 실행 아님."""
    opinions = []
    for tech in ("SW-01", "HW-01"):
        ids = [f"market/{tech}/cost", f"stakeholders/{tech}/developers", f"domain/{tech}/domain_fit"]
        evidence = sorted({e for a in payload["assessments"] if a["assessment_id"] in ids for e in a["evidence_ids"]})
        opinions.append(dict(kind="opinion", technology_ids=[tech], conclusion=f"[DUMMY 종합] {tech} 도입 가치는 편익과 검증·통합 부담을 함께 볼 때 판단할 수 있다.",
                             explanation="[DUMMY] 세 관점을 연결하는 형식 시험", source_assessment_ids=ids, evidence_ids=evidence,
                             conditions=["가상 환경"], risks=["통합 부담"], unknowns=["실제 비용"], confidence="low", basis="inference",
                             recommendation=False, absolute_ranking=False, rd_kv_conditions=[], photonic_cxl_conditions=[], undecidable_conditions=[]))
    originals = deepcopy(opinions)
    for original in originals:
        opinions.append({**original, "kind": "tension", "conclusion": "[DUMMY 상충] 편익과 통합 부담은 함께 검토해야 한다."})
    for kind in ("agreement", "conditional", "joint"):
        opinions.append({**originals[0], "kind": kind, "technology_ids": ["SW-01", "HW-01"],
                         "conclusion": f"[DUMMY {kind}] 두 기술의 조건을 연결한 형식 검사용 문장.",
                         "source_assessment_ids": sum((o["source_assessment_ids"] for o in originals), []),
                         "evidence_ids": sorted({e for o in originals for e in o["evidence_ids"]})})
    return {"opinions": opinions, "unresolved_relations": [], "limitations": ["DUMMY 결과이며 모델 실행 아님"]}


def fake_auditor(payload):
    """통합 테스트용 검사 스텁. 실제 의미 판단의 정확성을 증명하지 않는다."""
    return {"checks": [{"item_id": i["item_id"], "verdict": "supported", "reason": "DUMMY 검사 응답",
                        "evidence_ids": list(i["evidence"])[:1]} for i in payload["items"]]}


class SynthesisTests(unittest.TestCase):
    def test_model_dedicated_fields_keep_existing_flat_contract(self):
        state = make_input()
        payload = synthesis_payload(state, review_node(state))
        raw = fake_generator(payload)
        opinions = [{k: v for k, v in o.items() if k not in ("evidence_ids", "kind", "technology_ids", "source_assessment_ids")} for o in raw["opinions"]]
        structured = dict(rdkv_opinion=opinions[0], photonic_cxl_opinion=opinions[1], agreement=opinions[4],
                          rdkv_tension=opinions[2], photonic_cxl_tension=opinions[3],
                          conditional=opinions[5], joint=opinions[6], limitations=[])
        flat = ModelSynthesis.model_validate(structured).flatten(payload)
        self.assertEqual(len(validate_opinions(flat, payload)["opinions"]), 7)
        self.assertEqual(flat["opinions"][0]["source_assessment_ids"], payload["relation_source_candidates"]["rdkv_opinion"])
        invalid_gap = deepcopy(structured)
        invalid_gap["joint"] = {"kind": "joint", "technology_ids": ["SW-01", "HW-01"], "reason": "출처 없는 의견"}
        with self.assertRaises(ValueError):
            ModelSynthesis.model_validate(invalid_gap)
        invalid = deepcopy(payload)
        invalid["relation_source_candidates"]["rdkv_opinion"].append("market/SW-01/invented")
        with self.assertRaises(ValueError):
            ModelSynthesis.model_validate(structured).flatten(invalid)

    def test_unknown_assessments_are_separate_from_usable_sources(self):
        state = make_input()
        state["assessments"]["market"]["results"]["SW-01"]["items"][0].update(judgment="unknown", gaps=["시장 자료 부족"])
        payload = synthesis_payload(state, review_node(state))
        self.assertTrue(all(a["judgment"] not in ("unknown", "failed") for a in payload["assessments"]))
        self.assertTrue(any(a["assessment_id"] == "market/SW-01/market_size_growth" for a in payload["unconfirmed_assessments"]))

    def test_test_generator_cache_is_not_reused_for_real_api_mode(self):
        state = make_input()
        state.update(review_agent_node(state, fake_generator, fake_auditor))
        with patch("team_review.synthesize.call_openai", side_effect=lambda p, **_: fake_generator(p)) as api, \
             patch("team_review.synthesize.call_grounding", side_effect=lambda p, **_: fake_auditor(p)):
            actual = synthesize(state, review_node(state))
        api.assert_called_once()
        self.assertFalse(actual["cache_reused"])

    def test_complete_only_when_mock_has_no_gaps_and_opinions_complete(self):
        state = make_input()
        state["config"]["domain_requirements"] = {k: "DUMMY 요구값" for k in REQUIREMENTS}
        for evidence in state["evidence"].values():
            evidence.update(independence="third_party", method="operational")
        for role in state["assessments"].values():
            for cell in role["results"].values():
                for item in cell["items"]:
                    item.update(confidence="high", analysis_scope="selected_domain", domain_relevance="direct")
                for check in cell["trl_checks"].values():
                    check.update(status="met", evidence_ids=cell["items"][0]["evidence_ids"])
        output = review_agent_node(state, fake_generator, fake_auditor)
        header, _ = read_report_input(output["report_input_md"])
        self.assertEqual(header["review_status"], "complete")
        self.assertEqual(header["report_generation"], "allowed")

    def test_new_opinions_link_three_roles_for_both_technologies(self):
        state = make_input()
        before = deepcopy(state)
        output = review_agent_node(state, fake_generator, fake_auditor)
        self.assertEqual(state, before)
        integrated = output["synthesis"]["integrated"]
        self.assertEqual(integrated["status"], "completed")
        self.assertEqual(integrated["api_calls"], 0)
        self.assertEqual(len(integrated["opinions"]), 7)
        self.assertIn("새로운 종합 의견", output["report_input_md"])
        self.assertIn("시장", output["report_input_md"])
        read_report_input(output["report_input_md"])

    def test_invented_or_unrelated_evidence_rejected(self):
        state = make_input()
        result = review_node(state)
        payload = synthesis_payload(state, result)
        for eid in ("invented", "DUMMY-HW-01-p1"):
            raw = fake_generator(payload)
            raw["opinions"][0]["evidence_ids"] = [eid]
            with self.assertRaises(ValueError):
                validate_opinions(raw, payload)

    def test_missing_perspective_or_changed_technology_rejected(self):
        state = make_input()
        payload = synthesis_payload(state, review_node(state))
        for kind in ("role", "tech", "copy"):
            raw = fake_generator(payload)
            if kind == "role":
                raw["opinions"][0]["source_assessment_ids"].pop()
            elif kind == "tech":
                raw["opinions"][0]["technology_ids"] = ["HW-01"]
            else:
                raw["opinions"][0]["conclusion"] = next(a["conclusion"] for a in payload["assessments"] if a["assessment_id"] == "market/SW-01/cost")
            with self.assertRaises(ValueError):
                validate_opinions(raw, payload)

    def test_failed_generation_is_not_faked_as_success(self):
        def failed(_):
            raise RuntimeError("secret-do-not-print")
        output = review_agent_node(make_input(), failed, fake_auditor)
        self.assertEqual(output["synthesis"]["integrated"]["status"], "failed")
        self.assertNotIn("secret-do-not-print", output["report_input_md"])
        self.assertNotIn("[DUMMY 종합]", output["report_input_md"])

    def test_missing_relation_cannot_silently_pass(self):
        state = make_input()
        payload = synthesis_payload(state, review_node(state))
        raw = fake_generator(payload)
        raw["opinions"] = [o for o in raw["opinions"] if o["kind"] != "joint"]
        checked = validate_opinions(raw, payload)
        self.assertEqual(checked["unresolved_relations"][0]["kind"], "joint")
        self.assertIn("분석 누락", checked["unresolved_relations"][0]["reason"])
        missing = review_agent_node(state, lambda _: raw, fake_auditor)
        self.assertEqual(missing["synthesis"]["integrated"]["status"], "partial")
        self.assertEqual(len(missing["synthesis"]["integrated"]["opinions"]), 6)
        raw["unresolved_relations"] = [{"kind": "joint", "technology_ids": ["SW-01", "HW-01"],
                                         "reason": "DUMMY: 커넥터 호환 조건을 확인할 자료가 부족함"}]
        validate_opinions(raw, payload)
        output = review_agent_node(state, lambda _: raw, fake_auditor)
        header, body = read_report_input(output["report_input_md"])
        self.assertEqual(header["review_status"], "partial")
        self.assertIn("커넥터 호환 조건", body)

    def test_joint_conclusion_cannot_be_hidden_in_conditional(self):
        state = make_input()
        payload = synthesis_payload(state, review_node(state))
        raw = fake_generator(payload)
        next(o for o in raw["opinions"] if o["kind"] == "conditional")["conclusion"] = "병행 도입이 가능하다."
        with self.assertRaises(ValueError):
            validate_opinions(raw, payload)

    def test_relation_cannot_be_both_resolved_and_pending(self):
        state = make_input()
        payload = synthesis_payload(state, review_node(state))
        raw = fake_generator(payload)
        raw["unresolved_relations"] = [{"kind": "tension", "technology_ids": ["SW-01"], "reason": "불충분"}]
        with self.assertRaises(ValueError):
            validate_opinions(raw, payload)

    def test_cross_technology_conditions_and_cross_perspective_tensions_are_distinct(self):
        state = make_input()
        payload = synthesis_payload(state, review_node(state))
        raw = fake_generator(payload)
        conditional = next(o for o in raw["opinions"] if o["kind"] == "conditional")
        conditional["source_assessment_ids"] = ["domain/SW-01/domain_fit", "domain/HW-01/domain_fit"]
        validate_opinions(raw, payload)
        tension = next(o for o in raw["opinions"] if o["kind"] == "tension")
        tension["source_assessment_ids"] = ["domain/SW-01/quality", "domain/SW-01/deployment"]
        with self.assertRaises(ValueError):
            validate_opinions(raw, payload)

    def test_incomplete_cached_relations_cannot_retain_completed_status(self):
        state = make_input()
        state.update(review_agent_node(state, fake_generator, fake_auditor))
        cached = state["synthesis"]["integrated"]
        cached["opinions"] = [o for o in cached["opinions"] if o["kind"] != "agreement"]
        calls = []
        result = synthesize(state, review_node(state), lambda p: (calls.append(1) or fake_generator(p)), fake_auditor)
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["cache_reused"])
        self.assertEqual(calls, [1])

    def test_blocked_and_repair_inputs_do_not_call_generator(self):
        for case in ("fatal_error", "tool_failure", "bad_citation"):
            calls = []
            output = review_agent_node(make_input(case), lambda _: calls.append(1), fake_auditor)
            self.assertEqual(calls, [])
            self.assertEqual(output["synthesis"]["integrated"]["status"], "skipped")

    def test_same_validated_input_reuses_checkpoint_but_changes_invalidate(self):
        state = make_input()
        state.update(review_agent_node(state, fake_generator, fake_auditor))
        calls = []
        cached = synthesize(state, review_node(state), lambda p: calls.append(1), fake_auditor)
        self.assertTrue(cached["cache_reused"])
        self.assertEqual(calls, [])
        state["config"]["domain_requirements"] = {"quality": "테스트 변경"}
        fresh = synthesize(state, review_node(state), fake_generator, fake_auditor)
        self.assertFalse(fresh["cache_reused"])
