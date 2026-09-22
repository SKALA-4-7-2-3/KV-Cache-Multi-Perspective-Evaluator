"""실제 실행에서 발견한 대상 혼동을 재현하는 합성 원문 회귀 사례."""
import unittest
from datetime import date
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Analysis, Assessment, Evidence
from market_agent.validation import validate_analysis

INPUT = Path(__file__).parents[1] / 'fixtures/input.md'


class QualityRegressionTests(unittest.TestCase):
    def check_row(self, text, **changes):
        data = read_input(INPUT)
        evidence = Evidence(id='MKT-X', doc_id='DOC-X', title='Synthetic official announcement',
            url='https://example.org/announcement', published_at=date(2026, 9, 1),
            excerpt=text, access_status='full_text', tech_ids=['HW-01'])
        values = dict(tech_id='HW-01', criterion_id='ecosystem_support', judgment='선정 구현을 지원함',
            basis='fact', relation_to_technology='exact', evidence_ids=['MKT-X'],
            conditions=[], metric=None, gaps=[])
        values.update(changes)
        result, errors = validate_analysis(data, Analysis(assessments=[Assessment(**values)], followup_questions=[]), {'MKT-X': evidence})
        return next(a for a in result.assessments if a.tech_id == 'HW-01' and a.criterion_id == 'ecosystem_support'), errors

    def test_official_family_claim_without_identity_is_not_selected_paper_fact(self):
        row, _ = self.check_row('PF-NIC supports CXL 3.1 and PCIe 6.0.')
        self.assertEqual(row.basis, 'unknown')
        self.assertIn('identity_unverified', row.unknown_reasons)

    def test_exact_label_does_not_replace_original_quote(self):
        row, _ = self.check_row('Photonic-CXL: a simulated memory design.')
        self.assertEqual(row.basis, 'unknown')

    def test_unknown_always_has_report_verdict_and_reason(self):
        row, _ = self.check_row('', basis='unknown', judgment='unknown', gaps=['논문과 제품의 연결 자료 미확인'])
        self.assertEqual(row.verdict, 'unknown')
        self.assertIn('연결 자료', row.judgment)


if __name__ == '__main__':
    unittest.main()

class CitationContextTests(unittest.TestCase):
    def test_context_citation_is_relinked_only_to_matching_original_text(self):
        from market_agent.schemas import Citation, ContextFinding
        data = read_input(INPUT)
        quote = 'Marvell Photonic Fabric memory modules support shared memory for AI inference.'
        web = Evidence(id='MKT-R',doc_id='R',title='Marvell announcement',url='https://www.marvell.com/news/test',
            excerpt=quote,access_status='full_text',publisher='www.marvell.com',tech_ids=['HW-01'])
        row = Assessment(tech_id='HW-01',criterion_id='ecosystem_support',judgment='선정 구현과 동일성 미확인',
            basis='unknown',relation_to_technology='unknown',evidence_ids=[],conditions=[],gaps=['동일성 미확인'],metric=None,
            context_findings=[ContextFinding(statement='공급사는 공유 메모리 지원을 설명함',basis='fact',
                relation_to_technology='adjacent',conditions=['선정 논문과 동일성 미확인'],citations=[Citation(
                    evidence_id='E-HW-001',quote=quote,subject='Marvell Photonic Fabric',source_character='논문 저자',
                    identity_quote='Marvell Photonic Fabric memory modules')])])
        result,_=validate_analysis(data,Analysis(assessments=[row],followup_questions=[]),{**data.evidence,web.id:web})
        target=next(r for r in result.assessments if r.tech_id=='HW-01' and r.criterion_id=='ecosystem_support')
        self.assertEqual(len(target.context_findings),1)
        cite=target.context_findings[0].citations[0]
        self.assertEqual(cite.evidence_id,'MKT-R')
        self.assertNotIn('논문 저자',cite.source_character)

    def test_input_summary_does_not_certify_an_unrelated_web_claim_as_exact(self):
        from market_agent.schemas import Citation
        data = read_input(INPUT)
        e = Evidence(id='MKT-P',doc_id='P',title='PF-NIC',url='https://example.org',
            excerpt='PF-NIC improves token throughput.',access_status='full_text',tech_ids=['HW-01'])
        summary = data.evidence['E-HW-001']
        row = Assessment(tech_id='HW-01',criterion_id='business_value',judgment='선정 기술은 비용을 낮춘다',
            basis='fact',relation_to_technology='exact',evidence_ids=[summary.id,e.id],conditions=['조건'],gaps=[],metric=None,
            citations=[Citation(evidence_id=summary.id,quote=summary.excerpt,subject='Photonic-CXL',source_character='입력 요약'),
                Citation(evidence_id=e.id,quote=e.excerpt,subject='PF-NIC',source_character='공급사')])
        result,_=validate_analysis(data,Analysis(assessments=[row],followup_questions=[]),{**data.evidence,e.id:e})
        target=next(r for r in result.assessments if r.tech_id=='HW-01' and r.criterion_id=='business_value')
        self.assertEqual(target.basis,'unknown')

    def test_research_gaps_are_recomputed_instead_of_copying_previous_round(self):
        from market_agent.research import annotate, REASONS
        from market_agent.schemas import unknown, Limits
        from market_agent.tools import Budget
        data = read_input(INPUT)
        row = unknown('SW-01', 'commercialization', '제품화는 미확인')
        row.gaps = [REASONS['not_searched'], '상용 판매 자료 미확인']
        evidence = Evidence(id='MKT-X', doc_id='X', title='test', url='https://example.org',
            excerpt='RDKV product release', access_status='full_text', tech_ids=['SW-01'])
        result = annotate(Analysis(assessments=[row], followup_questions=[]), data, {'MKT-X': evidence},
            [], [], Budget(Limits(search=6,extract=10,llm=5)), True).assessments[0]
        self.assertEqual(result.research_status, 'reviewed')
        self.assertNotIn(REASONS['not_searched'], result.gaps)

    def test_context_survives_while_unproven_selected_claim_becomes_unknown(self):
        from market_agent.schemas import Citation, ContextFinding
        helper = QualityRegressionTests()
        cite = Citation(evidence_id='MKT-X', quote='PF-NIC supports CXL 3.1.', subject='PF-NIC', source_character='합성 공급사 발표')
        context = ContextFinding(statement='PF-NIC 공급사가 CXL 3.1 지원을 발표함', basis='fact',
            relation_to_technology='method_family', citations=[cite], conditions=['선정 논문의 구현과 연결 미확인'])
        row, _ = helper.check_row('PF-NIC supports CXL 3.1.', context_findings=[context])
        self.assertEqual(row.basis, 'unknown')
        self.assertEqual(len(row.context_findings), 1)
        self.assertTrue(row.context_findings[0].citations[0].locator)

    def test_fabricated_quote_and_unscoped_market_number_are_rejected(self):
        from market_agent.schemas import Citation, ContextFinding
        helper = QualityRegressionTests()
        context = ContextFinding(statement='연관 시장 100 billion USD', basis='fact', relation_to_technology='adjacent',
            citations=[Citation(evidence_id='MKT-X', quote='PF-NIC supports CXL 3.1.', subject='관련 시장', source_character='합성 자료')], conditions=[])
        row, _ = helper.check_row('PF-NIC supports CXL 3.1.', context_findings=[context])
        self.assertFalse(row.context_findings)

    def test_observed_baseline_metadata_preserves_five_review_cases(self):
        import json
        cases = json.loads((INPUT.parent/'review_cases.json').read_text())
        self.assertEqual(len(cases), 5)
        self.assertTrue(all(c['origin'] == 'observed_output' and c['required_check'] and c['forbidden'] for c in cases))
