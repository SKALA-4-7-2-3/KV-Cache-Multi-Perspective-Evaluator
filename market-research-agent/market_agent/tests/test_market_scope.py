import unittest
from market_agent.tests import test_semantic_review
from market_agent.schemas import ClaimReview
from market_agent.claims import review_claims

class MarketScopeTests(unittest.TestCase):
    setUp=test_semantic_review.SemanticReviewTests.setUp
    def check(self,criterion,quote):
        c=self.claim.model_copy(deep=True);c.criterion_id=criterion;c.citation.quote=quote
        c.citation.source_character='연구 원문 arxiv.org'
        return review_claims({'A':c},[ClaimReview(claim_id='A',supported=True,reason='모델은 허용')])[0]
    def test_benchmark_is_not_product_availability(self):
        self.assertFalse(self.check('commercialization','We evaluate RDKV on five open-source LLMs and LongBench benchmarks.'))
    def test_formula_is_not_customer_value(self):
        self.assertFalse(self.check('business_value','RDKV computes bit allocation by a reverse water-filling solution.'))
    def test_memory_benefit_keeps_research_condition(self):
        c=self.check('business_value','RDKV reduces memory usage for long context inference.')['A']
        self.assertEqual(c.basis,'inference')
        self.assertIn('실제 고객',str(c.conditions))
