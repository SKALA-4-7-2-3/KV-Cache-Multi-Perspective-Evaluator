import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from market_agent.schemas import Limits
from market_agent.tools import Budget, BudgetExceeded, ProviderError, TavilyWeb, public_url


class ToolTests(unittest.TestCase):
    def test_budget_is_shared_across_retries_and_threads(self):
        budget = Budget(Limits(search=6, extract=10, llm=5))
        def consume(_):
            try:
                budget.take("search")
                return True
            except BudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=10) as pool:
            self.assertEqual(sum(pool.map(consume, range(20))), 6)
        self.assertEqual(budget.used["search"], 6)

    def test_retry_consumes_attempts_but_auth_is_not_retried(self):
        budget = Budget(Limits(search=2, extract=0, llm=0))
        count = []
        def retry():
            count.append(1)
            if len(count) == 1:
                raise ProviderError("timeout", retryable=True)
            return "ok"
        self.assertEqual(budget.call("search", retry), "ok")
        self.assertEqual(budget.used["search"], 2)
        budget = Budget(Limits(search=6, extract=0, llm=0))
        with self.assertRaises(ProviderError):
            budget.call("search", lambda: (_ for _ in ()).throw(ProviderError("auth", fatal=True)))
        self.assertEqual(budget.used["search"], 1)

    def test_search_payload_and_raw_source_extraction(self):
        requests = []
        def handle(request):
            import json
            payload = json.loads(request.content)
            requests.append(payload)
            if request.url.path == "/search":
                return httpx.Response(200, json={"results": [{"title": "Official", "url": "https://example.org/a", "content": "snippet", "published_date": "Tue, 01 Sep 2026 17:00:00 GMT"}]})
            return httpx.Response(200, json={"results": [{"url": payload["urls"][0], "raw_content": "full source"}], "failed_results": []})
        web = TavilyWeb("test-only", client=httpx.Client(transport=httpx.MockTransport(handle)))
        candidate = web.search("RDKV", date(2026, 9, 21))[0]
        self.assertEqual(web.extract(candidate["url"]), "full source")
        self.assertEqual(requests[0]["max_results"], 6)
        self.assertFalse(requests[0]["include_answer"])
        self.assertFalse(requests[0]["include_raw_content"])

    def test_partial_extract_failure_is_not_a_success(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": [], "failed_results": [{"url": "https://example.org/a", "error": "private details"}]})))
        with self.assertRaisesRegex(ProviderError, "extract_failed"):
            TavilyWeb("test-only", client=client).extract("https://example.org/a")

    def test_private_urls_and_credentials_are_rejected(self):
        for url in ["file:///tmp/key", "http://localhost/x", "http://127.0.0.1/x", "https://u:p@example.org", "http://10.0.0.2", "http://[::1]/"]:
            self.assertFalse(public_url(url), url)
        self.assertTrue(public_url("https://example.org/a"))

    def test_provider_auth_error_does_not_leak_response(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"detail": "SECRET_VALUE"})))
        with self.assertRaises(ProviderError) as caught:
            TavilyWeb("test-only", client=client).search("q", date.today())
        self.assertNotIn("SECRET_VALUE", str(caught.exception))
        self.assertTrue(caught.exception.fatal)


if __name__ == "__main__":
    unittest.main()
