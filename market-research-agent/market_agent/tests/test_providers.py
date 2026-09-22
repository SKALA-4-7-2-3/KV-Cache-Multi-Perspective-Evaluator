"""설치된 OpenAI/LangChain의 직렬화·파싱을 실제 네트워크 없이 검증한다."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_openai import ChatOpenAI

from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, OpenAIAnalyst
from market_agent.tools import ProviderError
from market_agent.schemas import Extraction


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1] / "fixtures/input.md")

    def provider(self, handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch("langchain_openai.ChatOpenAI", side_effect=lambda **kw: ChatOpenAI(http_client=client, **kw)):
            provider = OpenAIAnalyst("test-only")
        self.addCleanup(provider.close)
        return provider

    def completion(self, content):
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
            "model": "gpt-4.1-mini", "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}})

    def test_installed_sdk_sends_strict_schema_and_parses_twelve_assessments(self):
        requests = []
        answer = FixtureAnalyst().compose(self.data, {})
        def handler(request):
            requests.append(json.loads(request.content))
            return self.completion(answer.model_dump_json())
        provider = self.provider(handler)
        result = provider.compose(self.data, {})
        self.assertEqual(len(result.assessments), 12)
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0]["response_format"]["json_schema"]["strict"])
        self.assertEqual(provider.usage[0]["total_tokens"], 30)

    def test_invalid_structured_output_is_reported_without_response_content(self):
        provider = self.provider(lambda _: self.completion('{"unexpected": "PRIVATE_BODY"}'))
        with self.assertRaises(ProviderError) as caught:
            provider.compose(self.data, {})
        self.assertEqual(caught.exception.code, "invalid_structured_output")
        self.assertNotIn("PRIVATE_BODY", str(caught.exception))

    def test_missing_new_handoff_fields_are_not_silently_filled_with_defaults(self):
        answer = FixtureAnalyst().compose(self.data, {}).model_dump(mode='json')
        for row in answer['assessments']:
            for key in ['verdict', 'claim_ids']:
                row.pop(key)
        provider = self.provider(lambda _: self.completion(json.dumps(answer)))
        with self.assertRaises(ProviderError) as caught:
            provider.compose(self.data, {})
        self.assertEqual(caught.exception.code, 'invalid_structured_output')

    def test_auth_error_is_sanitized_and_sdk_does_not_retry(self):
        attempts = []
        def handler(request):
            attempts.append(1)
            return httpx.Response(401, json={"error": {"message": "PRIVATE_BODY", "type": "invalid_request_error", "code": "invalid_api_key"}})
        provider = self.provider(handler)
        with self.assertRaises(ProviderError) as caught:
            provider.compose(self.data, {})
        self.assertEqual(len(attempts), 1)
        self.assertTrue(caught.exception.fatal)
        self.assertNotIn("PRIVATE_BODY", str(caught.exception))

    def test_extraction_and_composition_use_separate_source_boundaries(self):
        requests=[]
        def handler(request):
            payload=json.loads(request.content)
            requests.append(payload)
            answer=Extraction(claims=[],reviews=[]) if len(requests)==1 else FixtureAnalyst().compose(self.data,{})
            return self.completion(answer.model_dump_json())
        provider=self.provider(handler)
        provider.extract(self.data,self.data.evidence)
        provider.compose(self.data,{})
        self.assertIn('evidence',json.loads(requests[0]['messages'][1]['content']))
        composed=json.loads(requests[1]['messages'][1]['content'])
        self.assertNotIn('input_markdown',composed)
        self.assertNotIn('evidence',composed)
        self.assertIn('claims',composed)

    def test_json_context_preserves_limits_without_forwarding_paths_or_upstream_settings(self):
        requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return self.completion(Extraction(claims=[],reviews=[]).model_dump_json())
        data=read_input(Path(__file__).parents[1]/'fixtures/paper_analysis_hw.json')
        provider=self.provider(handler)
        provider.extract(data,data.evidence)
        payload=json.loads(requests[0]['messages'][1]['content'])
        context=payload['technologies']['HW-01']['technical_context']
        self.assertIn('limitations',context)
        self.assertIn('적용 조건',context)
        self.assertNotIn('/unavailable/',json.dumps(payload))
        self.assertNotIn('upstream-test-model',json.dumps(payload))
        self.assertEqual(payload['evidence'],[])


if __name__ == "__main__":
    unittest.main()
