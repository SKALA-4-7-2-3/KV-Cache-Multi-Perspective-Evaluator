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
    def test_benchmark_is_not_official_integration(self):
        self.assertFalse(self.check('ecosystem_support','CQ improves inference throughput relative to existing baselines.'))

    def test_formula_is_not_customer_value(self):
        self.assertFalse(self.check('business_value','RDKV computes bit allocation by a reverse water-filling solution.'))
    def test_translated_month_preserves_a_valid_standard_release(self):
        c=self.claim.model_copy(deep=True);c.criterion_id='standardization'
        c.statement='2020년 11월 CXL 2.0 규격을 발표했다.'
        c.citation.quote='In November 2020, the CXL Consortium announced the CXL 2.0 specification.'
        self.assertTrue(review_claims({'A':c},[ClaimReview(claim_id='A',supported=True,reason='유효한 번역')])[0])

    def test_backend_support_note_is_not_a_standard(self):
        self.assertFalse(self.check('standardization','Per-attention-head quantization is supported only with Flash Attention.'))

    def test_numbers_from_context_cannot_be_added_to_the_selected_quote(self):
        c=self.claim.model_copy(deep=True);c.statement='제품은 CXL 3.1을 지원한다.'
        c.citation.quote='The product supports shared memory frameworks.'
        c.citation.context='The other adapter supports CXL 3.1.'
        self.assertFalse(review_claims({'A':c},[ClaimReview(claim_id='A',supported=True,reason='허용')])[0])

    def test_generic_accuracy_efficiency_is_not_business_value(self):
        self.assertFalse(self.check('business_value','Our results show better accuracy at no cost to efficiency.'))

    def test_memory_benefit_keeps_research_condition(self):
        c=self.check('business_value','RDKV reduces memory usage for long context inference.')['A']
        self.assertEqual(c.basis,'inference')
        self.assertIn('실제 고객',str(c.conditions))

    def test_hardware_supported_bit_widths_are_not_ecosystem_integration(self):
        self.assertFalse(self.check('ecosystem_support',
            'We allocate hardware-supported bit-widths and realize memory savings with our packed decode kernel.'))
