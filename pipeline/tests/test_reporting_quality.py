"""Source and TRL preservation at the report revision boundary."""
from pathlib import Path
import json
import re
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from pipeline.reporting import (build_quality_revision_prompt, source_analysis,
                                validate_source_reading, source_quote_spans, resolve_source_reading_ids)
from report_agent.parser import parse_report_input

FIXTURES = Path(__file__).resolve().parents[2] / "report/tests/fixtures"


class ReportingQualityTests(unittest.TestCase):
    def test_revision_receives_original_sources_and_final_trl_contract(self):
        parsed = parse_report_input((FIXTURES / "trl-runtime.input.md").read_text())
        prompt = build_quality_revision_prompt(parsed, "UNIQUE_OLD_REPORT", ["Do not invent adoption."])
        self.assertIn(parsed.raw_markdown, prompt)
        self.assertIn("UNIQUE_OLD_REPORT", prompt)
        self.assertIn("BEGIN_TRL_ASSESSMENT SW-01", prompt)
        self.assertEqual(prompt.count("[Review 최종 TRL 보존 계약]"), 1)
        self.assertGreater(prompt.index("[Review 최종 TRL 보존 계약]"), prompt.index("---END_REPORT_SOURCE_"))
        self.assertIn("---REPORT_REVISION_", prompt)
        self.assertIn("---REPORT_FEEDBACK_", prompt)

    def test_source_reading_quote_must_be_contiguous_original_text(self):
        source = {"excerpt": "First observation. Exact original result. Final condition."}
        valid = {"use_in_report": True, "observations": [{"source_report": "저자 보고",
                 "supporting_quote": "Exact original result."}]}
        self.assertEqual(validate_source_reading(source, valid), valid)
        for quote in ("Commercial adoption verified.", "First observation ... Final condition."):
            invalid = {**valid, "observations": [{"source_report": "저자 보고", "supporting_quote": quote}]}
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                validate_source_reading(source, invalid)

    def test_used_source_cannot_have_empty_observations(self):
        with self.assertRaises(ValueError):
            validate_source_reading({"excerpt": "Original source."}, {"use_in_report": True, "observations": []})

    def test_threaded_source_call_keeps_its_source_task_identity(self):
        from pipeline.governance import _task
        identities = []
        class Client:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            @property
            def responses(self):
                return self
            def parse(self, **kwargs):
                identities.append(_task.get())
                return SimpleNamespace(output_parsed=SimpleNamespace(model_dump=lambda: {
                    "use_in_report": False, "observations": [], "omission_reason": "무관한 자료"}))
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([
            {"source_id": "source-a", "excerpt": "Original source.", "url": "https://example.test/a"}
        ]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            source_analysis(markdown, Path(directory), "offline-model")
        self.assertEqual(identities, ["report-source-source-a"])

    def test_source_contract_failure_is_saved_and_repaired_once(self):
        calls = []
        readings = [
            {"use_in_report": True, "observations": [{"source_report": "저자 보고",
                "supporting_quote": "Invented source quote."}]},
            {"use_in_report": True, "observations": [{"source_report": "저자 보고",
                "supporting_quote_id": "q00001"}]},
        ]
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def parse(self, **kwargs):
                calls.append(kwargs)
                value = readings[len(calls) - 1]
                return SimpleNamespace(output_text=json.dumps(value),
                    output_parsed=SimpleNamespace(model_dump=lambda: value))
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([
            {"source_id": "source-a", "excerpt": "Exact original result.", "url": "https://example.test/a"}
        ]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            output = Path(directory)
            result = source_analysis(markdown, output, "offline-model")
            attempts = sorted((output / "source-readings").glob("*.attempt-*.json"))
            self.assertEqual(len(attempts), 2)
            failed = json.loads(attempts[0].read_text())
            self.assertIn("contiguous", failed["validation_error"])
            self.assertEqual(failed["candidate"]["observations"][0]["supporting_quote"], "Invented source quote.")
            self.assertIn("Invented source quote.", calls[1]["input"])
            self.assertIn("Exact original result.", calls[1]["input"])
            self.assertIn("---SOURCE_READING_REPAIR_", calls[1]["input"])
            self.assertEqual(calls[0]["text_format"].__name__, "SourceReading")
            self.assertEqual(calls[1]["text_format"].__name__, "SourceReadingById")
            match = re.search(r"---SOURCE_READING_REPAIR_[0-9a-f]{16}---\n([\s\S]*?)\n---END_", calls[1]["input"])
            repair_data = json.loads(match.group(1))
            self.assertNotIn("excerpt", repair_data["source"])
            self.assertEqual("".join(span["text"] for span in repair_data["excerpt_spans"]), "Exact original result.")
            success = json.loads(next((output / "source-readings").glob("*.attempt-2.json")).read_text())
            self.assertEqual(success["candidate"]["observations"][0]["supporting_quote_id"], "q00001")
            self.assertEqual(success["resolved_reading"]["observations"][0]["supporting_quote"], "Exact original result.")
            self.assertIn("Exact original result.", result)
            source_analysis(markdown, output, "offline-model")
        self.assertEqual(len(calls), 2)

    def test_second_bad_source_reading_stops_and_preserves_both_candidates(self):
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def parse(self, **kwargs):
                calls.append(kwargs)
                value = {"use_in_report": True, "observations": [{"source_report": "저자 보고",
                    **({"supporting_quote": "Altered original result."} if len(calls) == 1
                       else {"supporting_quote_id": "q_not_registered"})}]}
                return SimpleNamespace(output_text=json.dumps(value),
                    output_parsed=SimpleNamespace(model_dump=lambda: value))
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([
            {"source_id": "source-b", "excerpt": "Exact original result."}
        ]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            with self.assertRaisesRegex(ValueError, "source-b.*two attempts"):
                source_analysis(markdown, Path(directory), "offline-model")
            attempts = list((Path(directory) / "source-readings").glob("*.attempt-*.json"))
            self.assertEqual(len(attempts), 2)
            self.assertTrue(all(json.loads(path.read_text())["validation_error"] for path in attempts))
            self.assertFalse((Path(directory) / "report.source-analysis.json").exists())
        self.assertEqual(len(calls), 2)

    def test_numbered_source_spans_cover_every_original_character_and_bind_exact_quotes(self):
        excerpt = "첫 줄\n" + "x" * 1599 + "\n마지막 조건: 시뮬레이션 ... 원문 자체의 생략 표시."
        source = {"excerpt": excerpt}
        spans = source_quote_spans(source)
        self.assertEqual("".join(span["text"] for span in spans), excerpt)
        self.assertEqual(spans[0]["start"], 0)
        self.assertEqual(spans[-1]["end"], len(excerpt))
        self.assertTrue(all(0 < len(span["text"]) <= 800 for span in spans))
        self.assertTrue(all(left["end"] == right["start"] for left, right in zip(spans, spans[1:])))
        selected = spans[-1]
        reading = {"use_in_report": True, "observations": [{"source_report": "출처 보고",
                   "supporting_quote_id": selected["id"]}]}
        resolved = resolve_source_reading_ids(source, reading, spans)
        self.assertEqual(resolved["observations"][0]["supporting_quote"], excerpt[selected["start"]:selected["end"]])
        self.assertEqual(validate_source_reading(source, resolved), resolved)
        for invalid in (None, "q_unknown", "q00001 ... q00003"):
            broken = {**reading, "observations": [{"source_report": "출처 보고", "supporting_quote_id": invalid}]}
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                resolve_source_reading_ids(source, broken, spans)

    def test_repaired_source_uses_code_owned_identity_and_old_success_key_without_calls(self):
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def parse(self, **kwargs):
                calls.append(kwargs)
                value = {"use_in_report": True, "observations": [{"source_report": "출처 보고",
                         **({"supporting_quote": "stitch ... stitch"} if len(calls) == 1
                            else {"supporting_quote_id": "q00001"})}],
                         "source_id": "model-injected-source", "technology_ids": ["HW-01"]}
                return SimpleNamespace(output_text=json.dumps(value),
                    output_parsed=SimpleNamespace(model_dump=lambda: value))
        source = {"source_id": "source-owner", "title": "Title", "url": "https://example.test/owner",
                  "citation_key": "WEB_owner", "role": "market", "technology_ids": ["SW-01"],
                  "excerpt": "Exact original result."}
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([source]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            output = Path(directory)
            source_analysis(markdown, output, "offline-model")
            cached = next(path for path in (output / "source-readings").glob("*.json") if ".attempt-" not in path.name)
            from hashlib import sha256
            expected_key = sha256(json.dumps([source, "offline-model", calls[0]["instructions"]], ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(cached.stem, expected_key)
            saved = json.loads(cached.read_text())
            for field in ("source_id", "title", "url", "citation_key", "role", "technology_ids"):
                self.assertEqual(saved[field], source[field])
            (output / "report.source-analysis.json").unlink()
            source_analysis(markdown, output, "offline-model")
            self.assertEqual(len(calls), 2)

    def test_unparsed_source_response_is_saved_before_one_repair(self):
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def parse(self, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    return SimpleNamespace(output_parsed=None, output_text='{"incomplete":')
                return SimpleNamespace(output_text="{}", output_parsed=SimpleNamespace(model_dump=lambda: {
                    "use_in_report": False, "observations": [], "omission_reason": "평가와 무관한 자료"}))
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([
            {"source_id": "source-c", "excerpt": "Exact original result."}
        ]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            source_analysis(markdown, Path(directory), "offline-model")
            attempt = json.loads(next((Path(directory) / "source-readings").glob("*.attempt-1.json")).read_text())
            self.assertEqual(attempt["raw_output"], '{"incomplete":')
            self.assertIsNone(attempt["candidate"])
            self.assertIn("unparsed", attempt["validation_error"])
        self.assertEqual(len(calls), 2)

    def test_source_transport_failure_is_saved_without_retry(self):
        calls = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def parse(self, **kwargs):
                calls.append(kwargs)
                raise TimeoutError("offline transport failure")
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([
            {"source_id": "source-d", "excerpt": "Exact original result."}
        ]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            with self.assertRaises(TimeoutError):
                source_analysis(markdown, Path(directory), "offline-model")
            attempts = list((Path(directory) / "source-readings").glob("*.attempt-*.json"))
            self.assertEqual(len(attempts), 1)
            self.assertIn("TimeoutError", json.loads(attempts[0].read_text())["validation_error"])
        self.assertEqual(len(calls), 1)

    def test_cached_source_reading_keeps_every_code_owned_provenance_field(self):
        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            @property
            def responses(self): return self
            def parse(self, **kwargs):
                return SimpleNamespace(output_text="{}", output_parsed=SimpleNamespace(model_dump=lambda: {
                    "use_in_report": False, "observations": [], "omission_reason": "무관한 자료"}))
        source = {"source_id": "source-e", "title": "Original title", "url": "https://example.test/e",
                  "citation_key": "WEB_original", "role": "market", "technology_ids": ["SW-01"],
                  "excerpt": "Exact original result."}
        markdown = "<!-- USABLE_SOURCE_REPORTS_JSON\n" + json.dumps([source]) + "\nEND_USABLE_SOURCE_REPORTS_JSON -->"
        with tempfile.TemporaryDirectory() as directory, patch("pipeline.governance.openai_client", return_value=Client()):
            output = Path(directory)
            source_analysis(markdown, output, "offline-model")
            aggregate = output / "report.source-analysis.json"
            original = json.loads(aggregate.read_text())
            for field, changed in (("title", "Wrong title"), ("role", "technical"), ("technology_ids", ["HW-01"])):
                modified = json.loads(json.dumps(original))
                modified["sources"][0][field] = changed
                aggregate.write_text(json.dumps(modified))
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "identity differs"):
                    source_analysis(markdown, output, "offline-model")


if __name__ == "__main__":
    unittest.main()
