import json
from pathlib import Path
import tempfile
import unittest

import httpx


class GovernanceTests(unittest.TestCase):
    def test_parallel_reservations_cannot_spend_the_same_tokens(self):
        from pipeline.governance import BudgetLedger, BudgetExceeded
        with tempfile.TemporaryDirectory() as d:
            ledger = BudgetLedger(Path(d), limits={"llm": 2, "tokens": 100})
            first = ledger.reserve("llm", 70, task_id="one")
            with self.assertRaises(BudgetExceeded):
                ledger.reserve("llm", 70, task_id="two")
            ledger.finish(first, tokens=20)
            second = ledger.reserve("llm", 70, task_id="two")
            ledger.finish(second, tokens=None, error="timeout")
            self.assertEqual(ledger.snapshot()["used_tokens"], 20)
            self.assertEqual(ledger.snapshot()["unconfirmed_tokens"], 70)
            reopened = BudgetLedger(Path(d), limits={"llm": 2, "tokens": 100})
            self.assertEqual(reopened.snapshot()["counts"]["llm"], 2)
            with self.assertRaises(BudgetExceeded):
                reopened.reserve("llm", 1, task_id="three")

    def test_http_usage_and_failed_attempts_are_recorded_without_secrets(self):
        from pipeline.governance import BudgetLedger, GovernedClient
        with tempfile.TemporaryDirectory() as d:
            ledger = BudgetLedger(Path(d), limits={"tokens": 10000})
            def endpoint(request):
                return httpx.Response(200, json={"usage": {"input_tokens": 13, "output_tokens": 7}})
            with GovernedClient(ledger=ledger, transport=httpx.MockTransport(endpoint)) as client:
                client.post("https://api.openai.com/v1/responses", json={
                    "input": "a secret private document", "max_output_tokens": 100})
            saved = (Path(d) / "usage.json").read_text()
            self.assertNotIn("private document", saved)
            self.assertEqual(json.loads(saved)["used_tokens"], 20)
            self.assertEqual(json.loads(saved)["counts"]["llm"], 1)

    def test_reserved_output_ceiling_is_sent_and_remaining_time_caps_timeout(self):
        from pipeline.governance import BudgetLedger, GovernedClient
        with tempfile.TemporaryDirectory() as d:
            ledger = BudgetLedger(Path(d), limits={"tokens": 100000, "seconds": 10})
            captured = []
            def endpoint(request):
                captured.append((json.loads(request.content), request.extensions["timeout"]))
                return httpx.Response(200, json={"usage": {"total_tokens": 21}})
            with GovernedClient(ledger=ledger, transport=httpx.MockTransport(endpoint), timeout=120) as client:
                client.post("https://api.openai.com/v1/responses", json={"input": "brief"})
                client.post("https://api.openai.com/v1/chat/completions", json={"messages": []})
            self.assertEqual(captured[0][0]["max_output_tokens"], 16384)
            self.assertEqual(captured[1][0]["max_completion_tokens"], 16384)
            self.assertTrue(all(0 < timeout <= 10 for _, settings in captured for timeout in settings.values()))
            saved = ledger.snapshot()
            self.assertEqual(saved["used_tokens"], 42)
            self.assertTrue(all(call["reserved_tokens"] >= 16384 for call in saved["calls"].values()))


if __name__ == "__main__":
    unittest.main()
