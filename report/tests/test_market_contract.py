"""Offline market coverage fixtures; they assert no real technology findings."""
import json
import re
import unittest

from report_agent import ReportAgent
from report_agent.parser import MARKET_CRITERIA, parse_report_input
from report_agent.prompt import build_generation_prompt, build_repair_prompt
from report_agent.validator import validate_latex
from tests.helpers import sample_input, valid_latex


def market_input():
    findings = [{"id": f"RAW-{tech}-{criterion}", "technology_ids": [tech],
        "criterion_id": criterion, "text": "Offline source analysis with explicit limitations.",
        "basis": "inference", "limitations": ["No real market claim is asserted."]}
        for tech in ("SW-01", "HW-01") for criterion in MARKET_CRITERIA]
    findings += [{**row, "id": row["id"] + "-second-source"} for row in findings[:8]]
    block = json.dumps({"draft_findings": findings}, ensure_ascii=False)
    return sample_input() + "\n<!-- UPSTREAM_ANALYSIS_JSON\n" + block + "\nEND_UPSTREAM_ANALYSIS_JSON -->\n", findings


def market_latex():
    cells = []
    for tech, name, cite in (("SW-01", "RDKV", "SW01_RDKV"),
                             ("HW-01", "Photonic-CXL", "HW01_PHOTONIC_CXL")):
        for criterion, label in MARKET_CRITERIA.items():
            cells.append(f"% BEGIN_MARKET_CELL {tech} {criterion}\n"
                + rf"\paragraph{{{name} — {label}}}" + "\n"
                + "원문에서 도입 조건을 제한적으로 설명한다. 적용 효과는 조건부 해석이며 실 운영 검증이 필요하다."
                + rf"\cite{{{cite}}}" + "\n"
                + f"% END_MARKET_CELL {tech} {criterion}\n")
    return valid_latex().replace("\\subsection{시장성}\n미확인 사항을 보존한다.",
                                "\\subsection{시장성}\n" + "".join(cells))


class MarketContractTests(unittest.TestCase):
    def test_all_raw_findings_preserved_and_contract_in_both_prompts(self):
        source, findings = market_input()
        parsed = parse_report_input(source)
        self.assertEqual(list(parsed.market_findings), findings)
        self.assertEqual(len(parsed.market_findings), 20)
        self.assertEqual(len(parsed.market_cells), 12)
        self.assertEqual(parsed.raw_markdown, source)
        for prompt in (build_generation_prompt(parsed), build_repair_prompt(parsed, "candidate", ["market missing"])):
            for tech, criterion in parsed.market_cells:
                self.assertIn(f"% BEGIN_MARKET_CELL {tech} {criterion}", prompt)
            self.assertIn(findings[-1]["id"], prompt)
        result = validate_latex(market_latex(), parsed)
        self.assertTrue(result.valid, result.issues)

    def test_missing_cell_and_comment_only_cell_rejected(self):
        parsed = parse_report_input(market_input()[0])
        pattern = r"(?m)^% BEGIN_MARKET_CELL HW-01 standardization\n([\s\S]*?)^% END_MARKET_CELL HW-01 standardization\n"
        for replacement in ("", "% BEGIN_MARKET_CELL HW-01 standardization\n"
                + r"\paragraph{Photonic-CXL — 표준화}" + "\n% END_MARKET_CELL HW-01 standardization\n"):
            candidate = re.sub(pattern, lambda _: replacement, market_latex())
            result = validate_latex(candidate, parsed)
            self.assertFalse(result.valid)
            self.assertTrue(any("HW-01/standardization" in issue for issue in result.issues))
        fake_prefix = market_latex().replace("% BEGIN_MARKET_CELL HW-01 standardization\n",
                                            "% BEGIN_MARKET_CELL HW-01 standardization_FAKE\n")
        self.assertFalse(validate_latex(fake_prefix, parsed).valid)

    def test_model_repairs_missing_cells_without_code_inserting_analysis(self):
        outputs = iter((valid_latex(), market_latex()))
        prompts = []
        def respond(_instructions, prompt):
            prompts.append(prompt)
            return next(outputs)
        result = ReportAgent(responder=respond).generate(market_input()[0])
        self.assertEqual(result.attempts, 2)
        self.assertTrue(result.validation.valid)
        self.assertIn("시장성 HW-01/standardization", prompts[1])

    def test_legacy_input_without_complete_canonical_cells_keeps_old_contract(self):
        parsed = parse_report_input(sample_input())
        self.assertEqual(parsed.market_cells, ())
        self.assertTrue(validate_latex(valid_latex(), parsed).valid)

    def test_uncited_gap_requires_impact_and_next_check_without_fake_pass(self):
        parsed = parse_report_input(market_input()[0])
        gap = ("% BEGIN_MARKET_CELL HW-01 business_value\n"
            + r"\paragraph{Photonic-CXL — 사업가치}" + "\n"
            + "미확인 범위: 실제 운영 비용 자료가 없다. 판단 영향: 총비용 절감 여부를 확정할 수 없다. "
            + "다음 확인: 동일 워크로드의 장비·운영 비용을 측정한다.\n"
            + "% END_MARKET_CELL HW-01 business_value\n")
        pattern = r"(?m)^% BEGIN_MARKET_CELL HW-01 business_value\n[\s\S]*?^% END_MARKET_CELL HW-01 business_value\n"
        candidate = re.sub(pattern, lambda _: gap, market_latex())
        result = validate_latex(candidate, parsed)
        self.assertTrue(result.valid, result.issues)
        self.assertFalse(validate_latex(candidate.replace("판단 영향:", "일반 설명:"), parsed).valid)
        self.assertIn("총비용 절감 여부를 확정할 수 없다", candidate)


if __name__ == "__main__":
    unittest.main()
