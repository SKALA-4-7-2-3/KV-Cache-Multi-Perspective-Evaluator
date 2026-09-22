import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from market_agent.parser import read_input, InputError
from market_agent.json_input import model_background
from market_agent.tests.test_json_input import SW, HW


def bundle():
    dossiers=[];registry=[]
    for path in [SW,HW]:
        old=json.loads(path.read_text())
        entries=old.pop('evidence_registry')
        for e in entries:
            e['content_hash']=hashlib.sha256(e['snippet'].encode()).hexdigest()
            e['locator']={'physical_page':e.pop('page'),'section_path':[e.pop('section') or '본문'], 'document_sha256':'a'*64}
        registry+=entries
        dossiers.append({'dossier_version':'1.0.0','paper':{**old['paper'],'source_hash':'a'*64},
            'analysis':old['analysis'],'evidence_ids':[e['evidence_id'] for e in entries],
            'claims':[],'experiment_observations':[{'observation_id':old['paper']['paper_id']+'::o1',
                'evaluation_mode':'simulated','evidence_ids':[entries[0]['evidence_id']]}]})
    comparison={'comparison_version':'1.0.0','metric_comparisons':[{'comparability':'not_comparable',
        'reason':'측정과 시뮬레이션은 직접 비교 불가','observation_ids':[d['experiment_observations'][0]['observation_id'] for d in dossiers]}]}
    return [registry,comparison,*dossiers]


class DossierInputTests(unittest.TestCase):
    def parse(self,docs):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for i,doc in enumerate(docs):
                p=Path(tmp)/f'{i}.json';p.write_text(json.dumps(doc));paths.append(p)
            return read_input(paths,as_of='2026-09-22')

    def test_four_files_order_independent_and_context_preserved(self):
        docs=bundle();a=self.parse(docs);b=self.parse(list(reversed(docs)))
        self.assertEqual(a.input_hash,b.input_hash)
        self.assertEqual(a.input_format,'technical_bundle_json')
        self.assertEqual(len(a.evidence),2)
        self.assertEqual(a.comparison['metric_comparisons'][0]['comparability'],'not_comparable')
        self.assertTrue(all(e.access_status=='provided_summary' for e in a.evidence.values()))
        self.assertIn('page 1',next(iter(a.evidence.values())).locator)
        self.assertIn('simulated',model_background(a,a.technologies['HW-01']))
        self.assertNotIn('ev-synthetic',model_background(a,a.technologies['HW-01']))

    def test_cached_bundle_array_roundtrip(self):
        a=self.parse(bundle())
        b=self.parse([[a.source_registry,a.comparison,*a.source_documents]])
        self.assertEqual(a.input_hash,b.input_hash)
        self.assertEqual(a.evidence,b.evidence)

    def test_broken_references_hashes_and_mixed_inputs_fail_closed(self):
        for mode in ['missing_registry','bad_hash','cross_owner','unknown_observation','bad_version','duplicate_registry','bad_array','null_array','bad_relation']:
            docs=copy.deepcopy(bundle())
            if mode=='missing_registry':docs.pop(0)
            if mode=='bad_hash':docs[0][0]['snippet']+='changed'
            if mode=='cross_owner':docs[2]['evidence_ids']=[docs[0][1]['evidence_id']]
            if mode=='unknown_observation':docs[1]['metric_comparisons'][0]['observation_ids']=['missing']
            if mode=='bad_version':docs[2]['dossier_version']='2.0.0'
            if mode=='bad_array':docs[1]['metric_comparisons']='invalid'
            if mode=='null_array':docs[1]['integration_hypotheses']=None
            if mode=='bad_relation':docs[1]['relationships']=[{'left_paper_id':'missing'}]
            if mode=='duplicate_registry':docs.append(copy.deepcopy(docs[0]))
            with self.subTest(mode=mode),self.assertRaises(InputError):self.parse(docs)
