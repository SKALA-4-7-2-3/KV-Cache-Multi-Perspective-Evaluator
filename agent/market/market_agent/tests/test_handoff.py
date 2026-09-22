import json
import unittest
from pathlib import Path

from market_agent.handoff import build_handoff, render_handoff
from market_agent.node import run_market
from market_agent.parser import read_input
from market_agent.providers import AdaptiveFixtureAnalyst, FixtureWeb
from market_agent.schemas import CRITERIA


class HandoffTests(unittest.TestCase):
    def state(self, single=False):
        fixture = 'paper_analysis_sw.json' if single else 'input.md'
        data = read_input(Path(__file__).parents[1] / 'fixtures' / fixture)
        return run_market(data, FixtureWeb(), AdaptiveFixtureAnalyst(), mode='fixture')

    def test_json_preserves_evaluations_and_exposes_only_referenced_sources(self):
        state = self.state()
        before = state['result'].model_dump()
        handoff = json.loads(render_handoff(state))
        self.assertEqual(handoff['schema_version'], '1.0.0')
        self.assertEqual(handoff['coverage']['provided'], 12)
        self.assertEqual(handoff['mode'], 'fixture')
        self.assertIn('가상', handoff['warnings'][0])
        refs = set()
        for row, original in zip(handoff['assessments'], state['result'].assessments):
            for key in ['judgment', 'observation', 'verdict', 'conditions', 'gaps', 'generation_method']:
                self.assertEqual(row[key], getattr(original, key))
            self.assertEqual(row['criterion_name'], CRITERIA[row['criterion_id']])
            for ref in row['citations'] + row['supporting_materials']:
                refs.add(ref['evidence_id'])
                self.assertIn(ref['evidence_id'], handoff['sources'])
            self.assertNotIn('search_ids', row)
        self.assertEqual(refs, set(handoff['sources']))
        self.assertEqual(before, state['result'].model_dump())
        for internal in ['queries', 'events', 'token_usage', 'progress', 'source_documents', 'raw_markdown']:
            self.assertNotIn(internal, handoff)

    def test_single_technology_has_six_rows_and_unicode_is_not_markdown_escaped(self):
        state = self.state(single=True)
        text = '한글 "인용" | [자료]\n다음 줄 <조건>'
        state['result'].assessments[0].judgment = text
        encoded = render_handoff(state)
        handoff = json.loads(encoded)
        self.assertEqual(handoff['coverage']['expected'], 6)
        self.assertEqual(handoff['assessments'][0]['judgment'], text)
        self.assertIn('한글', encoded)
        self.assertNotIn('\\u', encoded)

    def test_rejects_duplicate_rows_and_missing_or_wrong_owner_references(self):
        for corruption in ['duplicate', 'missing', 'owner']:
            with self.subTest(corruption=corruption):
                state = self.state()
                ref = state['result'].assessments[0].supporting_materials[0]
                if corruption == 'duplicate':
                    state['result'].assessments.append(state['result'].assessments[0])
                elif corruption == 'missing':
                    del state['evidence'][ref.evidence_id]
                else:
                    state['evidence'][ref.evidence_id].tech_ids = []
                with self.assertRaises(ValueError):
                    build_handoff(state)

    def test_legacy_conversion_retains_partial_status_and_does_not_upgrade_fallback(self):
        state = self.state()
        state['result'].output_schema_version = '0.5'
        state['result'].execution_status = 'partial'
        state['result'].errors = [{'stage':'extract','code':'failed','private_response':'do not export'}]
        handoff = build_handoff(state)
        self.assertEqual(handoff['execution_status'], 'partial')
        self.assertEqual(handoff['errors'], [{'stage':'extract','code':'failed'}])
        self.assertTrue(all(row['generation_method']=='deterministic_fallback' for row in handoff['assessments']))
        self.assertTrue(all(row['evaluation_level'] is None for row in handoff['assessments']))
