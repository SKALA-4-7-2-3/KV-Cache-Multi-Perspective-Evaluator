import json
import unittest
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Evidence, SelectedExtraction
from market_agent.tests import test_providers


class ReferenceContractTests(unittest.TestCase):
    setUp=test_providers.ProviderTests.setUp
    provider=test_providers.ProviderTests.provider
    completion=test_providers.ProviderTests.completion
    def source(self):
        return Evidence(id='MKT-X', doc_id='WEB-X', title='Memory product',
            url='https://example.org/product', tech_ids=['HW-01'],
            excerpt='Product-X supports shared CXL memory for inference deployments.',
            access_status='full_text', content_status='substantive')

    def test_extraction_enum_contains_only_collected_quotes(self):
        requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return self.completion(SelectedExtraction(claims=[],reviews=[]).model_dump_json())
        provider=self.provider(handler)
        data=read_input(Path(__file__).parents[1]/'fixtures/paper_analysis_hw.json')
        provider.extract(data,{**data.evidence,'MKT-X':self.source()})
        request=requests[0]
        schema=request['response_format']['json_schema']['schema']
        enums=[]
        def walk(value):
            if isinstance(value,dict):
                if 'quote_id' in value.get('properties',{}):
                    enums.append(value['properties']['quote_id'].get('enum'))
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        walk(schema)
        self.assertTrue(enums and all(enums))
        payload=json.loads(request['messages'][1]['content'])
        self.assertEqual(set(enums[0]),set(payload['evidence'][0]['quotes']))
        background=json.dumps(payload['technologies'])
        for eid in data.evidence:self.assertNotIn(eid,background)
        self.assertIn('적용 조건',json.dumps(payload['technologies'],ensure_ascii=False))

    def test_no_quotes_means_no_model_call(self):
        def handler(_):
            self.fail('Empty quote bank must not call the model')
        result=self.provider(handler).extract(self.data,self.data.evidence)
        self.assertEqual(result.claims,[])


if __name__=='__main__':unittest.main()
