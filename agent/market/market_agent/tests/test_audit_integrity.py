"""최종 audit의 예약 예산과 후속 호출의 오류 수명주기를 검사한다."""
import unittest
from datetime import date
from pathlib import Path

from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.schemas import Citation, Claim, Evidence, Extraction, Limits, SourceReview
from market_agent.tools import Budget, ProviderError


class EmptyWeb(FixtureWeb):
    def search(self, query, as_of):
        return []

    def extract(self, url):
        raise AssertionError('이 테스트는 주입한 합성 원문만 사용합니다')


class SuccessfulAudit(FixtureAnalyst):
    def audit(self, data, claims):
        return FixtureAnalyst.compose(self, data, claims)


class AuditIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1] / 'fixtures/input.md')
        for technology in self.data.technologies.values():
            technology.url = ''
        self.source = Evidence(
            id='MKT-audit', doc_id='DOC-audit', title='Synthetic PF-NIC support',
            url='https://example.org/audit', published_at=date(2026, 9, 1),
            excerpt='PF-NIC supports CXL shared memory for AI inference.',
            access_status='full_text', content_status='substantive',
            tech_ids=['HW-01'], criteria=['ecosystem_support'],
        )
        self.claim = Claim(
            tech_id='HW-01', criterion_id='ecosystem_support',
            statement='합성 공급사는 PF-NIC의 CXL 공유 메모리 지원을 설명한다.',
            basis='fact', relation_to_technology='method_family',
            conditions=['선정 논문과의 동일성 미확인; 실제 시장 사실이 아닌 합성 자료'],
            metric=None,
            citation=Citation(
                evidence_id=self.source.id, quote=self.source.excerpt,
                subject='PF-NIC', source_character='합성 공급사 설명',
            ),
        )

    def test_compose_transport_retry_cannot_spend_reserved_audit_attempt(self):
        class RetryableComposition(FixtureAnalyst):
            def compose(self, data, claims, previous=None, issues=None):
                raise ProviderError('synthetic_transport', retryable=True)

            def audit(self, data, claims):
                draft = FixtureAnalyst.compose(self, data, claims)
                for review in draft.claim_reviews:
                    review.supported = False
                    review.reason = '최종 합성 검토에서 근거 범위 과장을 확인함'
                return draft

        self.data.limits = Limits(search=0, extract=0, llm=2)
        state = run_market(
            self.data, EmptyWeb(), RetryableComposition(),
            existing_evidence={self.source.id: self.source}, existing_claims={'prior': self.claim},
            auto_repair=False, mode='fixture',
        )

        self.assertEqual(state['result'].usage['llm'], 2)
        self.assertFalse(any(row.context_findings for row in state['result'].assessments),
                         'audit에 예약된 예산이 남아야 최종 기각이 결과에 반영됩니다')
        self.assertFalse(any(error['stage'] == 'llm_audit' for error in state['result'].errors))

    def test_successful_audit_clears_only_previous_audit_errors(self):
        self.data.limits = Limits(search=0, extract=0, llm=3)
        progress = {
            'errors': [
                {'stage': 'llm_audit', 'code': 'synthetic_old_transport', 'scope': 'global'},
                {'stage': 'audit', 'code': 'missing_claim_review',
                 'tech_id': 'HW-01', 'criterion_id': 'ecosystem_support'},
                {'stage': 'extract', 'code': 'unresolved_other_source',
                 'tech_id': 'SW-01', 'criterion_id': 'adoption'},
            ],
            'model_successes': 1,
        }
        state = run_market(
            self.data, EmptyWeb(), SuccessfulAudit(),
            existing_evidence={self.source.id: self.source}, existing_claims={'prior': self.claim},
            previous_progress=progress, round_number=1, auto_repair=False, mode='fixture',
        )

        self.assertTrue(any(row.context_findings for row in state['result'].assessments))
        self.assertFalse(any(error['stage'] in {'audit', 'llm_audit'} for error in state['result'].errors))
        self.assertTrue(any(error['code'] == 'unresolved_other_source' for error in state['result'].errors),
                        '다른 자료 수집 단계의 미해결 오류까지 지우면 안 됩니다')

    def test_resume_without_calls_preserves_audit_validation_error_and_partial_status(self):
        source, claim = self.source, self.claim

        class MissingAuditReview(FixtureAnalyst):
            def extract(self, data, evidence, previous=None, issues=None):
                return Extraction(claims=[claim], reviews=[SourceReview(
                    evidence_id=source.id, outcome='claims_extracted',
                    reason='합성 후보 추출', criteria=source.criteria,
                )])

            def audit(self, data, claims):
                draft = FixtureAnalyst.compose(self, data, claims)
                draft.claim_reviews = []
                return draft

        self.data.limits = Limits(search=6, extract=0, llm=5)
        budget = Budget(self.data.limits)
        first = run_market(
            self.data, EmptyWeb(), MissingAuditReview(), budget=budget,
            existing_evidence={source.id: source}, mode='fixture',
        )
        self.assertEqual(first['result'].execution_status, 'partial')
        self.assertTrue(any(error['code'] == 'missing_claim_review' for error in first['result'].errors))
        budget.constrain(Limits(**budget.used))

        second = run_market(
            self.data, EmptyWeb(), MissingAuditReview(), budget=budget,
            previous=first['analysis'], existing_evidence=first['evidence'],
            round_number=1, auto_repair=False, mode='fixture',
        )

        self.assertEqual(second['result'].usage, first['result'].usage)
        self.assertEqual(second['result'].execution_status, 'partial')
        self.assertTrue(any(error['code'] == 'missing_claim_review' for error in second['result'].errors),
                        '새 audit가 없으면 최종 검토 누락 오류를 해소할 수 없습니다')


if __name__ == '__main__':
    unittest.main()
