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
        answer = FixtureAnalyst().analyze(self.data, self.data.evidence)
        def handler(request):
            requests.append(json.loads(request.content))
            return self.completion(answer.model_dump_json())
        provider = self.provider(handler)
        result = provider.analyze(self.data, self.data.evidence)
        self.assertEqual(len(result.assessments), 12)
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0]["response_format"]["json_schema"]["strict"])
        self.assertEqual(provider.usage[0]["total_tokens"], 30)

    def test_invalid_structured_output_is_reported_without_response_content(self):
        provider = self.provider(lambda _: self.completion('{"unexpected": "PRIVATE_BODY"}'))
        with self.assertRaises(ProviderError) as caught:
            provider.analyze(self.data, self.data.evidence)
        self.assertEqual(caught.exception.code, "invalid_structured_output")
        self.assertNotIn("PRIVATE_BODY", str(caught.exception))

    def test_missing_new_handoff_fields_are_not_silently_filled_with_defaults(self):
        answer = FixtureAnalyst().analyze(self.data, self.data.evidence).model_dump(mode='json')
        for row in answer['assessments']:
            for key in ['verdict', 'citations', 'context_findings']:
                row.pop(key)
        provider = self.provider(lambda _: self.completion(json.dumps(answer)))
        with self.assertRaises(ProviderError) as caught:
            provider.analyze(self.data, self.data.evidence)
        self.assertEqual(caught.exception.code, 'missing_required_handoff_fields')

    def test_auth_error_is_sanitized_and_sdk_does_not_retry(self):
        attempts = []
        def handler(request):
            attempts.append(1)
            return httpx.Response(401, json={"error": {"message": "PRIVATE_BODY", "type": "invalid_request_error", "code": "invalid_api_key"}})
        provider = self.provider(handler)
        with self.assertRaises(ProviderError) as caught:
            provider.analyze(self.data, self.data.evidence)
        self.assertEqual(len(attempts), 1)
        self.assertTrue(caught.exception.fatal)
        self.assertNotIn("PRIVATE_BODY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
