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
        cells=schema['properties']['claims']['properties']
        self.assertEqual(len(cells),6)
        self.assertTrue(all(c['maxItems']<=2 for c in cells.values()))
        self.assertEqual(cells['HW-01::standardization']['maxItems'],0)
        branch=schema['$defs'][cells['HW-01::ecosystem_support']['items']['anyOf'][0]['$ref'].rsplit('/',1)[-1]]['properties']
        self.assertNotIn('tech_id',branch)
        self.assertNotIn('exact',branch['relation_to_technology']['enum'])
        self.assertIn('Product-X',schema['$defs'][branch['subject']['$ref'].rsplit('/',1)[-1]]['enum'])
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
        self.assertLessEqual(len(enums),6)
        payload=json.loads(request['messages'][1]['content'])
        self.assertEqual(set(enums[0]),set(payload['evidence'][0]['quotes']))
        background=json.dumps(payload['technologies'])
        for eid in data.evidence:self.assertNotIn(eid,background)
        self.assertIn('적용 조건',json.dumps(payload['technologies'],ensure_ascii=False))

    def test_grouped_response_becomes_scoped_internal_claims_and_reviews(self):
        def handler(request):
            wire=json.loads(request.content)
            schema=wire['response_format']['json_schema']['schema']
            claims={key:[] for key in schema['properties']['claims']['properties']}
            ref=schema['properties']['claims']['properties']['HW-01::ecosystem_support']['items']['anyOf'][0]['$ref']
            props=schema['$defs'][ref.rsplit('/',1)[-1]]['properties']
            claims['HW-01::ecosystem_support']=[dict(statement='공유 메모리를 지원한다고 발표함',basis='fact',
                relation_to_technology='method_family',quote_id=props['quote_id']['enum'][0],subject='Product-X',
                conditions=['선정 구현과 호환성 검증 필요'],metric=None,evidence_level='publisher_statement')]
            reviews={key:dict(outcome='claims_extracted',reason='합성 검토',criteria=['ecosystem_support'])
                for key in schema['properties']['reviews']['properties']}
            return self.completion(json.dumps(dict(claims=claims,reviews=reviews)))
        result=self.provider(handler).extract(self.data,{'MKT-X':self.source()})
        self.assertEqual(len(result.claims),1)
        self.assertEqual((result.claims[0].tech_id,result.claims[0].criterion_id),('HW-01','ecosystem_support'))
        self.assertEqual(result.reviews[0].evidence_id,'MKT-X')

    def test_no_quotes_means_no_model_call(self):
        def handler(_):
            self.fail('Empty quote bank must not call the model')
        result=self.provider(handler).extract(self.data,self.data.evidence)
        self.assertEqual(result.claims,[])


if __name__=='__main__':unittest.main()
