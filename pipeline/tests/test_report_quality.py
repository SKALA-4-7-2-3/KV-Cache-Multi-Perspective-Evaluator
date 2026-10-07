"""Offline quality contracts; model and PDF extraction boundaries are controlled."""
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from pipeline.report_quality import (evaluate_report, canonical_evidence, _audit, JudgeContractError,
                                     _audit_schema, _judge_prompt, _provider, _normalize_provider_answer, JUDGE_INSTRUCTIONS)

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


def schema_accepts(schema, value, root=None):
    """Offline JSON Schema subset evaluator, independent of Judge normalization."""
    root = schema if root is None else root
    if "$ref" in schema:
        target = root
        for key in schema["$ref"].removeprefix("#/").split("/"):
            target = target[key]
        return schema_accepts(target, value, root)
    if "anyOf" in schema and not any(schema_accepts(branch, value, root) for branch in schema["anyOf"]):
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None)}
    if kind in types and type(value) is not types[kind]:
        return False
    if kind == "object":
        properties = schema.get("properties", {})
        if not set(schema.get("required", [])) <= set(value):
            return False
        if schema.get("additionalProperties") is False and not set(value) <= set(properties):
            return False
        return all(schema_accepts(properties[key], item, root) for key, item in value.items() if key in properties)
    if kind == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            return False
        return all(schema_accepts(schema.get("items", {}), item, root) for item in value)
    if kind == "integer":
        return schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf"))
    return True


def raw_audit_checks(answer, data):
    """Convert the explicit offline normalized responder into the provider wire contract."""
    claims = {claim["claim_id"]: claim for claim in data["claims"]}
    sources = {source["evidence_id"]: source for source in data["evidence"]}
    def anchor(row):
        claim = claims[row["claim_id"]]
        return next(({"evidence_id": identifier, "span_index": 0} for identifier in row["evidence_ids"]
                     if (not claim["technology_ids"] or set(claim["technology_ids"]) & set(sources[identifier]["technology_ids"]))
                     and (not claim["citation_keys"] or data["documents"][sources[identifier]["doc_id"]]["citation_key"] in claim["citation_keys"])), None)
    return {"checks": {row["claim_id"]: {**{key: value for key, value in row.items()
        if key not in {"claim_id", "supporting_quotes", "evidence_ids"}},
        "claim_reference": anchor(row),
        "technology_references": {technology: next((
            {"evidence_id": identifier, "span_index": 0} for identifier in row["evidence_ids"]
            if technology in sources[identifier]["technology_ids"]), None)
            for technology in claims[row["claim_id"]]["technology_ids"]},
        "references": [{"evidence_id": identifier, "span_index": 0} for identifier in row["evidence_ids"]]}
        for row in answer["checks"]}}


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
                       {"block_id": "p001-b002", "page": 1, "text": "표: 실운영 채택은 미확인이다 [1]."}]
        self.calls = []

    def responder(self, instructions, prompt):
        data = payload(prompt)
        self.calls.append(data)
        if data["phase"] == "atomize":
            return {"blocks": [{"block_id": block["block_id"], "non_claim_reason": "",
                "claims": [{"report_quote": block["text"], "text": block["text"],
                    "kind": "author_report" if block.get("parent_block_id", block["block_id"]).endswith("001") else "gap",
                    "technology_ids": ["SW-01"], "citation_keys": block.get("paragraph_citation_keys", ["SW01_RDKV"]), "core": True}]}
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
        with patch(__name__ + ".canonical", return_value=evidence):
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

    def test_page_break_preserves_closing_citations_without_borrowing_next_paragraph(self):
        from pipeline.report_quality import rendered_units, bind_rendered_citations
        pages = [
            {"block_id": "p001-b001", "page": 1, "text": "   RDKV 검증 조건은\n페이지에서 이어진다\n\n  1\n"},
            {"block_id": "p002-b001", "page": 2, "text": "다음 페이지의 동일 문단이다 [1,2].\n\n   새 문단의 별도 근거 [3].\n\n  2\n"},
            {"block_id": "p003-b001", "page": 3, "text": "9 REFERENCE\n\n[4] 서지 정보\n\n  3\n"},
        ]
        units = rendered_units(pages)
        bind_rendered_citations(units, {"1": "SW", "2": "HW", "3": "WEB", "4": "REF"})
        self.assertEqual(len(units), 9)  # Includes all three page-number lines.
        self.assertEqual([unit["paragraph_citation_keys"] for unit in units[:2]], [["HW", "SW"]] * 2)
        continued = next(unit for unit in units if unit["text"].startswith("다음"))
        separate = next(unit for unit in units if "새 문단" in unit["text"])
        heading = next(unit for unit in units if unit["text"].startswith("9 REFERENCE"))
        self.assertEqual(continued["paragraph_id"], units[0]["paragraph_id"])
        self.assertEqual(continued["paragraph_citation_keys"], ["HW", "SW"])
        self.assertEqual(separate["paragraph_citation_keys"], ["WEB"])
        self.assertEqual(heading["paragraph_citation_keys"], [])

    def test_new_indented_page_paragraph_does_not_inherit_previous_citation(self):
        from pipeline.report_quality import rendered_units, bind_rendered_citations
        pages = [{"block_id": "p001-b001", "page": 1, "text": "   이전 주장 [1].\n\n 1\n"},
                 {"block_id": "p002-b001", "page": 2, "text": "   새 주장에 근거 없음.\n\n 2\n"}]
        units = rendered_units(pages)
        bind_rendered_citations(units, {"1": "SW"})
        self.assertEqual(units[0]["paragraph_citation_keys"], ["SW"])
        self.assertEqual(units[2]["paragraph_citation_keys"], [])

    def test_adjacent_new_paragraph_and_list_citations_do_not_cover_previous_uncited_fact(self):
        from pipeline.report_quality import rendered_units, bind_rendered_citations
        blocks = [{"block_id": "p001-b001", "page": 1,
            "text": "   SW 상용 채택 주장\n   HW 처리량 주장 [1].\n • 별도 목록 주장 [2].\n[3] 서지\n"}]
        units = rendered_units(blocks)
        bind_rendered_citations(units, {"1": "HW", "2": "WEB", "3": "REF"})
        self.assertEqual([u["paragraph_citation_keys"] for u in units], [[], ["HW"], ["WEB"], ["REF"]])

    def test_unused_paragraph_reference_cannot_make_uncited_core_fact_pass(self):
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "atomize":
                answer["blocks"][0]["claims"][0]["citation_keys"] = []
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "report_repair")
        self.assertGreater(result["checked_claims"]["uncited_facts"], 0)
        self.assertEqual(result["gates"]["H2"]["status"], "fail")
        audit = next(call for call in self.calls if call["phase"] == "audit")
        self.assertEqual(audit["evidence_scope"]["selection"], "all_originals_uncited")

    def test_exact_report_qualification_and_last_page_number_remain_in_denominator(self):
        from pipeline.report_quality import rendered_units, _atomize, _atomize_schema
        blocks = [{"block_id": "p001-b001", "page": 1, "text": (
            "공개 정보 기반 팀 추정이며 공식 인증이 아니다.\n"
            "RDKV는 공식 인증이 아니다.\n1\n다른 본문\n   1\n")}]
        units = rendered_units(blocks)
        self.assertEqual(len(units), 5)
        self.assertEqual([bool(u.get("required_non_claim_reason")) for u in units], [True, False, False, False, True])
        data = {"blocks": units, "citation_numbers": {"1": "SW01_RDKV"}}
        schema = _atomize_schema(data)["properties"]["blocks"]["properties"]
        self.assertEqual(schema[units[0]["block_id"]]["properties"]["claims"]["maxItems"], 0)
        rows = [{"block_id":u["block_id"], "claims":[],
                 "non_claim_reason":u.get("required_non_claim_reason", "offline non-claim")}
                for u in units]
        self.assertEqual(_atomize({"blocks":rows}, units, {"SW01_RDKV"}), [])
        rows[0]["non_claim_reason"] = "Unverified replacement reason"
        with self.assertRaises(JudgeContractError):
            _atomize({"blocks":rows}, units, {"SW01_RDKV"})

    def test_collective_paragraph_references_allow_each_assertions_actual_support(self):
        from pipeline.report_quality import _audit
        data = canonical()
        data["documents"]["other"] = {"sha256": "b" * 64, "citation_key": "WEB_OTHER"}
        data["evidence"]["other"] = {"id": "other", "doc_id": "other", "technology_ids":["SW-01"],
            "excerpt":"Other registered original.", "location":"Body", "provenance":{"source_hash":"b"*64}}
        evidence = canonical_evidence(data)
        claim = {"claim_id":"fixed", "technology_ids":["SW-01"], "citation_keys":["SW01_RDKV", "WEB_OTHER"],
            "rendered_citation_keys":["SW01_RDKV", "WEB_OTHER"]}
        source = next(e for e in evidence if e["evidence_id"] == "SW-laboratory")
        check = {"claim_id":"fixed", "verdict":"supported", "reason":"Original experiment supports this assertion",
            "evidence_ids":[source["evidence_id"]], "supporting_quotes":[{"evidence_id":source["evidence_id"], "quote":source["excerpt"]}],
            "target":"report", "role":None, "criterion_ids":[]}
        self.assertEqual(len(_audit({"checks":[deepcopy(check)]},[claim],evidence,data["documents"])), 1)
        claim["rendered_citation_keys"] = ["WEB_OTHER"]
        with self.assertRaises(JudgeContractError):
            _audit({"checks":[deepcopy(check)]},[claim],evidence,data["documents"])
        claim["rendered_citation_keys"] = ["SW01_RDKV", "WEB_OTHER"]
        claim["citation_keys"] = ["WEB_OTHER"]
        with self.assertRaises(JudgeContractError):
            _audit({"checks":[deepcopy(check)]},[claim],evidence,data["documents"])

    def test_uncited_claim_in_cited_paragraph_still_receives_unrelated_originals(self):
        from pipeline.report_quality import _audit_groups
        sources = [{"evidence_id":"one", "doc_id":"one", "excerpt":"First complete original"},
                   {"evidence_id":"two", "doc_id":"two", "excerpt":"Second complete original"}]
        documents = {"one":{"citation_key":"ONE"}, "two":{"citation_key":"TWO"}}
        claim = {"claim_id":"fixed", "citation_keys":[], "rendered_citation_keys":["ONE"]}
        groups = _audit_groups([claim],sources,documents,10000,10000)
        self.assertEqual(groups[0]["evidence_scope"]["selection"], "all_originals_uncited")
        self.assertEqual(groups[0]["evidence"], sources)

    def test_partial_technology_evidence_can_reject_but_cannot_support_compound_claim(self):
        data = canonical()
        source = canonical_evidence(data)[0]
        claim = {"claim_id":"fixed", "technology_ids":["SW-01","HW-01"], "citation_keys":["SW01_RDKV"]}
        check = {"claim_id":"fixed", "verdict":"unsupported", "reason":"SW evidence does not establish the HW half",
            "evidence_ids":[source["evidence_id"]], "supporting_quotes":[{"evidence_id":source["evidence_id"], "quote":source["excerpt"]}],
            "target":"report", "role":None, "criterion_ids":[]}
        for verdict in ("unsupported", "uncertain", "contradicted"):
            check["verdict"] = verdict
            self.assertEqual(_audit({"checks":[deepcopy(check)]},[claim],[source],data["documents"])[0]["verdict"],verdict)
        check["verdict"] = "supported"
        with self.assertRaises(JudgeContractError):
            _audit({"checks":[check]},[claim],[source],data["documents"])

    def test_failed_later_audit_preserves_only_completed_claim_counts(self):
        def responder(instructions, prompt):
            data = payload(prompt)
            answer = self.responder(instructions, prompt)
            if data["phase"] == "atomize":
                answer["blocks"][1]["claims"][0]["citation_keys"] = []
            if data["phase"] == "audit" and any("b002" in c["claim_id"] for c in data["claims"]):
                raise JudgeContractError("OFFLINE remaining audit rejected")
            return answer
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["checked_claims"]["total"], 2)
        self.assertEqual(result["checked_claims"]["checked"], 1)
        self.assertEqual(result["checked_claims"]["supported"], 1)

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
        with patch(__name__ + ".canonical", return_value=evidence):
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
        for block in self.blocks:
            block["text"] = block["text"].replace("[1]", "[1,2]")
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
        with patch(__name__ + ".canonical", return_value=evidence):
            result = self.evaluate(responder)
        self.assertEqual(result["route"], "passed")
        self.assertEqual(len([call for call in self.calls if call["phase"] == "audit"]), 1)

    def test_uncited_claims_receive_every_original_and_missing_cited_document_fails_closed(self):
        for block in self.blocks:
            block["text"] = block["text"].replace("[1]", "")
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
        for block in self.blocks:
            block["text"] += " [1,2]"
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

    def bridge_web_fixture(self, *, image=False):
        """Real bridge and saved papers; web text/assertions are explicit offline fixtures."""
        from pipeline.research_input import load_saved_research
        from pipeline.review_bridge import build_review_state
        from pipeline.tests.test_orchestration import portable_role
        bundle = load_saved_research(ROOT / "rag/examples/results/technical-bge-e2e-two-papers")
        request = json.loads((ROOT / "config/pipeline.json").read_text())["request"]
        body = ("OFFLINE fixture: the source reports memory pooling. "
                "Contrary original condition: deployment requires fabric validation. "
                "The source does not verify actual adoption.")
        if image:
            body += " ![offline image](data:image/png;base64,AAABBB)"
        market = portable_role("market")
        market["evidence"] = {"web-offline-original": {"id": "web-offline-original",
            "doc_id": "collected-web", "url": "https://example.test/offline-web",
            "title": "OFFLINE web source contract fixture", "technology_ids": ["SW-01"],
            "excerpt": body, "access_status": "full_text", "method": "statement",
            "source_type": "official_product", "collected_content_sha256": sha256(body.encode()).hexdigest()}}
        if not image:
            market["retained_draft_findings"] = [{"supports": [
                {"evidence_id": "web-offline-original", "quote": "the source reports memory pooling."},
                {"evidence_id": "web-offline-original", "quote": "The source does not verify actual adoption."}]}]
        state = build_review_state(bundle, request, {"market": market,
            "domain": portable_role("domain"), "stakeholders": portable_role("stakeholders")},
            run_id="offline-web-quality", as_of="2026-10-07")
        return state, body

    def test_real_bridge_web_projection_preserves_full_counterevidence_and_collected_hash(self):
        state, body = self.bridge_web_fixture()
        source = next(row for row in canonical_evidence(state) if row["evidence_id"] == "web-offline-original")
        registered = state["documents"][source["doc_id"]]
        self.assertIsNone(state["evidence"][source["evidence_id"]]["provenance"].get("source_hash"))
        self.assertNotIn("Contrary original condition:", state["evidence"][source["evidence_id"]]["excerpt"])
        self.assertEqual(source["source_hash"], registered["sha256"])
        self.assertEqual(source["excerpt"], body)
        self.assertEqual(source["method"], state["evidence"][source["evidence_id"]]["method"])
        claim = {"claim_id": "offline-web-claim", "technology_ids": ["SW-01"],
                 "citation_keys": [registered["citation_key"]]}
        quote = "Contrary original condition: deployment requires fabric validation."
        answer = {"checks": [{"claim_id": claim["claim_id"], "verdict": "supported",
            "reason": "OFFLINE contract: exact original condition", "evidence_ids": [source["evidence_id"]],
            "supporting_quotes": [{"evidence_id": source["evidence_id"], "quote": quote}],
            "target": "report", "role": None, "criterion_ids": []}]}
        self.assertEqual(_audit(answer, [claim], [source], state["documents"])[0]["verdict"], "supported")
        broken = deepcopy(state)
        broken["documents"][source["doc_id"]]["sha256"] = "f" * 64
        with self.assertRaises(JudgeContractError):
            canonical_evidence(broken)

    def test_web_original_hash_mismatch_is_rejected_and_sanitized_view_does_not_replace_raw(self):
        state, body = self.bridge_web_fixture()
        state["config"]["usable_source_reports"][0]["excerpt"] += " ALTERED"
        with self.assertRaises(JudgeContractError):
            canonical_evidence(state)
        state, body = self.bridge_web_fixture(image=True)
        report = state["config"]["usable_source_reports"][0]
        self.assertNotEqual(report["excerpt"], body)
        source = next(row for row in canonical_evidence(state) if row["evidence_id"] == "web-offline-original")
        self.assertEqual(source["excerpt"], body)
        self.assertEqual(sha256(source["excerpt"].encode()).hexdigest(), source["source_hash"])

    def test_each_provider_request_input_explicitly_requests_json(self):
        from types import SimpleNamespace
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def create(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(status="completed", output_text='{"offline": true}')
        with patch("pipeline.governance.openai_client", return_value=Client()):
            for phase in ("atomize", "audit", "rubric"):
                prompt = _judge_prompt(phase, {"text": "plain fixture"})
                self.assertIn("Return a JSON object", prompt)
                self.assertGreater(prompt.index("Return a JSON object"), prompt.index("---END_QUALITY_DATA_"))
                _provider("offline-model")(JUDGE_INSTRUCTIONS, prompt)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all("JSON" in call["input"] for call in calls))

    def test_full_source_reports_change_invalidates_checked_canonical_input_hash(self):
        evidence = canonical()
        evidence["config"] = {"usable_source_reports": [{"evidence_id": "offline-unused",
            "reference_id": "offline-doc", "excerpt": "OFFLINE original source input"}]}
        def responder(instructions, prompt):
            answer = self.responder(instructions, prompt)
            if payload(prompt)["phase"] == "rubric":
                evidence["config"]["usable_source_reports"][0]["excerpt"] += " changed after audit"
            return answer
        with patch(__name__ + ".canonical", return_value=evidence):
            result = self.evaluate(responder)
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["gates"]["H6"]["status"], "fail")

    def test_atomize_provider_schema_requires_each_unit_and_registered_ids(self):
        from types import SimpleNamespace
        units = [{"block_id": "p001-b001-u001", "page": 1, "text": "첫 원문 줄 [1].\n"},
                 {"block_id": "p001-b001-u002", "page": 1, "text": "둘째 원문 줄 [2].\n"}]
        data = {"blocks": units, "citation_numbers": {"1": "SW01_RDKV", "2": "HW01_PHOTONIC_CXL"}}
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def create(self, **kwargs):
                calls.append(kwargs)
                answer = {"blocks": {unit["block_id"]: {"non_claim_reason": "", "claims": [{
                    "text": "OFFLINE assertion", "kind": "fact",
                    "technology_ids": ["SW-01"], "citation_keys": [data["citation_numbers"][str(index)]], "core": True}]}
                    for index, unit in enumerate(units, 1)}}
                return SimpleNamespace(status="completed", output_text=json.dumps(answer))
        with patch("pipeline.governance.openai_client", return_value=Client()):
            answer = _provider("offline-model", phase="atomize", data=data)(JUDGE_INSTRUCTIONS, _judge_prompt("atomize", data))
        format = calls[0]["text"]["format"]
        self.assertEqual(format["type"], "json_schema")
        self.assertIs(format["strict"], True)
        schema = format["schema"]
        blocks = schema["properties"]["blocks"]
        self.assertEqual(set(blocks["required"]), {unit["block_id"] for unit in units})
        self.assertIs(blocks["additionalProperties"], False)
        for unit in units:
            branches = blocks["properties"][unit["block_id"]]["anyOf"]
            self.assertEqual(branches[0]["properties"]["claims"]["minItems"], 1)
            self.assertEqual(branches[1]["properties"]["claims"]["maxItems"], 0)
            self.assertEqual(branches[1]["properties"]["non_claim_reason"]["minLength"], 1)
            claim = branches[0]["properties"]["claims"]["items"]
            properties = claim["properties"]
            self.assertNotIn("report_quote", properties)
            self.assertEqual(properties["technology_ids"]["items"]["enum"], ["SW-01", "HW-01"])
            number = str(units.index(unit) + 1)
            self.assertEqual(properties["citation_keys"]["items"]["enum"], [data["citation_numbers"][number]])
            self.assertEqual(set(schema["$defs"]["citation_key"]["enum"]), set(data["citation_numbers"].values()))
        self.assertEqual([row["block_id"] for row in answer["blocks"]], [unit["block_id"] for unit in units])
        self.assertEqual([row["claims"][0]["report_quote"] for row in answer["blocks"]],
                         [unit["text"] for unit in units])

    def test_incomplete_provider_response_never_reaches_atomization(self):
        from types import SimpleNamespace
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def create(self, **kwargs):
                return SimpleNamespace(status="incomplete", output_text='{"blocks": []}')
        with patch("pipeline.governance.openai_client", return_value=Client()):
            with self.assertRaises(JudgeContractError):
                _provider("offline-model")(JUDGE_INSTRUCTIONS, _judge_prompt("audit", {}))

    def test_atomization_batches_at_most_twenty_units_without_losing_units(self):
        self.blocks[0]["text"] += "\n" + "\n".join("추가 원문 줄 " + str(i) for i in range(44))
        result = self.evaluate(max_judge_calls=64)
        self.assertEqual(result["route"], "passed")
        batches = [call["blocks"] for call in self.calls if call["phase"] == "atomize"]
        self.assertTrue(all(len(batch) <= 20 for batch in batches))
        self.assertEqual(sum(len(batch) for batch in batches), result["checked_units"]["total"])
        audits = [call["claims"] for call in self.calls if call["phase"] == "audit"]
        self.assertTrue(all(len(batch) <= 20 for batch in audits))
        self.assertEqual(sum(len(batch) for batch in audits), result["checked_claims"]["total"])

    def test_strict_audit_uses_all_original_spans_and_binds_selected_reference(self):
        from types import SimpleNamespace
        source = canonical_evidence(canonical())[0]
        source["excerpt"] = "A" * 800 + "B" * 800 + "Contrary condition remains original."
        claim = {"claim_id": "fixed-claim", "technology_ids": ["SW-01"], "citation_keys": ["SW01_RDKV"]}
        data = {"claims": [claim], "evidence": [source], "documents": canonical()["documents"]}
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def create(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(status="completed", output_text=json.dumps({"checks": {
                    claim["claim_id"]: {"verdict": "supported", "reason": "OFFLINE original condition",
                        "claim_reference": {"evidence_id": source["evidence_id"], "span_index": 2},
                        "technology_references": {"SW-01": {"evidence_id": source["evidence_id"], "span_index": 2}},
                        "references": [{"evidence_id": source["evidence_id"], "span_index": 2}],
                        "target": "report", "role": None, "criterion_ids": []}}}))
        with patch("pipeline.governance.openai_client", return_value=Client()):
            answer = _provider("offline-model", phase="audit", data=data)(JUDGE_INSTRUCTIONS, _judge_prompt("audit", data))
        format = calls[0]["text"]["format"]
        self.assertEqual(format["type"], "json_schema")
        self.assertEqual(format["schema"]["properties"]["checks"]["required"], [claim["claim_id"]])
        self.assertEqual(format["schema"]["$defs"]["source_reference"]["anyOf"], [{"$ref": "#/$defs/source_0"}])
        reference = format["schema"]["$defs"]["source_0"]["properties"]
        self.assertEqual(reference["evidence_id"]["enum"], [source["evidence_id"]])
        self.assertEqual(reference["span_index"], {"type": "integer", "minimum": 0, "maximum": 2})
        projected = payload(calls[0]["input"])["evidence"][0]
        self.assertNotIn("excerpt", projected)
        self.assertEqual("".join(span["text"] for span in projected["quote_spans"]), source["excerpt"])
        self.assertTrue(all(len(span["text"]) <= 800 for span in projected["quote_spans"]))
        self.assertEqual(answer["checks"][0]["supporting_quotes"], [{"evidence_id": source["evidence_id"],
            "quote": "Contrary condition remains original."}])
        self.assertEqual(_audit(answer, [claim], [source], data["documents"])[0]["verdict"], "supported")

    def test_strict_audit_rejects_unregistered_source_and_invalid_span_without_copying_quotes(self):
        from types import SimpleNamespace
        source = canonical_evidence(canonical())[0]
        data = {"claims": [{"claim_id": "fixed-claim"}], "evidence": [source]}
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def create(self, **kwargs):
                return SimpleNamespace(status="completed", output_text=json.dumps({"checks": {
                    "fixed-claim": {"verdict": "supported", "reason": "OFFLINE invalid reference",
                        "claim_reference": {"evidence_id": source["evidence_id"], "span_index": 0},
                        "technology_references": {},
                        "references": [reference], "target": "report", "role": None, "criterion_ids": []}}}))
        for reference in ({"evidence_id": "invented", "span_index": 0},
                          {"evidence_id": source["evidence_id"], "span_index": 50},
                          {"evidence_id": source["evidence_id"], "span_index": None},
                          {"evidence_id": source["evidence_id"], "span_index": True}):
            with self.subTest(reference=reference), patch("pipeline.governance.openai_client", return_value=Client()):
                with self.assertRaises(JudgeContractError):
                    _provider("offline-model", phase="audit", data=data)(JUDGE_INSTRUCTIONS, _judge_prompt("audit", data))

    def technology_audit_fixture(self):
        sw = canonical_evidence(canonical())[0]
        sw["excerpt"] = "원본 SW 조건.\n" + "S" * 810
        hw = {**deepcopy(sw), "evidence_id": "HW-original", "doc_id": "HW-01",
              "technology_ids": ["HW-01"], "source_hash": "b" * 64,
              "excerpt": "원본 HW 조건.\n"}
        claim = {"claim_id": "two-technology-claim", "technology_ids": ["SW-01", "HW-01"],
                 "citation_keys": ["SW01_RDKV", "HW01_PHOTONIC_CXL"],
                 "rendered_citation_keys": ["SW01_RDKV", "HW01_PHOTONIC_CXL"]}
        documents = {**canonical()["documents"], "HW-01": {"sha256": "b" * 64, "citation_key": "HW01_PHOTONIC_CXL"}}
        data = {"claims": [claim], "evidence": [sw, hw], "documents": documents}
        row = {"verdict": "supported", "reason": "OFFLINE two-source contract fixture, not a semantic judgment",
            "claim_reference": {"evidence_id": sw["evidence_id"], "span_index": 0},
            "technology_references": {"SW-01": {"evidence_id": sw["evidence_id"], "span_index": 0},
                                      "HW-01": {"evidence_id": hw["evidence_id"], "span_index": 0}},
            "references": [{"evidence_id": sw["evidence_id"], "span_index": 0},
                           {"evidence_id": sw["evidence_id"], "span_index": 1}],
            "target": "report", "role": None, "criterion_ids": []}
        return data, {"checks": {claim["claim_id"]: row}}

    def test_supported_wire_schema_requires_original_reference_for_every_actual_technology(self):
        data, answer = self.technology_audit_fixture()
        schema = _audit_schema(data)
        self.assertTrue(schema_accepts(schema, answer))
        invalid_rows = []
        original = answer["checks"]["two-technology-claim"]
        for replacement in (None, {"evidence_id": "SW-laboratory", "span_index": 0},
                            {"evidence_id": "HW-original", "span_index": 1},
                            {"evidence_id": "HW-original", "span_index": True}):
            row = deepcopy(original)
            row["technology_references"]["HW-01"] = replacement
            invalid_rows.append(row)
        missing, extra, no_table = deepcopy(original), deepcopy(original), deepcopy(original)
        del missing["technology_references"]["HW-01"]
        extra["technology_references"]["OTHER"] = None
        del no_table["technology_references"]
        invalid_rows.extend((missing, extra, no_table))
        for row in invalid_rows:
            raw = {"checks": {"two-technology-claim": row}}
            with self.subTest(row=row):
                self.assertFalse(schema_accepts(schema, raw))
                with self.assertRaises(JudgeContractError):
                    _normalize_provider_answer("audit", json.dumps(raw), data)

    def test_technology_references_bind_original_spans_and_deduplicate_extra_quotes(self):
        data, answer = self.technology_audit_fixture()
        immutable = deepcopy(data)
        normalized = _normalize_provider_answer("audit", json.dumps(answer), data)
        check = normalized["checks"][0]
        sw, hw = data["evidence"]
        self.assertEqual(check["supporting_quotes"], [
            {"evidence_id": sw["evidence_id"], "quote": sw["excerpt"][:800]},
            {"evidence_id": hw["evidence_id"], "quote": hw["excerpt"]},
            {"evidence_id": sw["evidence_id"], "quote": sw["excerpt"][800:]}])
        self.assertEqual(check["evidence_ids"], [sw["evidence_id"], hw["evidence_id"]])
        self.assertNotIn("technology_references", check)
        self.assertNotIn("claim_reference", check)
        self.assertEqual(data, immutable)
        self.assertEqual(_audit(normalized, data["claims"], data["evidence"], data["documents"])[0]["verdict"], "supported")

    def test_missing_technology_original_removes_supported_branch_but_allows_honest_partial_verdict(self):
        data, answer = self.technology_audit_fixture()
        data["evidence"] = data["evidence"][:1]
        row = answer["checks"]["two-technology-claim"]
        row["technology_references"]["HW-01"] = None
        schema = _audit_schema(data)
        self.assertFalse(schema_accepts(schema, answer))
        with self.assertRaises(JudgeContractError):
            _normalize_provider_answer("audit", json.dumps(answer), data)
        for verdict in ("contradicted", "unsupported", "uncertain"):
            row["verdict"] = verdict
            self.assertTrue(schema_accepts(schema, answer))
            normalized = _normalize_provider_answer("audit", json.dumps(answer), data)
            self.assertEqual(_audit(normalized, data["claims"], data["evidence"], data["documents"])[0]["verdict"], verdict)
        row["technology_references"]["SW-01"] = None
        row["claim_reference"] = None
        row["references"] = []
        self.assertTrue(schema_accepts(schema, answer))
        self.assertEqual(_normalize_provider_answer("audit", json.dumps(answer), data)["checks"][0]["evidence_ids"], [])

    def test_generic_supported_fact_requires_at_least_one_registered_original(self):
        data, answer = self.technology_audit_fixture()
        data["claims"][0]["technology_ids"] = []
        row = answer["checks"]["two-technology-claim"]
        row["technology_references"] = {}
        row["claim_reference"] = None
        row["references"] = []
        schema = _audit_schema(data)
        self.assertFalse(schema_accepts(schema, answer))
        with self.assertRaises(JudgeContractError):
            _normalize_provider_answer("audit", json.dumps(answer), data)
        row["claim_reference"] = {"evidence_id": "SW-laboratory", "span_index": 0}
        self.assertTrue(schema_accepts(schema, answer))
        normalized = _normalize_provider_answer("audit", json.dumps(answer), data)
        self.assertEqual(_audit(normalized, data["claims"], data["evidence"], data["documents"])[0]["verdict"], "supported")

    def test_claim_anchor_selects_the_claims_actual_citation_within_collective_paragraph_sources(self):
        data, answer = self.technology_audit_fixture()
        claim = data["claims"][0]
        claim["technology_ids"] = ["SW-01"]
        claim["citation_keys"] = ["SW01_RDKV"]
        claim["rendered_citation_keys"] = ["SW01_RDKV", "OTHER_SW"]
        other = {**deepcopy(data["evidence"][0]), "evidence_id": "other-SW-original", "doc_id": "other-SW"}
        data["evidence"].append(other)
        data["documents"]["other-SW"] = {"sha256": "a" * 64, "citation_key": "OTHER_SW"}
        row = answer["checks"][claim["claim_id"]]
        row["technology_references"].pop("HW-01")
        row["references"] = [{"evidence_id": "other-SW-original", "span_index": 0}]
        schema = _audit_schema(data)
        for verdict in ("supported", "contradicted", "unsupported", "uncertain"):
            row["verdict"] = verdict
            row["claim_reference"] = {"evidence_id": "SW-laboratory", "span_index": 0}
            self.assertTrue(schema_accepts(schema, answer))
            normalized = _normalize_provider_answer("audit", json.dumps(answer), data)
            self.assertEqual(_audit(normalized, data["claims"], data["evidence"], data["documents"])[0]["verdict"], verdict)
            row["claim_reference"] = {"evidence_id": "other-SW-original", "span_index": 0}
            self.assertFalse(schema_accepts(schema, answer))
            with self.assertRaises(JudgeContractError):
                _normalize_provider_answer("audit", json.dumps(answer), data)

    def test_quote_free_verdict_has_null_anchor_null_technology_table_and_no_extra_reference(self):
        data, answer = self.technology_audit_fixture()
        row = answer["checks"]["two-technology-claim"]
        row.update(verdict="uncertain", claim_reference=None, references=[],
                   technology_references={"SW-01": None, "HW-01": None})
        schema = _audit_schema(data)
        for verdict in ("unsupported", "uncertain"):
            row["verdict"] = verdict
            self.assertTrue(schema_accepts(schema, answer))
            self.assertEqual(_normalize_provider_answer("audit", json.dumps(answer), data)["checks"][0]["supporting_quotes"], [])
        for change in ({"verdict": "contradicted"},
                       {"references": [{"evidence_id": "SW-laboratory", "span_index": 0}]},
                       {"technology_references": {"SW-01": {"evidence_id": "SW-laboratory", "span_index": 0}, "HW-01": None}}):
            broken = {"checks": {"two-technology-claim": {**row, **change}}}
            self.assertFalse(schema_accepts(schema, broken))
            with self.assertRaises(JudgeContractError):
                _normalize_provider_answer("audit", json.dumps(broken), data)

    def test_no_owner_and_actual_citation_anchor_offers_only_quote_free_honest_verdicts(self):
        data, answer = self.technology_audit_fixture()
        data["claims"][0]["technology_ids"] = ["HW-01"]
        data["claims"][0]["citation_keys"] = ["SW01_RDKV"]
        row = answer["checks"]["two-technology-claim"]
        row.update(technology_references={"HW-01": None}, claim_reference=None, references=[])
        schema = _audit_schema(data)
        for verdict in ("supported", "contradicted", "unsupported", "uncertain"):
            row["verdict"] = verdict
            self.assertEqual(schema_accepts(schema, answer), verdict in {"unsupported", "uncertain"})
            if verdict in {"unsupported", "uncertain"}:
                self.assertEqual(_normalize_provider_answer("audit", json.dumps(answer), data)["checks"][0]["evidence_ids"], [])
            else:
                with self.assertRaises(JudgeContractError):
                    _normalize_provider_answer("audit", json.dumps(answer), data)
        for reference in ({"evidence_id": "SW-laboratory", "span_index": 0},
                          {"evidence_id": "HW-original", "span_index": 0}):
            row.update(verdict="uncertain", claim_reference=reference)
            self.assertFalse(schema_accepts(schema, answer))
            with self.assertRaises(JudgeContractError):
                _normalize_provider_answer("audit", json.dumps(answer), data)

    def test_shared_source_schema_fits_provider_limits_for_213_originals_and_twenty_claims(self):
        sources = [{"evidence_id": f"original-{index:03d}-" + "x" * 180,
                    "technology_ids": ["SW-01" if index % 2 else "HW-01"], "excerpt": "X" * 1601}
                   for index in range(213)]
        claims = [{"claim_id": f"claim-{index}", "technology_ids": ["SW-01", "HW-01"]} for index in range(20)]
        schema = _audit_schema({"claims": claims, "evidence": sources})
        serialized = json.dumps(schema)
        for source in sources:
            self.assertEqual(serialized.count(json.dumps(source["evidence_id"])), 1)
        counts = {"enums": 0, "properties": 0, "string_chars": 0}
        def count(node):
            if isinstance(node, dict):
                counts["enums"] += len(node.get("enum", []))
                counts["properties"] += len(node.get("properties", {}))
                counts["string_chars"] += sum(len(key) for key in node)
                for value in node.values(): count(value)
            elif isinstance(node, list):
                for value in node: count(value)
            elif isinstance(node, str):
                counts["string_chars"] += len(node)
        def depth(node):
            if "$ref" in node:
                return depth(schema["$defs"][node["$ref"].split("/")[-1]])
            choices = [depth(branch) for branch in node.get("anyOf", [])]
            if node.get("type") == "object":
                return 1 + max([depth(value) for value in node.get("properties", {}).values()] + [0])
            if node.get("type") == "array":
                return 1 + depth(node.get("items", {}))
            return max(choices + [0])
        count(schema)
        self.assertLessEqual(counts["enums"], 1000)
        self.assertLessEqual(counts["properties"], 5000)
        self.assertLessEqual(counts["string_chars"], 120000)  # Conservative: every schema string/key.
        self.assertLessEqual(depth(schema), 10)

    def test_structured_provider_rejects_omitted_fixed_units_and_claims(self):
        from types import SimpleNamespace
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def create(self, **kwargs):
                return SimpleNamespace(status="completed", output_text=json.dumps(answer))
        cases = [("atomize", {"blocks": [{"block_id": "fixed-unit", "text": "original", "page": 1}],
                   "citation_numbers": {"1": "SW01_RDKV"}}, {"blocks": {}}),
                 ("audit", {"claims": [{"claim_id": "fixed-claim"}],
                   "evidence": canonical_evidence(canonical())}, {"checks": {}})]
        for phase, data, answer in cases:
            with self.subTest(phase=phase), patch("pipeline.governance.openai_client", return_value=Client()):
                with self.assertRaises(JudgeContractError):
                    _provider("offline-model", phase=phase, data=data)(JUDGE_INSTRUCTIONS, _judge_prompt(phase, data))

    def test_literal_spaced_citations_are_distributed_without_dropping_or_borrowing(self):
        data = {"blocks": [{"block_id": "unit", "text": "실제 인용 [1,        8,9].\n", "page": 1}],
                "citation_numbers": {"1": "SW01_RDKV", "8": "FABRIC", "9": "BLOG", "10": "OTHER"}}
        def claim(keys):
            return {"text": "offline assertion", "kind": "fact", "technology_ids": ["SW-01"],
                    "citation_keys": keys, "core": True}
        good = {"blocks": {"unit": {"non_claim_reason": "", "claims": [claim(["SW01_RDKV"]), claim(["FABRIC", "BLOG"])]}}}
        answer = _normalize_provider_answer("atomize", json.dumps(good), data)
        self.assertEqual(answer["blocks"][0]["claims"][0]["citation_keys"], ["SW01_RDKV"])
        for wrong in ([claim(["BLOG"])], [claim(["SW01_RDKV", "FABRIC", "BLOG", "OTHER"])]):
            with self.assertRaises(JudgeContractError):
                _normalize_provider_answer("atomize", json.dumps({"blocks": {"unit": {"non_claim_reason": "", "claims": wrong}}}), data)

    def test_invalid_judgment_gets_one_correction_with_immutable_original_inputs(self):
        attempts = []
        def responder(instructions, prompt):
            data = payload(prompt)
            if data["phase"] == "atomize":
                attempts.append(data)
                if len(attempts) == 1:
                    return {"blocks": []}
            return self.responder(instructions, prompt)
        result = self.evaluate(responder)
        self.assertEqual(result["route"], "passed")
        self.assertEqual(result["judge_calls"], 4)
        self.assertEqual(attempts[0]["blocks"], attempts[1]["blocks"])
        self.assertEqual(attempts[0]["citation_numbers"], attempts[1]["citation_numbers"])
        self.assertIn("contract_feedback", attempts[1])
        result = self.evaluate(lambda *args: {"blocks": []})
        self.assertEqual(result["route"], "review_required")
        self.assertEqual(result["judge_calls"], 2)

    def test_verified_raw_cache_revalidates_without_replaying_completed_provider_calls(self):
        def provider(model, *, phase, data):
            def respond(instructions, prompt):
                answer = self.responder(instructions, _judge_prompt(phase, data))
                if phase == "atomize":
                    raw = {"blocks": {row["block_id"]: {"non_claim_reason": row["non_claim_reason"],
                        "claims": [{key: value for key, value in claim.items() if key != "report_quote"} for claim in row["claims"]]}
                        for row in answer["blocks"]}}
                elif phase == "audit":
                    raw = raw_audit_checks(answer, data)
                else:
                    raw = answer
                respond.raw_response = json.dumps(raw)
                return _normalize_provider_answer(phase, respond.raw_response, data)
            return respond
        def execute():
            with patch("pipeline.report_quality.extract_pdf", return_value=(1, self.blocks)):
                return evaluate_report(tex_path=self.tex, pdf_path=self.pdf, review_input=canonical(),
                    report_markdown=self.markdown, model="offline-judge", output_dir=self.output)
        with patch("pipeline.report_quality._provider", side_effect=provider):
            first, second = execute(), execute()
            self.assertEqual((first["route"], second["route"]), ("passed", "passed"))
            self.assertEqual((first["judge_calls"], second["judge_calls"]), (3, 1))
            self.assertEqual(second["cache_hits"], 2)
            self.assertEqual(len(self.calls), 4)
            cached = next((self.output / "quality-responses").glob("*.json"))
            envelope = json.loads(cached.read_text()); envelope["raw"] = "tampered"
            cached.write_text(json.dumps(envelope))
            third = execute()
            self.assertEqual(third["route"], "passed")
            self.assertEqual(third["judge_calls"], 2)


    def test_corrected_raw_cache_redirect_reuses_only_after_current_validation(self):
        atomize_calls = []
        def provider(model, *, phase, data):
            def respond(instructions, prompt):
                if phase == "atomize":
                    atomize_calls.append(data)
                    if len(atomize_calls) == 1:
                        respond.raw_response = json.dumps({"blocks": {}})
                        return _normalize_provider_answer(phase, respond.raw_response, data)
                answer = self.responder(instructions, _judge_prompt(phase, data))
                if phase == "atomize":
                    raw = {"blocks": {row["block_id"]: {"non_claim_reason": row["non_claim_reason"],
                        "claims": [{key: value for key, value in claim.items() if key != "report_quote"} for claim in row["claims"]]}
                        for row in answer["blocks"]}}
                elif phase == "audit":
                    raw = raw_audit_checks(answer, data)
                else:
                    raw = answer
                respond.raw_response = json.dumps(raw)
                return _normalize_provider_answer(phase, respond.raw_response, data)
            return respond
        def execute():
            with patch("pipeline.report_quality.extract_pdf", return_value=(1, self.blocks)):
                return evaluate_report(tex_path=self.tex, pdf_path=self.pdf, review_input=canonical(),
                    report_markdown=self.markdown, model="offline-judge", output_dir=self.output)
        with patch("pipeline.report_quality._provider", side_effect=provider):
            first, second = execute(), execute()
            self.assertEqual(first["route"], second["route"])
            self.assertNotEqual(first["route"], "review_required", first["gates"])
            self.assertEqual((first["judge_calls"], second["judge_calls"]), (4, 1))
            self.assertEqual(second["cache_hits"], 2)
            self.assertEqual(len(atomize_calls), 2)
            self.assertIn("contract_feedback", atomize_calls[1])
            from pipeline.report_quality import _atomize
            count = []
            def current_validator(*args):
                count.append(1)
                if len(count) == 1:
                    raise JudgeContractError("Offline current validator rejects the cached disposition")
                return _atomize(*args)
            with patch("pipeline.report_quality._atomize", side_effect=current_validator):
                third = execute()
            self.assertEqual(third["route"], second["route"])
            self.assertEqual(third["judge_calls"], 2)
            self.assertEqual(len(count), 2)


if __name__ == "__main__":
    unittest.main()
