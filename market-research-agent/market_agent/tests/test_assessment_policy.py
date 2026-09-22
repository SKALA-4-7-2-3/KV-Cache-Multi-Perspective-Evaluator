"""관련 시장 평가와 선정 구현의 사실 확인은 서로 다른 증거를 요구한다."""
import unittest
from market_agent.tests import test_claims
from market_agent.schemas import Analysis, DraftAnalysis, DraftAssessment
from market_agent.claims import validate_claims, materialize
from market_agent.validation import validate_analysis


class AssessmentPolicyTests(unittest.TestCase):
    def setUp(self):
        helper=test_claims.ClaimTests();helper.setUp()
        self.data,self.web,self.claim=helper.data,helper.web,helper.claim

    def assess(self, criterion='ecosystem_support', basis='inference'):
        claim=self.claim(criterion_id=criterion)
        pool,_=validate_claims(self.data,[claim],{self.web.id:self.web})
        draft=DraftAssessment(tech_id='HW-01',criterion_id=criterion,judgment='이 문구로 선정 논문 지원을 단정해서는 안 된다',
            verdict='conditional',basis=basis,claim_ids=list(pool),conditions=['선정 구현과 인터페이스 호환성 검증 필요'],gaps=[])
        analysis,_=materialize(self.data,DraftAnalysis(assessments=[draft],followup_questions=[]),pool)
        validated,_=validate_analysis(self.data,analysis,{self.web.id:self.web})
        return next(r for r in validated.assessments if r.tech_id=='HW-01' and r.criterion_id==criterion)

    def test_family_support_survives_as_conditional_inference_with_original_scope(self):
        row=self.assess()
        self.assertEqual(row.verdict,'conditional')
        self.assertEqual(row.basis,'inference')
        self.assertEqual(row.relation_to_technology,'method_family')
        self.assertIn('PF-NIC',row.judgment)
        self.assertNotIn('이 문구로',row.judgment)
        self.assertTrue(row.citations)
        self.assertFalse(row.context_findings)  # 선택한 같은 근거를 이중 출력하지 않는다.

    def test_related_market_cannot_be_promoted_to_productization_or_adoption(self):
        for criterion in ('commercialization','adoption'):
            with self.subTest(criterion=criterion):
                self.assertEqual(self.assess(criterion).verdict,'unknown')

    def test_related_fact_does_not_become_selected_technology_fact(self):
        row=self.assess(basis='fact')
        self.assertEqual(row.verdict,'conditional')
        self.assertEqual(row.basis,'inference')
        self.assertNotIn('이 문구로',row.judgment)

    def test_related_inference_needs_conditions(self):
        row=self.assess()
        row.conditions=[]
        result,_=validate_analysis(self.data,Analysis(assessments=[row],followup_questions=[]),{self.web.id:self.web})
        self.assertEqual(next(r for r in result.assessments if r.criterion_id==row.criterion_id and r.tech_id==row.tech_id).basis,'unknown')

    def test_consuming_last_call_does_not_make_a_reviewed_unknown_a_budget_failure(self):
        from market_agent.research import annotate
        from market_agent.schemas import unknown, Limits
        from market_agent.tools import Budget
        row=unknown('HW-01','adoption','직접 채택 근거 없음')
        budget=Budget(Limits(search=6,extract=10,llm=5));budget.used['llm']=5
        result=annotate(Analysis(assessments=[row],followup_questions=[]),self.data,{self.web.id:self.web},
            [],[],budget,True,reviewed={('HW-01','adoption'):[self.web.id]}).assessments[0]
        self.assertNotIn('budget_exhausted',result.unknown_reasons)
        self.assertIn('insufficient_evidence',result.unknown_reasons)

    def test_previous_conditional_assessment_keeps_its_related_claim_reference(self):
        from market_agent.claims import previous_draft
        row=self.assess()
        pool,_=validate_claims(self.data,[self.claim()],{self.web.id:self.web})
        fallback=DraftAnalysis(assessments=[DraftAssessment(tech_id=row.tech_id,criterion_id=row.criterion_id,
            judgment='미확인',verdict='unknown',basis='unknown',claim_ids=[],conditions=[],gaps=[])],followup_questions=[])
        recovered=previous_draft(Analysis(assessments=[row],followup_questions=[]),pool,fallback)
        self.assertEqual(set(recovered.assessments[0].claim_ids),set(pool))
        self.assertEqual(recovered.assessments[0].basis,'inference')
