import unittest
from datetime import date
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Analysis, Assessment, Evidence, Question, Citation
from market_agent.validation import validate_analysis


INPUT = Path(__file__).parents[1] / "fixtures/input.md"


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.input = read_input(INPUT)
        self.web = Evidence(id="MKT-1", doc_id="WEB-1", title="Test", url="https://example.org",
            published_at=date(2026, 9, 1), excerpt="RDKV: a customer reports production adoption.", access_status="full_text", tech_ids=["SW-01"])

    def assessment(self, **changes):
        fields = dict(tech_id="SW-01", criterion_id="adoption", judgment="고객 도입을 보고함",
            basis="fact", relation_to_technology="exact", evidence_ids=["MKT-1"],
            conditions=[], metric=None, gaps=[], citations=[Citation(evidence_id='MKT-1',
                quote='RDKV: a customer reports production adoption.', subject='RDKV', source_character='합성 테스트 자료')])
        fields.update(changes)
        return Assessment(**fields)

    def validate(self, items, evidence=None):
        return validate_analysis(self.input, Analysis(assessments=items, followup_questions=[]),
            evidence if evidence is not None else {**self.input.evidence, "MKT-1": self.web})

    def test_fills_missing_criteria_and_rejects_fake_citations(self):
        result, errors = self.validate([self.assessment(evidence_ids=["fake"])])
        self.assertEqual(len(result.assessments), 12)
        self.assertTrue(all(a.basis == "unknown" for a in result.assessments))
        self.assertTrue(errors)

    def test_abstract_does_not_prove_customer_adoption(self):
        result, _ = self.validate([self.assessment(evidence_ids=["E-SW-001"])])
        self.assertEqual(next(a for a in result.assessments if a.tech_id == "SW-01" and a.criterion_id == "adoption").basis, "unknown")

    def test_family_support_cannot_be_exact_technology_adoption(self):
        result, _ = self.validate([self.assessment(relation_to_technology="method_family")])
        self.assertEqual(next(a for a in result.assessments if a.tech_id == "SW-01" and a.criterion_id == "adoption").basis, "unknown")

    def test_future_source_and_duplicate_cells_are_rejected(self):
        future = self.web.model_copy(update={"published_at": date(2026, 10, 1)})
        result, errors = self.validate([self.assessment()], {"MKT-1": future})
        self.assertTrue(errors)
        result, errors = self.validate([self.assessment(), self.assessment()])
        self.assertTrue(any("duplicate" in e["code"] for e in errors))

    def test_valid_source_retains_supported_cell(self):
        result, _ = self.validate([self.assessment()])
        row = next(a for a in result.assessments if a.tech_id == "SW-01" and a.criterion_id == "adoption")
        self.assertEqual(row.basis, "fact")
        self.assertEqual(row.evidence_ids, ["MKT-1"])

    def test_unknown_judgment_explains_the_gap_in_korean(self):
        result, _ = self.validate([self.assessment(basis="unknown", judgment="unknown",
            gaps=["이번 조사에서 도입 사례를 확인하지 못함"])])
        row = next(a for a in result.assessments if a.tech_id == "SW-01" and a.criterion_id == "adoption")
        self.assertEqual(row.judgment, "미확인: 이번 조사에서 도입 사례를 확인하지 못함")


if __name__ == "__main__":
    unittest.main()
