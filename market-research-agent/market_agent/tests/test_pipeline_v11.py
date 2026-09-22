import unittest
from pathlib import Path

from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import FixtureWeb, FixtureAnalyst
from market_agent.schemas import Claim, Citation, Extraction, SourceReview, Limits


class ProductWeb(FixtureWeb):
    def extract(self, url):
        return 'PF-NIC supports CXL shared memory for AI inference. Availability is limited to evaluation partners.'


class ProductAnalyst(FixtureAnalyst):
    def extract(self, data, evidence, previous=None, issues=None):
        web=[e for e in evidence.values() if e.access_status=='full_text' and e.content_status=='substantive']
        e=web[0]
        claim=Claim(tech_id='HW-01',criterion_id='ecosystem_support',statement='공급사는 PF-NIC의 CXL 공유 메모리 지원을 설명한다.',
            basis='fact',relation_to_technology='method_family',conditions=['평가용 제공이며 선정 논문과 연결 미확인'],metric=None,
            citation=Citation(evidence_id=e.id,quote='PF-NIC supports CXL shared memory for AI inference.',subject='PF-NIC',source_character='합성 공급사 발표'))
        return Extraction(claims=[claim],reviews=[SourceReview(evidence_id=x.id,
            outcome='claims_extracted' if x.id==e.id else 'no_market_claim',reason='독립된 제품군 정보') for x in web])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.data=read_input(Path(__file__).parents[1]/'fixtures/input.md')

    def test_related_fact_reaches_report_even_when_composer_returns_unknown(self):
        from market_agent.report import render_report
        state=run_market(self.data,ProductWeb(),ProductAnalyst(),mode='fixture')
        row=next(r for r in state['result'].assessments if r.tech_id=='HW-01' and r.criterion_id=='ecosystem_support')
        self.assertEqual(row.verdict,'unknown')
        self.assertEqual(len(row.context_findings),1)
        self.assertIn('PF-NIC',render_report(state))
        self.assertLessEqual(state['result'].usage['llm'],3)
        self.assertIn('included',state['claim_dispositions'].values())

    def test_invalid_quote_is_repaired_from_existing_sources_without_research(self):
        class Repair(ProductAnalyst):
            calls=0
            def extract(self,*args,**kwargs):
                self.calls+=1
                result=super().extract(*args,**kwargs)
                if self.calls==1:result.claims[0].citation.quote='This quote does not exist.'
                return result
        state=run_market(self.data,ProductWeb(),Repair(),mode='fixture')
        self.assertEqual(state['result'].usage['search'],2)
        self.assertEqual(state['result'].usage['llm'],3)
        self.assertFalse(any(e['stage']=='claims' for e in state['result'].errors))
        self.assertTrue(state['claim_pool'])

    def test_metadata_only_pages_do_not_trigger_model(self):
        class Metadata(FixtureWeb):
            def search(self,*args):return []
            def extract(self,url):return '# Title:RDKV\n\n| Cite as | arXiv:2605.08317v1 |\n\n# Access Paper'
        state=run_market(self.data,Metadata(),ProductAnalyst(),mode='fixture')
        self.assertEqual(state['result'].usage['llm'],0)
        self.assertTrue(any('본문' in g for r in state['result'].assessments for g in r.gaps))

    def test_composition_repair_rechecks_candidates_after_missing_reviews(self):
        class Repair(ProductAnalyst):
            calls=0
            def compose(self,*args,**kwargs):
                self.calls+=1
                result=super().compose(*args,**kwargs)
                if self.calls==1:result.claim_reviews=[]
                return result
        # 추가 원문 예산이 없어 의미 검토 누락에 보완 1회를 사용한다.
        data=self.data.model_copy(update={'limits':Limits(search=2,extract=6,llm=5)})
        analyst=Repair()
        state=run_market(data,ProductWeb(),analyst,mode='fixture')
        self.assertEqual(analyst.calls,2)
        self.assertTrue(state['claim_pool'])
        self.assertTrue(any(r.context_findings for r in state['result'].assessments))
        self.assertFalse(any(e['code']=='missing_claim_review' for e in state['result'].errors))

    def test_one_llm_budget_keeps_unreviewed_claim_internal(self):
        data=self.data.model_copy(update={'limits':Limits(search=6,extract=10,llm=1)})
        state=run_market(data,ProductWeb(),ProductAnalyst(),mode='fixture')
        self.assertEqual(state['result'].usage['llm'],1)
        self.assertFalse(any(r.context_findings for r in state['result'].assessments))
        self.assertTrue(state['candidate_pool'])
        self.assertTrue(all(v.startswith('unreviewed') for v in state['claim_dispositions'].values()))
        self.assertTrue(any(e['code'].startswith('budget_') for e in state['result'].errors))

    def test_parent_continuation_preserves_previously_valid_context_with_no_budget(self):
        from market_agent.tools import Budget
        budget=Budget(Limits(search=6,extract=10,llm=2))
        first=run_market(self.data,ProductWeb(),ProductAnalyst(),mode='fixture',budget=budget,auto_repair=False)
        second=run_market(self.data,ProductWeb(),ProductAnalyst(),mode='fixture',budget=budget,auto_repair=False,
            round_number=1,previous=first['analysis'],existing_evidence=first['evidence'])
        self.assertTrue(any(r.context_findings for r in second['result'].assessments))
        self.assertEqual(second['result'].usage['llm'],2)
