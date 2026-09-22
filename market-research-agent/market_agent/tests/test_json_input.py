import copy
import json
import unittest
from datetime import date
from pathlib import Path

from market_agent.parser import InputError, read_input
from market_agent.schemas import Limits

FIXTURES=Path(__file__).parents[1]/'fixtures'
SW=FIXTURES/'paper_analysis_sw.json'
HW=FIXTURES/'paper_analysis_hw.json'


class JsonInputTests(unittest.TestCase):
    def parse(self, documents, **options):
        from market_agent.json_input import parse_paper_analyses
        return parse_paper_analyses(documents,**options)

    def test_two_documents_preserve_upstream_ids_and_research_context(self):
        data=read_input([SW,HW],as_of='2026-09-22')
        self.assertEqual(set(data.technologies),{'SW-01','HW-01'})
        self.assertEqual(data.schema_version,'1.1.0')
        self.assertEqual(data.input_format,'paper_analysis_json')
        self.assertEqual(data.evidence['ev-synthetic-hw'].doc_id,'synthetic-hw')
        self.assertIn('page 1',data.evidence['ev-synthetic-hw'].locator)
        self.assertEqual(data.evidence['ev-synthetic-hw'].access_status,'provided_summary')
        self.assertEqual(data.source_documents[0]['quality']['unsupported_claims'],0)
        self.assertIn('적용 조건',data.technologies['SW-01'].summary)

    def test_single_document_does_not_invent_a_second_technology(self):
        data=read_input(HW)
        self.assertEqual(list(data.technologies),['HW-01'])
        self.assertEqual(data.as_of,date.today())
        self.assertEqual(data.technologies['HW-01'].url,'')
        self.assertTrue(data.warnings)
        self.assertIsNone(data.evidence['ev-synthetic-hw'].published_at)

    def test_options_are_not_inherited_from_upstream_run(self):
        doc=json.loads(SW.read_text());doc['run']['limits']={'llm':999}
        data=self.parse(doc,as_of='2026-09-22',domain='on_device',limits=Limits(search=1,extract=2,llm=3))
        self.assertEqual(data.limits.llm,3)
        self.assertEqual(data.domain,'on_device')
        self.assertNotEqual(data.run_id,doc['run']['run_id'])

    def test_invalid_input_fails_before_any_provider_call(self):
        original=json.loads(SW.read_text())
        variants=[]
        for field,value in [('status','failed'),('schema_version','9.0.0'),('evidence_registry',[])]:
            d=copy.deepcopy(original);d[field]=value;variants.append(d)
        d=copy.deepcopy(original);d['evidence_registry'][0]['document_id']='different';variants.append(d)
        d=copy.deepcopy(original);d['analysis']['scope']['target_tasks'][0]['evidence_ids']=['missing'];variants.append(d)
        for doc in variants:
            with self.subTest(doc=doc.get('status')):
                with self.assertRaises(InputError):self.parse(doc)

    def test_duplicate_documents_and_evidence_ids_are_rejected(self):
        doc=json.loads(SW.read_text())
        with self.assertRaises(InputError):self.parse([doc,doc])
        doc['evidence_registry'].append(copy.deepcopy(doc['evidence_registry'][0]))
        with self.assertRaises(InputError):self.parse(doc)

    def test_unknown_paper_requires_explicit_approach(self):
        doc=json.loads(SW.read_text());doc['paper']['title']='New cache method';doc['paper']['arxiv_id']=None
        with self.assertRaisesRegex(InputError,'approach'):self.parse(doc)
        self.assertEqual(self.parse(doc,approaches=['SW']).technologies['SW-01'].name,'New cache method')

    def test_single_json_fixture_reaches_six_row_report_without_web_api(self):
        from market_agent.node import run_market
        from market_agent.providers import FixtureWeb, FixtureAnalyst
        state=run_market(read_input(HW),FixtureWeb(),FixtureAnalyst(),mode='fixture')
        self.assertEqual(len(state['result'].assessments),6)
        self.assertTrue(all(r.tech_id=='HW-01' for r in state['result'].assessments))

    def test_paper_snippets_do_not_become_verified_market_facts(self):
        from market_agent.quotes import quote_bank
        data=read_input(SW)
        self.assertEqual(quote_bank(data.evidence),{})
        self.assertTrue(all(e.access_status!='full_text' for e in data.evidence.values()))
