"""설치된 SDK를 통한 새 종합·검토 계약의 HTTP 경계 모의 검사. 외부 호출 없음."""
import json
import unittest
from market_agent.tests import test_providers
from market_agent.schemas import Synthesis,SynthesisRow,SynthesisReviews,SynthesisReview,Limits
from market_agent.providers import FixtureWeb
from market_agent.node import run_market


class AdaptiveProviderTests(unittest.TestCase):
    setUp=test_providers.ProviderTests.setUp
    provider=test_providers.ProviderTests.provider
    completion=test_providers.ProviderTests.completion

    def test_cell_contract_restricts_ownership_and_requires_nonempty_conditions(self):
        def handler(request):
            body=json.loads(request.content);schema=body['response_format']['json_schema']['schema']
            cell=schema['properties']['assessments']['properties']['SW-01::adoption']['anyOf'][0]
            self.assertEqual(cell['properties']['quote_ids']['items']['enum'],['MAT-sw'])
            self.assertEqual(cell['properties']['conditions']['minItems'],1)
            row=SynthesisRow(tech_id='SW-01',criterion_id='adoption',observation='원자료의 관찰',judgment='조건부 도입 판단',
                relation_to_technology='method_family',quote_ids=['MAT-sw'],conditions=['적용 환경 확인'],limitations=[])
            return self.completion(json.dumps({'assessments':{'SW-01::adoption':row.model_dump()}},ensure_ascii=False))
        provider=self.provider(handler)
        result=provider.synthesize(self.data,{'MAT-sw':{'tech_ids':['SW-01']},'MAT-hw':{'tech_ids':['HW-01']}},2,[('SW-01','adoption')])
        self.assertEqual(len(result.assessments),1)

    def test_real_sdk_routes_synthesis_and_review_and_preserves_model_output(self):
        requests=[]
        def handler(request):
            request=json.loads(request.content);requests.append(request)
            payload=json.loads(request['messages'][1]['content'])
            level=payload['research_policy']['level']
            if 'targets' in payload:
                rows=[]
                if level==2:
                    for cell in payload['targets']:
                        refs=[k for k,p in payload['packet'].items() if cell['tech_id'] in p['tech_ids'] and p['access_status']=='snippet'][:1]
                        if refs:rows.append(SynthesisRow(**cell,observation='검색 자료에는 시장 수치를 입증하지 않는다고 명시되어 있다.',
                            judgment='확정 시장 규모 산출에 사용하지 않고 후속 원문 조사의 출발점으로 활용한다.',
                            quote_ids=refs,relation_to_technology='adjacent',conditions=['합성 검색 자료에 대한 모의 판단'],limitations=['실시장 평가 아님']))
                answer=Synthesis(assessments=rows)
            else:
                answer=SynthesisReviews(reviews=[SynthesisReview(tech_id=r['tech_id'],criterion_id=r['criterion_id'],
                    supported=True,relevant=True,scope_preserved=True,uncertainty_preserved=True,reason='모의 검토 응답')
                    for r in payload['assessments']['assessments']])
            return self.completion(answer.model_dump_json())
        provider=self.provider(handler)
        self.data.limits=Limits(search=18,extract=0,llm=10)
        state=run_market(self.data,FixtureWeb(),provider,mode='fixture')
        self.assertEqual(len(state['result'].assessments),12)
        self.assertTrue(all(r.generation_method=='model_synthesis' for r in state['result'].assessments))
        self.assertEqual({item['stage'] for item in provider.usage},{'synthesize','review_synthesis'})
        self.assertTrue(all(r['response_format']['json_schema']['strict'] for r in requests))
        self.assertTrue(all('packet' in json.loads(r['messages'][1]['content']) for r in requests))

    def test_synthesis_parse_failure_is_sanitized(self):
        from market_agent.tools import ProviderError
        provider=self.provider(lambda _:self.completion('{"private_response":"never_print"}'))
        with self.assertRaises(ProviderError) as error:
            provider.synthesize(self.data,{},2,[('SW-01','adoption')])
        self.assertEqual(error.exception.code,'invalid_structured_output')
        self.assertNotIn('never_print',str(error.exception))
