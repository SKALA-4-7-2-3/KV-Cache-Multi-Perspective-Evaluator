import unittest
from pathlib import Path

from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.report import render_report
from market_agent.schemas import CRITERIA, Citation, ContextFinding


class ReportTests(unittest.TestCase):
    def test_model_synthesis_limitations_are_delivered_for_provisional_rows(self):
        from market_agent.providers import AdaptiveFixtureAnalyst
        state = run_market(read_input(Path(__file__).parents[1]/'fixtures/input.md'), FixtureWeb(), AdaptiveFixtureAnalyst(), mode='fixture')
        row = state['result'].assessments[0]
        row.evaluation_mode = 'provisional'
        row.gaps = ['자료에는 지역별 집계 기준과 발행 연도가 없다']
        self.assertEqual(row.generation_method, 'model_synthesis')
        self.assertIn(row.gaps[0], render_report(state))

    def test_only_owned_rows_and_cited_context_sources_are_delivered(self):
        state = run_market(read_input(Path(__file__).parents[1]/'fixtures/input.md'), FixtureWeb(), FixtureAnalyst(), mode='fixture')
        e = next(e for e in state['evidence'].values() if e.access_status == 'full_text')
        row = state['result'].assessments[0]
        row.context_findings = [ContextFinding(statement='합성 기술군 보조 정보', basis='fact', relation_to_technology='method_family',
            conditions=['선정 논문과 연결 미확인'], citations=[Citation(evidence_id=e.id, quote='파이프라인 검사용 응답이다.',
                subject='테스트 기술군', source_character='합성 테스트 자료', locator='본문')])]
        text = render_report(state)
        for criterion in CRITERIA:
            self.assertEqual(text.count(f'`{criterion}`'), 2)
        self.assertIn('합성 기술군', text)
        self.assertIn(e.id, text)
        self.assertIn('E-SW-001', text)
        self.assertIn('E-HW-001', text)
        self.assertIn('## 평가 참고자료', text)
        self.assertNotIn('| unknown |', text)
        for forbidden in ['## 실행 정보', '## 두 기술 비교', '## 미확인 사항과 보완 질문', 'API', 'SUMMARY']:
            self.assertNotIn(forbidden, text)
        self.assertIn('## 인용 근거', text)
