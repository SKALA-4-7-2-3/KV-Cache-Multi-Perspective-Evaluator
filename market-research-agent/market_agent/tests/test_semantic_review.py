import unittest
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Claim, Citation


class SemanticReviewTests(unittest.TestCase):
    def test_market_irrelevant_claim_is_rejected_even_when_quote_matches(self):
        from market_agent.claims import review_claims
        from market_agent.schemas import ClaimReview
        review=ClaimReview(claim_id='A',supported=True,reason='실험 수식만 설명함',market_relevant=False)
        pool,log,errors=review_claims({'A':self.claim},[review])
        self.assertFalse(pool)
        self.assertIn('rejected',log['A'])

    def test_planned_benefit_is_preserved_as_inference_with_conditions(self):
        from market_agent.claims import review_claims
        from market_agent.schemas import ClaimReview
        review=ClaimReview(claim_id='A',supported=True,reason='실측 고객 자료 없는 전망',evidence_level='projection')
        pool,_,_=review_claims({'A':self.claim},[review])
        self.assertEqual(pool['A'].basis,'inference')
        self.assertTrue(pool['A'].conditions)

    def test_other_product_does_not_become_exact_because_paper_is_mentioned(self):
        from market_agent.validation import identity_supported
        from market_agent.schemas import Evidence
        e=Evidence(id='E',doc_id='D',title='Related product',url='https://example.org',access_status='full_text',
            excerpt='RDKV is another approach. Product-X is commercially available.')
        cite=Citation(evidence_id='E',quote='Product-X is commercially available.',subject='Product-X',
            identity_quote='RDKV',source_character='합성 자료')
        self.assertFalse(identity_supported(self.data.technologies['SW-01'],[cite],{'E':e}))

    def setUp(self):
        self.data = read_input(Path(__file__).parents[1] / 'fixtures/input.md')
        self.claim = Claim(tech_id='SW-01', criterion_id='business_value',
            statement='연구 저자는 메모리 절약을 설명한다.', basis='fact', relation_to_technology='exact',
            citation=Citation(evidence_id='MKT-X', quote='RDKV reduces memory usage.',
                subject='RDKV', source_character='연구 저자 주장'), conditions=['실제 비용 절감 미검증'], metric=None)

    def test_unreviewed_or_rejected_claim_cannot_reach_context(self):
        from market_agent.claims import review_claims
        from market_agent.schemas import ClaimReview
        pool, log, errors = review_claims({'A': self.claim, 'B': self.claim}, [
            ClaimReview(claim_id='A', supported=False, reason='인용은 batching만 설명하며 메모리 병목은 입증하지 않음')])
        self.assertFalse(pool)
        self.assertIn('rejected', log['A'])
        self.assertTrue(any(e['code']=='missing_claim_review' for e in errors))

    def test_accepted_claim_does_not_inherit_broader_composer_prose(self):
        from market_agent.claims import materialize
        from market_agent.providers import FixtureAnalyst
        draft = FixtureAnalyst().compose(self.data, {'A': self.claim})
        row = next(r for r in draft.assessments if (r.tech_id,r.criterion_id)==('SW-01','business_value'))
        row.basis, row.verdict, row.claim_ids = 'fact', 'conditional', ['A']
        row.judgment = '운영 비용이 절반으로 줄었고 실제 고객이 도입했다.'
        result, _ = materialize(self.data,draft,{'A':self.claim})
        actual = next(r for r in result.assessments if (r.tech_id,r.criterion_id)==('SW-01','business_value'))
        self.assertEqual(actual.judgment,self.claim.statement)

    def test_modal_source_cannot_be_promoted_to_observed_fact(self):
        from market_agent.quotes import resolve_quotes
        from market_agent.schemas import SelectedClaim, SelectedExtraction, Evidence
        e = Evidence(id='E',doc_id='D',title='RDKV',url='https://example.org',
            excerpt='RDKV could reduce serving cost for large deployments.',access_status='full_text')
        c = SelectedClaim(tech_id='SW-01',criterion_id='business_value',statement='저자는 비용 절감 가능성을 제시한다.',
            basis='fact',relation_to_technology='exact',quote_id='Q',subject='RDKV',conditions=[],metric=None)
        result = resolve_quotes(self.data,SelectedExtraction(claims=[c],reviews=[]),
            {'Q':{'evidence_id':'E','text':e.excerpt,'locator':'abstract'}},{'E':e})
        self.assertEqual(result.claims[0].basis,'inference')
        self.assertTrue(result.claims[0].conditions)

    def test_quote_selection_keeps_complete_sentences(self):
        from market_agent.quotes import quote_bank
        from market_agent.schemas import Evidence
        body = 'The new shared memory product supports enterprise inference deployments with large contexts and includes software interfaces that customers can evaluate before deciding on a production deployment.'
        e = Evidence(id='E',doc_id='D',title='Product',url='https://example.org',excerpt=body,
            access_status='full_text',content_status='substantive')
        bank = quote_bank({'E':e})
        self.assertEqual([v['text'] for v in bank.values()],[body])
