import unittest
from market_agent.tests import test_claims
from market_agent.schemas import DraftAnalysis, MarketResult
from market_agent.claims import validate_claims, materialize
from market_agent.revalidate import revalidate

class RevalidateTests(unittest.TestCase):
    setUp=test_claims.ClaimTests.setUp
    claim=test_claims.ClaimTests.claim
    def test_revalidation_removes_scope_overreach_without_new_calls(self):
        c=self.claim(statement='장치는 CXL 3.1을 지원한다.')
        pool,_=validate_claims(self.data,[c],{self.web.id:self.web})
        analysis,_=materialize(self.data,DraftAnalysis(assessments=[],followup_questions=[]),pool)
        result=MarketResult(status='unknown',round=1,assessments=analysis.assessments,followup_questions=[],
            technology_status={'SW-01':'unknown','HW-01':'unknown'},errors=[],usage={'search':6,'extract':10,'llm':5},mode='live')
        saved={'input':self.data.model_dump(),'result':result.model_dump(),'evidence':{self.web.id:self.web.model_dump()},
            'claim_pool':{k:c.model_dump() for k,c in pool.items()},'queries':[],'events':[],'token_usage':[], 'model':'fixture'}
        state=revalidate(saved,{})
        self.assertEqual(state['result'].usage,result.usage)
        self.assertFalse(state['claim_pool'])
        self.assertTrue(all(not r.context_findings for r in state['result'].assessments))
        self.assertIn('local_scope_revalidation',state['history'])
