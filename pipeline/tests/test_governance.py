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


if __name__ == "__main__":
    unittest.main()
