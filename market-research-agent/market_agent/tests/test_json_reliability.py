"""JSON 실행에서 확인한 조사 상태·보완·예약 예산의 회귀 검사.

합성 제공자만 사용하고 run_market의 최종 평가와 실행 기록을 검사한다.
실제 논문이나 시장에 대한 주장으로 해석할 수 없는 테스트 자료다.
"""
import unittest
from datetime import date
from pathlib import Path

from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.schemas import (
    Citation, Claim, ClaimReview, Evidence, Extraction, Limits, SourceReview,
)
from market_agent.tools import ProviderError


FIXTURES = Path(__file__).parents[1] / 'fixtures'
HW_TEXT = 'Acme CXL memory supports pooled capacity for AI inference.'
SW_TEXT = 'RDKV implementation is available under a research license.'


def json_input(limits):
    data = read_input(
        [FIXTURES / 'paper_analysis_sw.json', FIXTURES / 'paper_analysis_hw.json'],
        as_of='2026-09-22',
    )
    # 논문 직접 조회 대신 아래의 합성 원문을 주입한다.
    technologies = {
        key: tech.model_copy(update={'url': ''})
        for key, tech in data.technologies.items()
    }
    return data.model_copy(update={'limits': limits, 'technologies': technologies})


def source(tech_id='HW-01'):
    return Evidence(
        id='MKT-synthetic-' + tech_id,
        doc_id='DOC-synthetic-' + tech_id,
        title='Synthetic source for ' + tech_id,
        url='https://example.org/synthetic/' + tech_id,
        publisher='example.org',
        published_at=date(2026, 9, 1),
        excerpt=HW_TEXT if tech_id == 'HW-01' else SW_TEXT,
        access_status='full_text',
        content_status='substantive',
        tech_ids=[tech_id],
    )


def claim_for(evidence):
    is_hw = evidence.tech_ids == ['HW-01']
    return Claim(
        tech_id='HW-01' if is_hw else 'SW-01',
        criterion_id='business_value' if is_hw else 'commercialization',
        statement='합성 공급사는 공유 용량 지원을 설명한다.' if is_hw else '합성 자료의 연구용 구현 공개',
        basis='fact',
        relation_to_technology='method_family' if is_hw else 'exact',
        citation=Citation(
            evidence_id=evidence.id,
            quote=evidence.excerpt,
            subject='Acme CXL memory' if is_hw else 'RDKV',
            source_character='합성 테스트 자료',
        ),
        conditions=['테스트 전용 자료이며 실제 제품 실적을 나타내지 않음'],
        metric=None,
    )


class NoSearchResults(FixtureWeb):
    def search(self, query, as_of):
        return []

    def extract(self, url):
        raise AssertionError('이 테스트는 주입한 합성 원문만 사용해야 합니다')


class JsonReliabilityTests(unittest.TestCase):
    def test_source_review_mismatch_does_not_mark_unrelated_technology_as_failed(self):
        """HW 출처 검토 모순이 SW 여섯 항목의 처리 오류가 되어서는 안 된다."""
        e = source()

        class MismatchedSourceReview(FixtureAnalyst):
            def extract(self, data, evidence, previous=None, issues=None):
                return Extraction(claims=[], reviews=[SourceReview(
                    evidence_id=e.id, outcome='claims_extracted',
                    reason='합성 모순: 후보는 없는데 추출했다고 응답함',
                )])

        state = run_market(
            json_input(Limits(search=0, extract=0, llm=2)),
            NoSearchResults(), MismatchedSourceReview(),
            existing_evidence={e.id: e}, auto_repair=False, mode='fixture',
        )

        sw_rows = [row for row in state['result'].assessments if row.tech_id == 'SW-01']
        self.assertEqual(len(sw_rows), 6)
        self.assertTrue(all('processing_error' not in row.unknown_reasons for row in sw_rows))

    def test_extraction_correction_does_not_skip_market_and_standard_searches(self):
        """인용 교정과 추가 조사는 별개이며 남은 검색 한도를 활용한다."""
        e = source()

        class CorrectedQuote(FixtureAnalyst):
            def __init__(self):
                self.extractions = 0

            def extract(self, data, evidence, previous=None, issues=None):
                self.extractions += 1
                claim = claim_for(e)
                if self.extractions == 1:
                    claim.citation.quote = 'This quote never appeared in the source.'
                return Extraction(claims=[claim], reviews=[SourceReview(
                    evidence_id=e.id, outcome='claims_extracted', reason='합성 후보 검토',
                )])

        state = run_market(
            json_input(Limits(search=6, extract=10, llm=5)),
            NoSearchResults(), CorrectedQuote(),
            existing_evidence={e.id: e}, mode='fixture',
        )

        for row in state['result'].assessments:
            if row.criterion_id in {'market_size_growth', 'standardization'}:
                with self.subTest(technology=row.tech_id, criterion=row.criterion_id):
                    self.assertTrue(row.search_ids, '보완 후에도 필수 조사 목적이 실행되지 않음')
        self.assertLessEqual(state['result'].usage['search'], 6)
        self.assertLessEqual(state['result'].usage['llm'], 5)

    def test_rejected_review_is_reviewed_even_without_an_adopted_claim(self):
        """후보를 읽고 기각한 항목은 조사 미실시와 구분한다."""
        e = source()

        class RejectAfterReview(FixtureAnalyst):
            def extract(self, data, evidence, previous=None, issues=None):
                return Extraction(claims=[claim_for(e)], reviews=[SourceReview(
                    evidence_id=e.id, outcome='claims_extracted', reason='합성 후보를 검토함',
                )])

            def compose(self, data, claims, previous=None, issues=None):
                draft = super().compose(data, claims, previous, issues)
                draft.claim_reviews = [ClaimReview(
                    claim_id=key, supported=False,
                    reason='공유 용량 지원만으로 고객 가치나 비용 효과를 입증할 수 없음',
                ) for key in claims]
                return draft

        state = run_market(
            json_input(Limits(search=0, extract=0, llm=2)),
            NoSearchResults(), RejectAfterReview(),
            existing_evidence={e.id: e}, auto_repair=False, mode='fixture',
        )
        row = next(row for row in state['result'].assessments
                   if (row.tech_id, row.criterion_id) == ('HW-01', 'business_value'))

        self.assertEqual(row.verdict, 'provisional')
        self.assertEqual(row.basis, 'inference')
        self.assertFalse(row.context_findings)
        self.assertEqual(row.research_status, 'reviewed')
        self.assertIn(e.id, row.reviewed_evidence_ids)
        self.assertNotIn('not_searched', row.unknown_reasons)

    def test_extraction_transport_retry_preserves_one_composition_attempt(self):
        """기존 유효 후보가 있으면 추출 재시도 때문에 평가 기회를 잃지 않는다."""
        e = source('SW-01')

        class RetryableExtractionFailure(FixtureAnalyst):
            def extract(self, data, evidence, previous=None, issues=None):
                raise ProviderError('synthetic_transport', retryable=True)

            def compose(self, data, claims, previous=None, issues=None):
                draft = super().compose(data, claims, previous, issues)
                row = next(row for row in draft.assessments
                           if (row.tech_id, row.criterion_id) == ('SW-01', 'commercialization'))
                row.verdict = 'conditional'
                row.basis = 'fact'
                row.claim_ids = list(claims)
                row.conditions = ['합성 테스트의 연구용 라이선스 조건']
                return draft

        state = run_market(
            json_input(Limits(search=0, extract=0, llm=2)),
            NoSearchResults(), RetryableExtractionFailure(),
            existing_evidence={e.id: e}, existing_claims={'previous': claim_for(e)},
            auto_repair=False, mode='fixture',
        )
        row = next(row for row in state['result'].assessments
                   if (row.tech_id, row.criterion_id) == ('SW-01', 'commercialization'))

        self.assertEqual(row.verdict, 'conditional', '추출 재시도가 최종 평가 예산을 소진함')
        self.assertEqual(row.evidence_ids, [e.id])
        self.assertEqual(state['result'].usage['llm'], 2)


if __name__ == '__main__':
    unittest.main()
