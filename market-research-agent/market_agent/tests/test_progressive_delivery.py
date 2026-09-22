import unittest
from pathlib import Path

from market_agent.node import run_market, relevant_candidate
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.schemas import Analysis, Limits
from market_agent.claims import recover_previous


class ProgressiveDeliveryTests(unittest.TestCase):
    def test_three_levels_reach_every_criterion_without_repeating_queries(self):
        data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        data.limits=Limits(search=18,extract=24,llm=10)
        state=run_market(data,FixtureWeb(),FixtureAnalyst(),mode='fixture')
        self.assertEqual({q['research_level'] for q in state['queries']},{0,1,2})
        self.assertEqual(len(state['queries']),len({q['query'] for q in state['queries']}))
        for row in state['result'].assessments:
            self.assertNotEqual(row.verdict,'unknown')
            self.assertTrue(row.search_ids)
        self.assertTrue(all(state['result'].usage[k]<=getattr(data.limits,k) for k in state['result'].usage))

    def test_broad_level_accepts_adjacent_sources_but_rejects_acronym_collision(self):
        data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        tech=data.technologies['SW-01']
        row={'title':'Inference software deployment market','content':'GPU software deployment forecast'}
        self.assertFalse(relevant_candidate(row,tech,0))
        self.assertTrue(relevant_candidate(row,tech,2))
        self.assertFalse(relevant_candidate({'title':'RDKV','content':'TV platform software'},tech,2))

    def test_delivery_completion_cannot_be_recovered_as_verified_claims(self):
        data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        data.limits=Limits(search=0,extract=0,llm=0)
        state=run_market(data,FixtureWeb(),FixtureAnalyst(),mode='fixture')
        delivery=Analysis(assessments=state['result'].assessments,followup_questions=[])
        self.assertEqual(recover_previous(delivery),[])
        self.assertEqual(state['result'].execution_status,'partial')
        self.assertEqual(state['result'].status,'provisional')
        self.assertEqual(set(state['result'].technology_status.values()),{'provisional'})
        from market_agent.report import render_report
        report=render_report(state)
        self.assertIn('일부 단계 미완료',report)
        self.assertIn('배정된 호출 한도',report)
        self.assertTrue(all(r.evaluation_mode=='scenario' for r in delivery.assessments))
