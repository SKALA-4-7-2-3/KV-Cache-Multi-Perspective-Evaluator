import unittest
from market_agent.tests import test_claims
from market_agent.node import run_market
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.schemas import Limits, Extraction, SourceReview

class AuditTests(unittest.TestCase):
    setUp=test_claims.ClaimTests.setUp
    claim=test_claims.ClaimTests.claim
    def test_final_rejection_removes_previously_accepted_context_within_budget(self):
        source=self.web;claim=self.claim()
        class Analyst(FixtureAnalyst):
            def extract(self,data,evidence,previous=None,issues=None):
                return Extraction(claims=[claim],reviews=[SourceReview(evidence_id=source.id,
                    outcome='claims_extracted',reason='합성 검사',criteria=['ecosystem_support'])])
            def audit(self,data,claims):
                answer=self.compose(data,claims)
                for review in answer.claim_reviews:review.supported=False;review.reason='최종 검토에서 범위 과장 확인'
                return answer
        data=self.data.model_copy(deep=True);data.limits=Limits(search=0,extract=0,llm=3)
        for tech in data.technologies.values():tech.url=''
        state=run_market(data,FixtureWeb(),Analyst(),existing_evidence={source.id:source},mode='fixture')
        self.assertEqual(state['result'].usage['llm'],3)
        self.assertIn('audit',state['history'])
        self.assertFalse(state['claim_pool'])
        self.assertTrue(all(not r.context_findings for r in state['result'].assessments))
