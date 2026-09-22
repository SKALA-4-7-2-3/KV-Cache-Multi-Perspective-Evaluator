import unittest
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Evidence, Citation


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1]/'fixtures/input.md')
        self.web = Evidence(id='MKT-X', doc_id='X', title='PF-NIC support', url='https://example.org/support',
            excerpt='PF-NIC supports CXL shared memory for AI inference.', access_status='full_text',
            content_status='substantive', tech_ids=['HW-01'])

    def claim(self, **updates):
        from market_agent.schemas import Claim
        values = dict(tech_id='HW-01', criterion_id='ecosystem_support', statement='공급사는 PF-NIC의 CXL 공유 메모리 지원을 설명한다.',
            basis='fact', relation_to_technology='method_family', conditions=['선정 논문 구현과의 연결 미확인'], metric=None,
            citation=Citation(evidence_id=self.web.id, quote=self.web.excerpt, subject='PF-NIC', source_character='합성 공급사 발표'))
        values.update(updates)
        return Claim(**values)

    def test_invalid_claim_does_not_erase_independent_valid_context(self):
        from market_agent.claims import validate_claims, materialize
        from market_agent.schemas import DraftAnalysis
        bad = self.claim(statement='상용 채택됨', citation=Citation(evidence_id='E-HW-001', quote='invented',subject='Photonic-CXL',source_character='요약'))
        pool, errors = validate_claims(self.data,[bad,self.claim()],{**self.data.evidence,self.web.id:self.web})
        self.assertEqual(len(pool),1)
        self.assertTrue(errors)
        result, _ = materialize(self.data,DraftAnalysis(assessments=[],followup_questions=[]),pool)
        row=next(r for r in result.assessments if r.tech_id=='HW-01' and r.criterion_id=='ecosystem_support')
        self.assertEqual(row.verdict,'unknown')
        self.assertEqual(len(row.context_findings),1)
        self.assertEqual(row.context_findings[0].citations[0].evidence_id,'MKT-X')

    def test_metadata_cannot_supply_a_market_claim(self):
        from market_agent.claims import validate_claims
        self.web.content_status='metadata_only'
        pool,errors=validate_claims(self.data,[self.claim()],{self.web.id:self.web})
        self.assertFalse(pool)
        self.assertTrue(errors)

    def test_related_claim_cannot_be_used_as_selected_paper_conclusion(self):
        from market_agent.claims import validate_claims, materialize
        from market_agent.schemas import DraftAnalysis, DraftAssessment
        pool,_=validate_claims(self.data,[self.claim()],{self.web.id:self.web})
        draft=DraftAssessment(tech_id='HW-01',criterion_id='ecosystem_support',judgment='선정 논문을 지원한다',
            verdict='conditional',basis='fact',claim_ids=list(pool),conditions=['조건'],gaps=[])
        result,errors=materialize(self.data,DraftAnalysis(assessments=[draft],followup_questions=[]),pool)
        row=next(r for r in result.assessments if r.tech_id=='HW-01' and r.criterion_id=='ecosystem_support')
        self.assertEqual(row.basis,'unknown')
        self.assertEqual(len(row.context_findings),1)
        self.assertFalse(errors)

    def test_duplicate_source_claim_is_not_counted_twice(self):
        from market_agent.claims import validate_claims
        pool,_=validate_claims(self.data,[self.claim(),self.claim()],{self.web.id:self.web})
        self.assertEqual(len(pool),1)
