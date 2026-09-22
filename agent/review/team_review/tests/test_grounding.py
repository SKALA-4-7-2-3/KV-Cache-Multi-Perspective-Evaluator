"""판정 스텁으로 제어 흐름·실패 차단을 검증. 모델 정확도 평가는 별도."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from team_review import read_report_input, review_agent_node, review_handoff_node, route_to_report
from team_review.demo import make_input
from team_review.grounding import audit_payload, is_validated, validate_audit
from team_review.synthesize import synthesis_payload
from team_review.tests.test_synthesize import fake_generator, fake_auditor


class GroundingTests(unittest.TestCase):
    def test_rule_guard_repairs_actual_misinterpretation_even_if_judge_would_pass(self):
        requests = []
        def generator(payload):
            requests.append(payload)
            candidate = fake_generator(payload)
            if "repair" not in payload:
                candidate["opinions"][0]["explanation"] = "이해관계자 관점에서 운영자와 개발자가 품질 변화와 검증 부담을 인지한다."
                candidate["opinions"][0]["risks"] = ["실제 서비스 환경 검증 미완료"]
                candidate["opinions"][0]["rd_kv_conditions"] = ["품질 허용치 미확인 상태"]
            return candidate
        output = review_agent_node(make_input(), generator, fake_auditor)
        value = output["synthesis"]["integrated"]
        self.assertTrue(is_validated(value))
        self.assertEqual(value["semantic_validation"]["attempts"][0]["status"], "rule_rejected")
        self.assertEqual(len(requests[1]["repair"]["issues"]), 3)
        self.assertEqual(value["validation_calls"], 1)
        self.assertNotIn("인지한다", output["report_input_md"])

    def test_repeated_rule_failure_cannot_be_overridden_by_audit(self):
        def generator(payload):
            candidate = fake_generator(payload)
            candidate["opinions"][0]["explanation"] = "고객이 비용 부담을 인지한다."
            return candidate
        with patch("team_review.synthesize.call_grounding") as audit:
            output = review_agent_node(make_input(), generator, fake_auditor)
        audit.assert_not_called()
        value = output["synthesis"]["integrated"]
        self.assertEqual(value["generation_calls"], 2)
        self.assertEqual(value["validation_calls"], 0)
        self.assertEqual(value["status"], "failed")

    def test_missing_tradeoff_and_conflated_mechanisms_are_rejected(self):
        from team_review import review_node
        from team_review.grounding import conservative_issues
        state = make_input()
        source = synthesis_payload(state, review_node(state))
        candidate = fake_generator(source)
        next(o for o in candidate["opinions"] if o["kind"] == "tension")["conclusion"] = "도입 위험과 통합 부담이 상충한다."
        agreement = next(o for o in candidate["opinions"] if o["kind"] == "agreement")
        agreement["explanation"] = "두 기술 모두 메모리 용량 확장이라는 공통 방식을 사용한다."
        issues = conservative_issues(audit_payload(candidate, source))
        self.assertEqual(len(issues), 2)

    def test_unknown_promoted_to_absence_is_repaired_and_rechecked(self):
        requests = []

        def generator(payload):
            requests.append(deepcopy(payload))
            result = fake_generator(payload)
            result["opinions"][0]["conclusion"] = (
                "제공된 자료에서는 상용 배포 여부를 확인하지 못했다."
                if "repair" in payload else "상용 배포된 사례는 없다.")
            return result

        def auditor(payload):
            result = fake_auditor(payload)
            if payload["items"][0]["content"]["conclusion"] == "상용 배포된 사례는 없다.":
                result["checks"][0].update(verdict="unsupported", reason="미확인을 실제 부재로 바꿈. 자료 범위로 한정하세요.")
            return result

        out = review_agent_node(make_input(), generator, auditor)
        value = out["synthesis"]["integrated"]
        self.assertTrue(is_validated(value))
        self.assertEqual((value["generation_calls"], value["validation_calls"], value["repair_attempts"]), (2, 2, 1))
        self.assertEqual(len(requests), 2)
        self.assertIn("미확인을 실제 부재", requests[1]["repair"]["issues"][0]["reason"])
        self.assertNotIn("상용 배포된 사례는 없다.", out["report_input_md"])
        read_report_input(out["report_input_md"])

    def test_repeated_rejection_or_uncertainty_never_reaches_report(self):
        for verdict in ("unsupported", "uncertain"):
            with self.subTest(verdict=verdict):
                def reject(payload):
                    result = fake_auditor(payload)
                    result["checks"][0].update(verdict=verdict, reason="이 문장은 지지되지 않음")
                    return result
                state = make_input()
                output = review_agent_node(state, fake_generator, reject)
                integrated = output["synthesis"]["integrated"]
                self.assertEqual(integrated["status"], "failed")
                self.assertEqual(integrated["opinions"], [])
                self.assertEqual(integrated["generation_calls"] + integrated["validation_calls"], 4)
                self.assertNotIn("[DUMMY 종합]", output["report_input_md"])
                self.assertEqual(route_to_report({**state, **output}), "diagnostic")
                with self.assertRaises(ValueError):
                    read_report_input(output["report_input_md"])

    def test_audit_missing_duplicate_unrelated_citation_and_error_fail_closed(self):
        for failure in ("missing", "duplicate", "citation", "exception"):
            with self.subTest(failure=failure):
                def broken(payload):
                    result = fake_auditor(payload)
                    if failure == "missing":
                        result["checks"].pop()
                    elif failure == "duplicate":
                        result["checks"].append(result["checks"][0])
                    elif failure == "citation":
                        result["checks"][0]["evidence_ids"] = ["not-in-scope"]
                    else:
                        raise RuntimeError("SECRET-do-not-export")
                    return result
                output = review_agent_node(make_input(), fake_generator, broken)
                self.assertEqual(output["synthesis"]["integrated"]["semantic_validation"]["status"], "failed")
                self.assertEqual(output["synthesis"]["integrated"]["generation_calls"], 1)
                self.assertNotIn("SECRET-do-not-export", output["report_input_md"])
                with self.assertRaises(ValueError):
                    read_report_input(output["report_input_md"])

    def test_each_opinion_has_only_its_assigned_evidence(self):
        from team_review import review_node
        state = make_input()
        source = synthesis_payload(state, review_node(state))
        candidate = fake_generator(source)
        payload = audit_payload(candidate, source)
        for item, opinion in zip(payload["items"], candidate["opinions"]):
            self.assertEqual(set(item["evidence"]), set(opinion["evidence_ids"]))
            self.assertEqual({a["assessment_id"] for a in item["assessments"]}, set(opinion["source_assessment_ids"]))
        audit = fake_auditor(payload)
        audit["checks"][0]["evidence_ids"] = []
        with self.assertRaises(ValueError):
            validate_audit(audit, payload)

    def test_injected_generator_cannot_silently_bypass_audit(self):
        with patch("team_review.synthesize.call_grounding") as api:
            output = review_agent_node(make_input(), fake_generator)
        api.assert_not_called()
        self.assertEqual(output["synthesis"]["integrated"]["status"], "failed")

    def test_real_mode_call_budget_is_two_or_four(self):
        for reject_first in (False, True):
            counter = []
            def check(payload, **_):
                result = fake_auditor(payload)
                if reject_first and not counter:
                    result["checks"][0].update(verdict="unsupported", reason="수정 필요")
                counter.append(1)
                return result
            with patch("team_review.synthesize.call_openai", side_effect=lambda p, **_: fake_generator(p)), \
                 patch("team_review.synthesize.call_grounding", side_effect=check):
                output = review_agent_node(make_input())
            self.assertEqual(output["synthesis"]["integrated"]["api_calls"], 4 if reject_first else 2)

    def test_old_unchecked_md_is_diagnostic_only(self):
        output = review_handoff_node(make_input())
        header, _ = read_report_input(output["report_input_md"], require_allowed=False)
        self.assertEqual(header["semantic_validation_status"], "not_run")
        self.assertEqual(header["report_generation"], "blocked")

    def test_editing_validation_or_opinions_invalidates_seal(self):
        integrated = review_agent_node(make_input(), fake_generator, fake_auditor)["synthesis"]["integrated"]
        for kind in ("opinion", "check", "version"):
            value = deepcopy(integrated)
            if kind == "opinion":
                value["opinions"][0]["conclusion"] = "뒤에서 바꾼 문장"
            elif kind == "check":
                value["semantic_validation"]["checks"][0]["reason"] = "뒤에서 바꾼 검사"
            else:
                value["semantic_validation"]["version"] = "old-version"
            self.assertFalse(is_validated(value))

    def test_prompt_version_change_invalidates_cached_success(self):
        from team_review.synthesize import synthesize
        from team_review import review_node
        state = make_input()
        state.update(review_agent_node(state, fake_generator, fake_auditor))
        with patch("team_review.synthesize.AUDIT_VERSION", "grounding-test-new"):
            out = synthesize(state, review_node(state), fake_generator, fake_auditor)
        self.assertFalse(out["cache_reused"])
        self.assertEqual(out["validation_calls"], 1)
