"""자료 수준을 숨기지 않고 12개 전달 항목을 완성하는 공개 계약을 검사한다."""
import copy
import unittest
from datetime import date
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Analysis, Assessment, Citation, CRITERIA, Evidence


class DeliveryCompletionTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1] / 'fixtures/input.md')

    def complete(self, analysis, evidence, errors):
        # 신규 공개 진입점이 구현되기 전에는 이 import에서 RED가 된다.
        from market_agent.delivery import complete_delivery
        return complete_delivery(self.data, analysis, evidence, errors)

    def assert_complete(self, result, evidence):
        self.assertIsInstance(result, Analysis)
        expected = {(tech, criterion) for tech in self.data.technologies for criterion in CRITERIA}
        self.assertEqual(len(result.assessments), 12)
        self.assertEqual({(row.tech_id, row.criterion_id) for row in result.assessments}, expected)
        known = {**self.data.evidence, **evidence}
        for row in result.assessments:
            with self.subTest(technology=row.tech_id, criterion=row.criterion_id):
                self.assertNotEqual(row.verdict, 'unknown')
                self.assertTrue(row.judgment.strip())
                self.assertTrue(row.conditions)
                self.assertTrue(all(condition.strip() for condition in row.conditions))
                self.assertIn(row.evaluation_mode, {'grounded', 'provisional', 'scenario', 'research_plan'})
                self.assertIn(row.confidence, {'high', 'medium', 'low'})
                for material in row.model_dump()['supporting_materials']:
                    self.assertIn(material['evidence_id'], known)
                    self.assertIn(row.tech_id, known[material['evidence_id']].tech_ids)
                    self.assertTrue(material['review_status'])
                    self.assertTrue(material['reason'].strip())
        for technology in self.data.technologies:
            judgments = {row.judgment for row in result.assessments if row.tech_id == technology}
            self.assertEqual(len(judgments), 6, '서로 다른 평가 기준을 같은 일반 문구로 채우면 안 됩니다')

    def test_empty_analysis_produces_twelve_distinct_deliveries_with_conditions(self):
        result = self.complete(Analysis(assessments=[], followup_questions=[]), {}, [])

        self.assert_complete(result, {})

    def test_technical_summaries_alone_cannot_become_grounded_market_facts(self):
        evidence = {key: value.model_copy(deep=True) for key, value in self.data.evidence.items()}
        self.assertTrue(all(item.access_status == 'provided_summary' for item in evidence.values()))

        result = self.complete(Analysis(assessments=[], followup_questions=[]), evidence, [])

        self.assert_complete(result, evidence)
        for row in result.assessments:
            with self.subTest(technology=row.tech_id, criterion=row.criterion_id):
                self.assertNotEqual(row.basis, 'fact')
                self.assertIn(row.evaluation_mode, {'scenario', 'provisional'})
                self.assertNotEqual(row.confidence, 'high')

    def test_failed_metadata_and_future_sources_are_traceable_but_not_verified_citations(self):
        unsuitable = [
            Evidence(id='MKT-failed', doc_id='DOC-failed', title='Unavailable source',
                     url='https://example.org/failed', excerpt='Search result only; retrieval failed.',
                     access_status='failed', content_status='unchecked', tech_ids=['HW-01']),
            Evidence(id='MKT-metadata', doc_id='DOC-metadata', title='Paper metadata',
                     url='https://example.org/metadata', excerpt='Title and citation metadata only.',
                     access_status='full_text', content_status='metadata_only', tech_ids=['HW-01']),
            Evidence(id='MKT-future', doc_id='DOC-future', title='Future announcement',
                     url='https://example.org/future', excerpt='Photonic-CXL is commercially available.',
                     published_at=date(2027, 1, 1), access_status='full_text',
                     content_status='substantive', tech_ids=['HW-01']),
        ]
        evidence = {**self.data.evidence, **{item.id: item for item in unsuitable}}

        result = self.complete(Analysis(assessments=[], followup_questions=[]), evidence, [])

        self.assert_complete(result, evidence)
        invalid_ids = {item.id for item in unsuitable}
        retained = set()
        for row in result.assessments:
            citations = [*row.citations, *(citation for finding in row.context_findings
                                           for citation in finding.citations)]
            self.assertFalse(invalid_ids & {citation.evidence_id for citation in citations})
            for material in row.model_dump()['supporting_materials']:
                if material['evidence_id'] in invalid_ids:
                    retained.add(material['evidence_id'])
                    self.assertNotIn(material['review_status'], {'verified', 'accepted'})
                    self.assertTrue(material['reason'].strip())
        self.assertEqual(retained, invalid_ids, '검증에 사용할 수 없는 자료도 제외 이유와 함께 추적되어야 합니다')

    def test_existing_supported_conditional_assessment_is_preserved(self):
        source = Evidence(
            id='MKT-valid', doc_id='DOC-valid', title='Synthetic RDKV implementation',
            url='https://example.org/rdkv', published_at=date(2026, 9, 1),
            excerpt='RDKV implementation is available under a research license.',
            access_status='full_text', content_status='substantive', tech_ids=['SW-01'],
            locator='Implementation section',
        )
        original = Assessment(
            tech_id='SW-01', criterion_id='commercialization',
            judgment='합성 공식 자료는 RDKV의 연구용 구현 공개를 설명한다.',
            verdict='conditional', basis='fact', relation_to_technology='exact',
            evidence_ids=[source.id], conditions=['연구용 라이선스 조건 확인 필요'],
            metric=None, gaps=['실제 상용 고객 실적은 확인하지 못함'],
            citations=[Citation(
                evidence_id=source.id, quote=source.excerpt, subject='RDKV',
                source_character='합성 공식 자료', identity_quote='RDKV', locator=source.locator,
            )],
        )
        analysis = Analysis(assessments=[original], followup_questions=[])
        before = original.model_dump()
        evidence = {**self.data.evidence, source.id: source}

        result = self.complete(analysis, evidence, [])

        self.assert_complete(result, evidence)
        kept = next(row for row in result.assessments
                    if (row.tech_id, row.criterion_id) == ('SW-01', 'commercialization'))
        for field in ['judgment', 'verdict', 'basis', 'relation_to_technology', 'evidence_ids',
                      'conditions', 'metric', 'gaps', 'citations']:
            with self.subTest(field=field):
                self.assertEqual(kept.model_dump()[field], before[field])
        self.assertEqual(original.model_dump(), before)

    def test_materials_prefer_substantive_sentences_over_site_navigation(self):
        source=Evidence(id='MKT-noise',doc_id='DOC-noise',title='Implementation',
            url='https://example.org/noise',access_status='full_text',content_status='substantive',
            tech_ids=['SW-01'],criteria=['commercialization'],
            excerpt='Chat is not available. Get Free Sample: https://example.org/sample market growth forecast. '
                    'RDKV provides an implementation for KV cache quantization under a research license.')
        result=self.complete(Analysis(assessments=[],followup_questions=[]),{source.id:source},[])
        row=next(r for r in result.assessments if r.tech_id=='SW-01' and r.criterion_id=='commercialization')
        material=next(m for m in row.supporting_materials if m.evidence_id==source.id)
        self.assertIn('RDKV provides',material.quote)
        self.assertNotIn('Chat is',material.quote)
        self.assertNotIn('Get Free',material.quote)

    def test_model_failure_still_returns_twelve_deliveries_without_mutating_inputs(self):
        analysis = Analysis(assessments=[], followup_questions=[])
        evidence = {key: value.model_copy(deep=True) for key, value in self.data.evidence.items()}
        errors = [{'stage': 'llm_extract', 'code': 'synthetic_transport', 'scope': 'global'}]
        errors_before = copy.deepcopy(errors)
        evidence_before = {key: value.model_dump() for key, value in evidence.items()}
        analysis_before = analysis.model_dump()

        result = self.complete(analysis, evidence, errors)

        self.assert_complete(result, evidence)
        self.assertEqual(errors, errors_before)
        self.assertEqual({key: value.model_dump() for key, value in evidence.items()}, evidence_before)
        self.assertEqual(analysis.model_dump(), analysis_before)
        self.assertTrue(all(row.evaluation_mode != 'grounded' and row.basis != 'fact'
                            for row in result.assessments))


if __name__ == '__main__':
    unittest.main()
