"""독립 검토에서 재현한 출처 연결·인용 손실·수치·추론의 회귀 검사."""
import unittest
from datetime import date
from pathlib import Path

from market_agent.claims import materialize, review_claims, validate_claims
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst
from market_agent.quotes import quote_bank, resolve_quotes
from market_agent.schemas import (
    ClaimReview, Evidence, Metric, SelectedClaim, SelectedExtraction,
)
from market_agent.validation import validate_analysis


class ReviewFindingTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1] / 'fixtures/input.md')

    def source(self, text, tech_id='SW-01'):
        return Evidence(
            id='E', doc_id='D', title='Synthetic review source',
            url='https://example.org/review', excerpt=text,
            access_status='full_text', content_status='substantive',
            published_at=date(2026, 9, 1), tech_ids=[tech_id],
        )

    def selected(self, quote_id, **updates):
        values = dict(
            tech_id='SW-01', criterion_id='commercialization',
            statement='합성 주장: RDKV 제품을 구매할 수 있다.',
            basis='fact', relation_to_technology='exact', quote_id=quote_id,
            subject='RDKV', conditions=['합성 자료이며 실제 시장 정보가 아님'], metric=None,
        )
        values.update(updates)
        return SelectedExtraction(claims=[SelectedClaim(**values)], reviews=[])

    def test_remote_technology_mention_cannot_make_another_products_quote_exact(self):
        text = (
            'RDKV is mentioned only as an unrelated research approach.\n\n'
            + 'This paragraph is unrelated to the product. ' * 20
            + '\n\nProduct-X is commercially available to enterprise customers.'
        )
        e = self.source(text)
        bank = quote_bank({'E': e})
        quote_id = next(key for key, value in bank.items() if value['text'].startswith('Product-X'))
        self.assertNotIn('RDKV', bank[quote_id]['context'])

        claims = resolve_quotes(self.data, self.selected(quote_id), bank, {'E': e}).claims
        pool, errors = validate_claims(self.data, claims, {'E': e})

        self.assertFalse(pool, '문서의 다른 부분에 있는 RDKV 언급을 직접 동일성으로 사용함')
        self.assertTrue(errors)

    def test_product_announcement_with_markdown_link_remains_an_exact_source_quote(self):
        text = ('Marvell announced [Structera](https://example.org/structera) '
                'CXL memory controllers for AI infrastructure.')
        e = self.source(text, 'HW-01')

        bank = quote_bank({'E': e})

        self.assertIn(text, [entry['text'] for entry in bank.values()],
                      '제품명 링크가 있는 실질적 발표 문장을 누락하거나 원문을 변조함')

    def market_metric(self):
        return Metric(
            value=5, unit='billion', currency='USD', year='2030',
            market_definition='CXL memory market', geography='global',
            actual_or_forecast='forecast',
        )

    def metric_claim(self, e, subject):
        bank = quote_bank({'E': e})
        selected = self.selected(
            next(iter(bank)), tech_id='HW-01', criterion_id='market_size_growth',
            statement='합성 전망: 2030년 세계 CXL 메모리 시장은 5 billion USD이다.',
            relation_to_technology='method_family', subject=subject, metric=self.market_metric(),
        )
        return resolve_quotes(self.data, selected, bank, {'E': e}).claims

    def test_controller_count_cannot_support_invented_market_currency_year_and_scope(self):
        e = self.source(
            'Product-X supports CXL memory expansion with 5 controller units for AI inference.',
            'HW-01',
        )

        pool, errors = validate_claims(self.data, self.metric_claim(e, 'Product-X'), {'E': e})

        self.assertFalse(pool, '숫자가 같다는 이유만으로 시장 정의·단위·연도를 지어낼 수 없음')
        self.assertTrue(any(error['code'] == 'unsupported_metric' for error in errors))

    def test_complete_market_forecast_quote_preserves_the_supported_metric(self):
        e = self.source(
            'The global CXL memory market is forecast to reach USD 5 billion in 2030.',
            'HW-01',
        )

        pool, errors = validate_claims(self.data, self.metric_claim(e, 'CXL memory market'), {'E': e})

        self.assertFalse(errors)
        self.assertEqual(len(pool), 1)
        self.assertEqual(next(iter(pool.values())).metric, self.market_metric())

    def test_projection_review_conservatively_downgrades_fact_row_without_losing_the_claim(self):
        e = self.source('RDKV reduces the energy consumption of inference deployments.')
        bank = quote_bank({'E': e})
        selected = self.selected(
            next(iter(bank)), criterion_id='business_value',
            statement='합성 연구 저자는 추론 에너지 절감 가능성을 전망한다.',
        )
        candidates, errors = validate_claims(
            self.data, resolve_quotes(self.data, selected, bank, {'E': e}).claims, {'E': e},
        )
        self.assertFalse(errors)
        key = next(iter(candidates))
        draft = FixtureAnalyst().compose(self.data, candidates)
        row = next(row for row in draft.assessments
                   if (row.tech_id, row.criterion_id) == ('SW-01', 'business_value'))
        row.basis, row.verdict, row.claim_ids = 'fact', 'conditional', [key]
        reviewed, _, _ = review_claims(candidates, [ClaimReview(
            claim_id=key, supported=True, reason='고객 실적이 없는 전망이므로 추론으로 한정',
            evidence_level='projection',
        )])

        analysis, errors = materialize(self.data, draft, reviewed)
        result, validation_errors = validate_analysis(self.data, analysis, {'E': e})
        row = next(row for row in result.assessments
                   if (row.tech_id, row.criterion_id) == ('SW-01', 'business_value'))

        self.assertEqual(row.basis, 'inference')
        self.assertEqual(row.verdict, 'conditional')
        self.assertEqual(row.evidence_ids, ['E'])
        self.assertEqual(row.judgment, reviewed[key].statement)
        self.assertTrue(set(reviewed[key].conditions).issubset(row.conditions))
        self.assertFalse(errors + validation_errors)


if __name__ == '__main__':
    unittest.main()
