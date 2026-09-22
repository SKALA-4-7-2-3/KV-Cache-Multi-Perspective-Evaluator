"""수량 단위를 정규화하되 생산량·생산능력·시장금액의 의미를 섞지 않는다."""
import unittest
from datetime import date

from market_agent.schemas import Citation, Evidence, Metric
from market_agent.validation import metric_supported


PRODUCTION_QUOTE = (
    'In 2025, global production of CXL Memory Expansion Modules reached approximately '
    '1.44 million units, while worldwide production capacity was estimated at around '
    '1.90 million units.'
)
REVENUE_QUOTE = 'The global CXL memory market is forecast to reach USD 5 billion in 2030.'


class MetricNormalizationTests(unittest.TestCase):
    def supports(self, quote, metric):
        source = Evidence(
            id='MKT-metric', doc_id='WEB-metric', title='Synthetic quantity fixture',
            url='https://example.org/quantity-fixture', published_at=date(2026, 9, 1),
            excerpt=quote, access_status='full_text', content_status='substantive',
            tech_ids=['HW-01'],
        )
        citation = Citation(
            evidence_id=source.id, quote=quote,
            subject='CXL Memory Expansion Modules' if quote == PRODUCTION_QUOTE else 'CXL memory market',
            source_character='합성 수량 검증 자료',
        )
        return metric_supported(metric, [citation], {source.id: source})

    def production_metric(self, **updates):
        fields = dict(
            value=1440000, unit='units', currency=None, year='2025',
            market_definition='Global production volume of CXL Memory Expansion Modules',
            geography='global', actual_or_forecast='actual',
        )
        fields.update(updates)
        return Metric(**fields)

    def revenue_metric(self, **updates):
        fields = dict(
            value=5, unit='billion', currency='USD', year='2030',
            market_definition='CXL memory market', geography='global',
            actual_or_forecast='forecast',
        )
        fields.update(updates)
        return Metric(**fields)

    def test_million_units_production_supports_both_scaled_and_base_unit_values(self):
        for value, unit in [(1.44, 'million units'), (1440000, 'units')]:
            with self.subTest(value=value, unit=unit):
                self.assertTrue(self.supports(
                    PRODUCTION_QUOTE, self.production_metric(value=value, unit=unit),
                ))

    def test_production_capacity_does_not_become_production_volume(self):
        for value, unit in [(1.90, 'million units'), (1900000, 'units')]:
            with self.subTest(value=value, unit=unit):
                self.assertFalse(self.supports(
                    PRODUCTION_QUOTE, self.production_metric(value=value, unit=unit),
                ))

    def test_production_volume_does_not_become_production_capacity(self):
        for value, unit in [(1.44, 'million units'), (1440000, 'units')]:
            with self.subTest(value=value, unit=unit):
                self.assertFalse(self.supports(PRODUCTION_QUOTE, self.production_metric(
                    value=value, unit=unit,
                    market_definition='Global production capacity of CXL Memory Expansion Modules',
                )))

    def test_production_quantity_cannot_become_money_or_total_addressable_market(self):
        variants = [
            self.production_metric(
                unit='USD', currency='USD',
                market_definition='Global market revenue of CXL Memory Expansion Modules',
            ),
            self.production_metric(
                market_definition='Global total addressable market of CXL Memory Expansion Modules',
            ),
        ]
        for metric in variants:
            with self.subTest(definition=metric.market_definition):
                self.assertFalse(self.supports(PRODUCTION_QUOTE, metric))

    def test_normalized_production_preserves_year_geography_and_actual_status(self):
        for changed in [
            {'year': '2024'},
            {'geography': 'United States'},
            {'actual_or_forecast': 'forecast'},
        ]:
            with self.subTest(changed=changed):
                self.assertFalse(self.supports(PRODUCTION_QUOTE, self.production_metric(**changed)))

    def test_billion_dollars_supports_scaled_and_base_currency_values(self):
        for value, unit in [(5, 'billion'), (5000000000, 'USD')]:
            with self.subTest(value=value, unit=unit):
                self.assertTrue(self.supports(
                    REVENUE_QUOTE, self.revenue_metric(value=value, unit=unit),
                ))

    def test_billion_dollars_cannot_become_wrong_scale_currency_units_or_actual(self):
        for changed in [
            {'value': 5000000, 'unit': 'USD'},
            {'currency': 'EUR'},
            {'value': 5000000000, 'unit': 'units', 'currency': None},
            {'actual_or_forecast': 'actual'},
        ]:
            with self.subTest(changed=changed):
                self.assertFalse(self.supports(REVENUE_QUOTE, self.revenue_metric(**changed)))

    def test_unit_currency_and_definition_must_match_including_non_english_scope(self):
        for changed in [
            {'unit':'EUR'},
            {'market_definition':'국내 클라우드 매출'},
            {'market_definition':'CXL memory market 국내 매출'},
        ]:
            with self.subTest(changed=changed):
                self.assertFalse(self.supports(REVENUE_QUOTE,self.revenue_metric(**changed)))

    def test_other_subject_quantity_in_same_quote_is_not_reused(self):
        quote='In 2025, global production of Module A reached 1.44 million units, while production of Module B reached 1.90 million units.'
        self.assertFalse(self.supports(quote,self.production_metric(value=1900000,
            market_definition='Global production of Module A')))


if __name__ == '__main__':
    unittest.main()
