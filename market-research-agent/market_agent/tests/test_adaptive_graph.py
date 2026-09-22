import unittest
from pathlib import Path
from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import FixtureWeb,FixtureAnalyst
from market_agent.schemas import Limits,Synthesis,SynthesisRow,SynthesisReviews,SynthesisReview
from market_agent.tools import Budget,ProviderError
from market_agent.cli import save_run,cache_path,fingerprint
from market_agent.revalidate import revalidate
import tempfile,json


class AdaptiveAnalyst(FixtureAnalyst):
    def synthesize(self,data,packet,level,targets,previous=None,issues=None):
        if level<2:return Synthesis(assessments=[])
        rows=[]
        for t,c in targets:
            refs=[q for q,p in packet.items() if t in p['tech_ids'] and p['access_status']=='snippet'][:2]
            if refs:rows.append(SynthesisRow(tech_id=t,criterion_id=c,observation=f'{c}: 공급자의 통합 지원 설명을 검토했다.',
                judgment=f'{c}: 공급자의 연결 경로를 해당 환경에서 실증할 조건으로 도입 후보를 검토한다.',
                quote_ids=refs,relation_to_technology='adjacent',conditions=['검색 발췌이며 실적을 확정하지 않는다.'],limitations=['원문 확인 필요']))
        return Synthesis(assessments=rows)

    def review_synthesis(self,data,draft,packet,level):
        return SynthesisReviews(reviews=[SynthesisReview(tech_id=r.tech_id,criterion_id=r.criterion_id,
            supported=True,relevant=True,scope_preserved=True,uncertainty_preserved=True,reason='합성 자료의 조건부 판단 검사') for r in draft.assessments])


class AdaptiveGraphTests(unittest.TestCase):
    def data(self):
        data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        data.limits=Limits(search=18,extract=0,llm=10)
        return data

    def test_broadest_stage_synthesizes_every_cell_from_snippets(self):
        state=run_market(self.data(),FixtureWeb(),AdaptiveAnalyst(),mode='fixture')
        rows=state['result'].assessments
        self.assertEqual(len(rows),12)
        self.assertTrue(all(r.generation_method=='model_synthesis' for r in rows))
        self.assertTrue(all(r.evaluation_level==2 and r.basis=='inference' for r in rows))
        self.assertEqual(state['result'].execution_status,'completed')
        self.assertEqual({q['research_level'] for q in state['queries']},{0,1,2})
        self.assertTrue(all(r.observation and r.supporting_materials for r in rows))
        self.assertTrue(all(not r.citations for r in rows))

    def test_failure_emits_explicit_fallback_and_preserves_error(self):
        class Broken(AdaptiveAnalyst):
            def synthesize(self,*args,**kwargs):raise ProviderError('test_auth',fatal=True)
        state=run_market(self.data(),FixtureWeb(),Broken(),mode='fixture')
        self.assertEqual(state['result'].execution_status,'failed')
        self.assertEqual(len(state['result'].assessments),12)
        self.assertTrue(all(r.generation_method=='deterministic_fallback' and r.verdict!='unknown' for r in state['result'].assessments))
        self.assertTrue(any(e['code']=='test_auth' for e in state['result'].errors))

    def test_last_level_repairs_failed_rows_with_remaining_budget_without_more_search(self):
        class NeedsCorrection(AdaptiveAnalyst):
            broad_calls=0
            def synthesize(self,data,packet,level,targets,**kwargs):
                if level==2:
                    self.broad_calls+=1
                    if self.broad_calls==1:
                        draft=super().synthesize(data,packet,level,targets,**kwargs)
                        draft.assessments[0].quote_ids=['MAT-invalid']
                        return draft
                return super().synthesize(data,packet,level,targets,**kwargs)
        analyst=NeedsCorrection()
        state=run_market(self.data(),FixtureWeb(),analyst,mode='fixture')
        self.assertTrue(all(r.generation_method=='model_synthesis' for r in state['result'].assessments))
        # 원문 조회가 0이라 단계 0은 모델을 호출하지 않는다. 단계 1/2 + 최종 수정 = 6회.
        self.assertEqual(state['result'].usage['llm'],6)
        self.assertEqual(state['history'].count('collect'),3)
        self.assertEqual(len(state['result'].progress['stage_history'][-1]['targets']),1)
        self.assertFalse(state['result'].errors)

    def test_resume_preserves_model_evaluation_without_new_budget(self):
        data=self.data();budget=Budget(data.limits)
        first=run_market(data,FixtureWeb(),AdaptiveAnalyst(),mode='fixture',budget=budget)
        budget.constrain(Limits(**budget.used))
        second=run_market(data,FixtureWeb(),AdaptiveAnalyst(),mode='fixture',budget=budget,round_number=1,
            previous=first['analysis'],existing_evidence=first['evidence'])
        self.assertEqual(first['result'].usage,second['result'].usage)
        self.assertEqual([r.judgment for r in first['result'].assessments],[r.judgment for r in second['result'].assessments])
        self.assertTrue(all(r.generation_method=='model_synthesis' for r in second['result'].assessments))

    def test_larger_budget_does_not_create_an_unbounded_final_repair_loop(self):
        class RejectAll(AdaptiveAnalyst):
            def synthesize(self,*args,**kwargs):return Synthesis(assessments=[])
        data=self.data();data.limits=Limits(search=18,extract=0,llm=100)
        state=run_market(data,FixtureWeb(),RejectAll(),mode='fixture')
        self.assertEqual(state['history'].count('repair_synthesis'),2)
        self.assertEqual(len(state['result'].assessments),12)
        self.assertEqual(state['result'].execution_status,'partial')

    def test_mixed_verified_and_synthesized_rows_survive_resume_and_revalidation(self):
        from market_agent.schemas import Evidence,Assessment,Citation,Analysis
        data=self.data();budget=Budget(data.limits)
        source=Evidence(id='MKT-legacy',doc_id='DOC-legacy',title='RDKV',url='https://example.org/legacy',
            excerpt='RDKV supports a custom inference integration for serving.',access_status='full_text',content_status='substantive',tech_ids=['SW-01'])
        row=Assessment(tech_id='SW-01',criterion_id='ecosystem_support',judgment='기존에 검토된 RDKV 연결 경로',
            basis='inference',relation_to_technology='exact',evidence_ids=[source.id],conditions=['환경 검증 필요'],metric=None,gaps=[],verdict='conditional',
            citations=[Citation(evidence_id=source.id,quote=source.excerpt,subject='RDKV',source_character='합성 자료')])
        first=run_market(data,FixtureWeb(),AdaptiveAnalyst(),mode='fixture',budget=budget,
            previous=Analysis(assessments=[row],followup_questions=[]),existing_evidence={source.id:source})
        budget.constrain(Limits(**budget.used))
        resumed=run_market(data,FixtureWeb(),AdaptiveAnalyst(),mode='fixture',budget=budget,round_number=1,
            previous=first['analysis'],existing_evidence=first['evidence'])
        kept=next(r for r in resumed['result'].assessments if (r.tech_id,r.criterion_id)==('SW-01','ecosystem_support'))
        self.assertEqual(kept.generation_method,'verified_claim')
        self.assertEqual(kept.judgment,row.judgment)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out';save_run(first,out,fingerprint(data,'fixture','fixture-no-llm'))
            saved=json.loads((cache_path(out)/'run.json').read_text())
            final=revalidate(saved,first['sources'])['result']
            kept=next(r for r in final.assessments if (r.tech_id,r.criterion_id)==('SW-01','ecosystem_support'))
            self.assertEqual(kept.generation_method,'verified_claim')
            self.assertEqual(kept.judgment,row.judgment)

    def test_saved_synthesis_survives_offline_revalidation(self):
        state=run_market(self.data(),FixtureWeb(),AdaptiveAnalyst(),mode='fixture')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out';save_run(state,out,fingerprint(state['data'],'fixture','fixture-no-llm'))
            saved=json.loads((cache_path(out)/'run.json').read_text())
            result=revalidate(saved,{})['result']
            self.assertTrue(all(r.generation_method=='model_synthesis' for r in result.assessments))
            self.assertEqual([r.judgment for r in result.assessments],[r.judgment for r in state['result'].assessments])
