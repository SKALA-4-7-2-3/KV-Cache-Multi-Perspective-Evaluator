"""부모 후속 호출이 미해결 오류와 이미 완료한 원문 검토를 보존하는지 검사한다."""
import unittest
from datetime import date
from pathlib import Path

from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.schemas import (
    CRITERIA, Citation, Claim, Evidence, Extraction, Limits, SourceReview,
)
from market_agent.tools import Budget


class NoRemoteSources(FixtureWeb):
    def search(self, query, as_of):
        return []

    def extract(self, url):
        raise AssertionError('주입한 합성 원문 외에는 조회하지 않아야 합니다')


class ResumeIntegrityTests(unittest.TestCase):
    def setUp(self):
        fixtures = Path(__file__).parents[1] / 'fixtures'
        data = read_input(
            [fixtures / 'paper_analysis_sw.json', fixtures / 'paper_analysis_hw.json'],
            as_of='2026-09-22',
        )
        self.data = data.model_copy(update={
            'limits': Limits(search=6, extract=0, llm=3),
            'technologies': {
                key: value.model_copy(update={'url': ''})
                for key, value in data.technologies.items()
            },
        })
        self.source = Evidence(
            id='MKT-resume', doc_id='DOC-resume', title='Synthetic resume source',
            url='https://example.org/resume', published_at=date(2026, 9, 1),
            excerpt='Acme CXL memory supports pooled capacity for AI inference.',
            access_status='full_text', content_status='substantive',
            tech_ids=['HW-01'], criteria=list(CRITERIA),
        )

    def test_resume_without_available_calls_does_not_clear_unresolved_error_or_become_completed(self):
        e = self.source

        class InvalidQuote(FixtureAnalyst):
            def extract(self, data, evidence, previous=None, issues=None):
                claim = Claim(
                    tech_id='HW-01', criterion_id='business_value',
                    statement='합성 자료의 공유 용량 지원 주장', basis='fact',
                    relation_to_technology='method_family', conditions=['합성 자료'], metric=None,
                    citation=Citation(
                        evidence_id=e.id, quote='An invented claim with no source support.',
                        subject='Acme CXL memory', source_character='합성 테스트 자료',
                    ),
                )
                return Extraction(claims=[claim], reviews=[SourceReview(
                    evidence_id=e.id, outcome='claims_extracted',
                    reason='후속 검증에서 기각되어야 하는 후보', criteria=list(CRITERIA),
                )])

        budget = Budget(self.data.limits)
        first = run_market(
            self.data, NoRemoteSources(), InvalidQuote(), budget=budget,
            existing_evidence={e.id: e}, mode='fixture',
        )
        self.assertEqual(first['result'].execution_status, 'partial')
        self.assertTrue(any(error['code'] == 'missing_or_invalid_quote'
                            for error in first['result'].errors))
        self.assertTrue(all(row.search_ids for row in first['result'].assessments))
        # 부모가 남은 역할 예산을 회수했을 때는 기존 오류를 해소할 새 시도가 없다.
        budget.constrain(Limits(**budget.used))
        used_before_resume = dict(budget.used)

        second = run_market(
            self.data, NoRemoteSources(), InvalidQuote(), budget=budget,
            round_number=1, auto_repair=False, previous=first['analysis'],
            existing_evidence=first['evidence'], mode='fixture',
        )

        self.assertEqual(second['result'].usage, used_before_resume)
        with self.subTest(contract='unresolved_error'):
            self.assertTrue(any(error['code'] == 'missing_or_invalid_quote'
                                for error in second['result'].errors))
        with self.subTest(contract='execution_status'):
            self.assertEqual(second['result'].execution_status, 'partial')

    def test_resume_preserves_composition_error_without_a_new_review(self):
        progress={'errors':[{'stage':'compose','code':'missing_claim_review','tech_id':'HW-01',
            'criterion_id':'business_value'}], 'composition_errors':[{'stage':'compose',
            'code':'missing_claim_review','tech_id':'HW-01','criterion_id':'business_value'}]}
        state=run_market(self.data,NoRemoteSources(),FixtureAnalyst(),round_number=1,
            auto_repair=False,previous_progress=progress,mode='fixture')
        self.assertIn('missing_claim_review',[e['code'] for e in state['result'].errors])
        self.assertEqual(state['result'].execution_status,'partial')

    def test_resume_keeps_reviewed_source_ids_without_another_model_call(self):
        e = self.source

        class ReviewedButInsufficient(FixtureAnalyst):
            def extract(self, data, evidence, previous=None, issues=None):
                return Extraction(claims=[], reviews=[SourceReview(
                    evidence_id=e.id, outcome='no_market_claim',
                    reason='원문을 검토했지만 선정 논문의 시장 실적은 입증하지 못함',
                    criteria=list(CRITERIA),
                )])

        budget = Budget(self.data.limits)
        first = run_market(
            self.data, NoRemoteSources(), ReviewedButInsufficient(), budget=budget,
            existing_evidence={e.id: e}, mode='fixture',
        )
        first_row = next(row for row in first['result'].assessments
                         if (row.tech_id, row.criterion_id) == ('HW-01', 'business_value'))
        self.assertEqual(first_row.research_status, 'reviewed')
        self.assertEqual(first_row.reviewed_evidence_ids, [e.id])
        used_before_resume = dict(budget.used)

        second = run_market(
            self.data, NoRemoteSources(), ReviewedButInsufficient(), budget=budget,
            round_number=1, auto_repair=False, previous=first['analysis'],
            existing_evidence=first['evidence'],
            previous_progress=first['result'].model_dump(mode='json')['progress'],
            mode='fixture',
        )
        second_row = next(row for row in second['result'].assessments
                          if (row.tech_id, row.criterion_id) == ('HW-01', 'business_value'))

        self.assertEqual(second['result'].usage, used_before_resume)
        with self.subTest(contract='research_status'):
            self.assertEqual(second_row.research_status, 'reviewed')
        with self.subTest(contract='reviewed_sources'):
            self.assertEqual(second_row.reviewed_evidence_ids, [e.id])
        self.assertNotIn('not_searched', second_row.unknown_reasons)


if __name__ == '__main__':
    unittest.main()
