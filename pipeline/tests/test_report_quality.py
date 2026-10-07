"""Offline quality contracts; model and PDF extraction boundaries are controlled."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from pipeline.report_quality import evaluate_report

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "report/tests/fixtures"


def payload(prompt):
    match = re.search(r"---QUALITY_DATA_[0-9a-f]{16}---\n([\s\S]*?)\n---END_QUALITY_DATA_", prompt)
    return json.loads(match.group(1))


def canonical():
    return {"documents": {"SW-01": {"sha256": "a" * 64, "citation_key": "SW01_RDKV"}},
            "evidence": {"SW-laboratory": {"id": "SW-laboratory", "doc_id": "SW-01",
                "technology_ids": ["SW-01"], "excerpt": "The authors report laboratory GPU experiments.",
                "page": 1, "location": "Results", "method": "GPU experiment",
                "provenance": {"source_hash": "a" * 64}}}}


class ReportQualityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.tex = self.output / "report.tex"
        self.tex.write_text((FIXTURES / "trl-runtime.tex").read_text())
        self.pdf = self.output / "report.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\noffline boundary")
        self.markdown = (FIXTURES / "trl-runtime.input.md").read_text()
        self.blocks = [{"block_id": "p001-b001", "page": 1, "text": "SUMMARY: RDKV GPU 실험 보고 [1]. 추정 TRL: 4. Photonic-CXL 추정 TRL: 미확인."},
                       {"block_id": "p001-b002", "page": 1, "text": "표: 실운영 채택은 미확인이다."}]
        self.calls = []

    def responder(self, instructions, prompt):
        data = payload(prompt)
        self.calls.append(data)
        if data["phase"] == "atomize":
            return {"blocks": [{"block_id": block["block_id"], "non_claim_reason": "",
                "claims": [{"report_quote": block["text"], "text": block["text"],
                    "kind": "author_report" if block["block_id"].endswith("001") else "gap",
                    "technology_ids": ["SW-01"], "citation_keys": ["SW01_RDKV"], "core": True}]}
                for block in data["blocks"]]}
        if data["phase"] == "audit":
            return {"checks": [{"claim_id": claim["claim_id"], "verdict": "supported",
                "reason": "원문의 저자 보고 범위를 보존함", "evidence_ids": ["SW-laboratory"],
                "supporting_quotes": [{"evidence_id": "SW-laboratory",
                    "quote": "The authors report laboratory GPU experiments."}],
                "target": "report", "role": None, "criterion_ids": []}
                for claim in data["claims"]]}
        return {"axes": {name: {"score": 4, "reason": "조건·공백을 보존", "claim_ids": data["claim_ids"]}
                         for name in ("groundedness", "neutrality", "bias_control", "perspective_coverage")},
                "block_coverage": [{"block_id": block["block_id"], "complete": True} for block in data["blocks"]],
                "critical_fact_errors": [], "untraced_core_claims": [], "recommendations": [],
                "missing_perspectives": [], "findings": [],
                "market_coverage": [{"technology_id": tech, "criterion_id": criterion,
                    "analysis_present": True, "gap_handled": False,
                    "report_quote": data["blocks"][0]["text"], "claim_ids": data["claim_ids"]}
                    for tech in ("SW-01", "HW-01") for criterion in (
                        "market_size_growth", "commercialization", "adoption", "ecosystem_support",
                        "standardization", "business_value")]}

    def evaluate(self, responder=None, **changes):
        with patch("pipeline.report_quality.extract_pdf", return_value=(1, self.blocks)):
            return evaluate_report(tex_path=self.tex, pdf_path=self.pdf, review_input=canonical(),
                report_markdown=self.markdown, model="offline-judge", output_dir=self.output,
                responder=responder or self.responder, **changes)

    def test_all_rendered_blocks_and_original_quotes_are_judged(self):
        result = self.evaluate()
        self.assertEqual(result["route"], "passed")
        self.assertEqual(result["weighted_score"], 80)
        self.assertEqual(result["checked_blocks"], {"total": 2, "checked": 2})
        self.assertEqual(result["checked_claims"]["total"], 2)
        audit = next(call for call in self.calls if call["phase"] == "audit")
        self.assertEqual(audit["evidence"][0]["excerpt"], canonical()["evidence"]["SW-laboratory"]["excerpt"])
        self.assertTrue((self.output / "quality.json").exists())

    def test_timeout_never_passes(self):
        def timeout(*args):
            raise TimeoutError("offline timeout")
        result = self.evaluate(timeout)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["failure_type"], "judge_timeout")

    def test_missing_block_and_unparsed_responses_never_pass(self):
        for response in ({"blocks": []}, "not json"):
            result = self.evaluate(lambda *args: response)
            self.assertEqual(result["route"], "review_required")

    def test_axis_floor_is_required_even_when_weighted_score_is_high(self):
        def responder(instructions, prompt):
            data = payload(prompt)
            answer = self.responder(instructions, prompt)
            if data["phase"] == "rubric":
                for axis in answer["axes"].values():
                    axis["score"] = 5
                answer["axes"]["neutrality"]["score"] = 3
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["weighted_score"], 92)
        self.assertEqual(result["route"], "report_repair")

    def test_fabricated_quote_and_wrong_source_identity_never_pass(self):
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "audit":
                answer["checks"][0]["supporting_quotes"][0]["quote"] = "Commercial deployment verified."
            return answer
        result = self.evaluate(responder)
        self.assertNotEqual(result["route"], "passed")
        self.assertEqual(result["failure_type"], "judge_contract_invalid")

    def test_page_limit_fails_before_judge_spending(self):
        with patch("pipeline.report_quality.extract_pdf", return_value=(11, self.blocks)):
            result = evaluate_report(tex_path=self.tex, pdf_path=self.pdf, review_input=canonical(),
                report_markdown=self.markdown, model="offline", output_dir=self.output, responder=self.responder)
        self.assertEqual(result["route"], "report_repair")
        self.assertEqual(self.calls, [])

    def test_changed_rendered_pdf_trl_fails_even_with_valid_tex(self):
        self.blocks[0]["text"] = self.blocks[0]["text"].replace("추정 TRL: 4", "추정 TRL: 9")
        result = self.evaluate()
        self.assertEqual(result["route"], "report_repair")
        self.assertEqual(self.calls, [])

    def test_uncovered_summary_or_table_is_not_a_completed_evaluation(self):
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "rubric":
                answer["block_coverage"][1]["complete"] = False
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")

    def test_unverified_document_hash_is_not_accepted(self):
        evidence = canonical()
        evidence["documents"]["SW-01"]["sha256"] = "b" * 64
        with patch("pipeline.tests.test_report_quality.canonical", return_value=evidence):
            result = self.evaluate()
        self.assertEqual(result["route"], "review_required")

    def test_scoped_missing_core_evidence_requests_upstream(self):
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "audit":
                check = answer["checks"][0]
                check.update(verdict="uncertain", evidence_ids=[], supporting_quotes=[],
                             target="upstream", role="market", criterion_ids=["standardization"])
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "upstream_replan")
        self.assertEqual(result["repair_requests"][0]["criterion_ids"], ["standardization"])

    def test_report_revision_hash_change_invalidates_quality(self):
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "rubric":
                self.tex.write_text(self.tex.read_text() + "\n% changed revision")
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")

    def test_claims_and_original_quotes_are_not_silently_truncated_at_limits(self):
        result = self.evaluate(max_evidence_chars=30)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["failure_type"], "judge_contract_invalid")

    def test_unrelated_fact_line_cannot_disappear_inside_a_checked_page(self):
        self.blocks[0]["text"] += "\n추가 사실: 실제로 채택한 기업이 있다."
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "atomize":
                answer["blocks"] = [row for row in answer["blocks"] if not row["block_id"].endswith("-u002")]
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")

    def test_each_market_criterion_for_each_technology_must_be_checked(self):
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "rubric":
                answer["market_coverage"] = answer["market_coverage"][:-1]
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")

    def test_wrapped_units_keep_paragraph_citation_and_context_in_audit(self):
        self.blocks[0]["text"] += "\nRDKV 검증은 시뮬레이션으로\n수행되었으며 실제 운용 검증은 아니다 [1]."
        captured_instructions = []
        def responder(instructions, prompt):
            captured_instructions.append(prompt)
            return self.responder(instructions, prompt)
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "passed")
        atomize = next(call for call in self.calls if call["phase"] == "atomize")
        audit = next(call for call in self.calls if call["phase"] == "audit")
        self.assertEqual(audit["page_context"], atomize["page_context"])
        self.assertIn("실제 운용 검증은 아니다", audit["page_context"][0]["text"])
        self.assertTrue(any("SINGLE supplied line unit" in prompt for prompt in captured_instructions))
        self.assertTrue(any("same assertion's owning paragraph" in prompt for prompt in captured_instructions))
        self.assertTrue(all("parent_block_id" in claim for claim in audit["claims"]))

    def test_quote_spanning_wrapped_lines_is_rejected_without_normalization(self):
        self.blocks[0]["text"] += "\nRDKV 검증은 시뮬레이션으로\n수행되었으며 실제 운용 검증은 아니다 [1]."
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "atomize":
                answer["blocks"][0]["claims"][0]["report_quote"] = "RDKV 검증은 시뮬레이션으로\n수행되었으며 실제 운용 검증은 아니다 [1]."
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["failure_type"], "judge_contract_invalid")

    def test_cited_claim_batches_keep_large_sources_full_without_repeating_unrelated_sources(self):
        evidence = canonical()
        evidence["documents"]["market-web"] = {"sha256": "b" * 64, "citation_key": "WEB_OTHER"}
        original = "Contrary market evidence. " + "x" * 265_407
        evidence["evidence"]["market-original"] = {"id": "market-original", "doc_id": "market-web",
            "technology_ids": ["SW-01"], "excerpt": original, "location": "Original web body",
            "provenance": {"source_hash": "b" * 64}}
        with patch("pipeline.tests.test_report_quality.canonical", return_value=evidence):
            result = self.evaluate()
        self.assertEqual(result["route"], "passed")
        audits = [call for call in self.calls if call["phase"] == "audit"]
        self.assertEqual(len(audits), 1)
        self.assertEqual([source["evidence_id"] for source in audits[0]["evidence"]], ["SW-laboratory"])
        rubric = next(call for call in self.calls if call["phase"] == "rubric")
        self.assertEqual(next(source for source in rubric["evidence"] if source["evidence_id"] == "market-original")["excerpt"], original)
        plan = json.loads(Path(result["input_plan_path"]).read_text())
        self.assertEqual(plan["canonical_evidence_count"], 2)
        self.assertEqual(plan["calls"][-1]["evidence_count"], 2)
        self.assertGreater(plan["calls"][-1]["input_utf8_bytes"], len(original))

    def test_compound_citations_are_audited_together_with_complete_owned_originals(self):
        evidence = canonical()
        evidence["documents"]["HW-01"] = {"sha256": "b" * 64, "citation_key": "HW01_PHOTONIC_CXL"}
        evidence["evidence"]["HW-laboratory"] = {"id": "HW-laboratory", "doc_id": "HW-01",
            "technology_ids": ["HW-01"], "excerpt": "The HW authors report simulation only.",
            "page": 2, "provenance": {"source_hash": "b" * 64}}
        def responder(instructions, prompt):
            data = payload(prompt)
            answer = self.responder(instructions, prompt)
            if data["phase"] == "atomize":
                for row in answer["blocks"]:
                    row["claims"][0].update(citation_keys=["SW01_RDKV", "HW01_PHOTONIC_CXL"],
                                            technology_ids=["SW-01", "HW-01"])
            if data["phase"] == "audit":
                self.assertEqual({source["doc_id"] for source in data["evidence"]}, {"SW-01", "HW-01"})
                for check in answer["checks"]:
                    check["evidence_ids"].append("HW-laboratory")
                    check["supporting_quotes"].append({"evidence_id": "HW-laboratory",
                        "quote": "The HW authors report simulation only."})
            return answer
        with patch("pipeline.tests.test_report_quality.canonical", return_value=evidence):
            result = self.evaluate(responder)
        self.assertEqual(result["route"], "passed")
        self.assertEqual(len([call for call in self.calls if call["phase"] == "audit"]), 1)

    def test_uncited_claims_receive_every_original_and_missing_cited_document_fails_closed(self):
        def uncited(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "atomize":
                for row in answer["blocks"]:
                    row["claims"][0]["citation_keys"] = []
            return answer
        result = self.evaluate(uncited)
        self.assertEqual(result["route"], "report_repair")
        self.assertEqual(result["gates"]["H2"]["status"], "fail")
        self.assertTrue(any(finding["type"] == "uncited_core_fact" and finding["target"] == "report"
                            for finding in result["findings"]))
        audit = next(call for call in self.calls if call["phase"] == "audit")
        self.assertEqual(audit["evidence_scope"]["selection"], "all_originals_uncited")
        self.assertEqual(len(audit["evidence"]), len(canonical()["evidence"]))
        self.calls.clear()
        def missing(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "atomize":
                for row in answer["blocks"]:
                    row["claims"][0]["citation_keys"] = ["HW01_PHOTONIC_CXL"]
            return answer
        result = self.evaluate(missing)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["failure_type"], "judge_contract_invalid")
        self.assertFalse(any(call["phase"] == "audit" for call in self.calls))

    def test_budget_failure_preserves_input_byte_plan_without_pass_or_retry(self):
        class BudgetExceeded(RuntimeError): pass
        calls = []
        def responder(*args):
            calls.append(args)
            raise BudgetExceeded("offline byte reservation exhausted")
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["failure_type"], "budget_exhausted")
        plan = json.loads(Path(result["input_plan_path"]).read_text())
        self.assertEqual(len(plan["calls"]), 1)
        self.assertEqual(plan["calls"][0]["input_utf8_bytes"], len(calls[0][1].encode()))
        self.assertGreater(plan["planned_input_utf8_bytes"], plan["calls"][0]["input_utf8_bytes"])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
