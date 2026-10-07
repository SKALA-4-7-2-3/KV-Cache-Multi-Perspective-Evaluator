"""Offline CLI contract tests, not real perspective research or paper TRL estimates.

The checked-in saved RAG bundle and bridge/Review/report parser run unchanged.
Only provider boundaries are faked. Empty perspective outputs deliberately stay
unknown, and the supported TRL decisions below are synthetic test decisions.
"""

from contextlib import ExitStack, contextmanager, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline import ROOT
from pipeline.__main__ import main
from pipeline.tests.test_orchestration import portable_role
from report_agent.parser import parse_report_input


class TRLPipelineTests(unittest.TestCase):
    @contextmanager
    def boundaries(self):
        parsed_reports = []

        def plan(instructions, prompt, model):
            payload = json.loads(prompt)
            cells = payload["eligible_cells"]
            roles = list(dict.fromkeys(cell["role"] for cell in cells))
            return {"tasks": [{"role": role, "active_cells": [
                {k: v for k, v in cell.items() if k != "role"}
                for cell in cells if cell["role"] == role],
                "reason": "OFFLINE TEST ONLY: select each missing perspective cell exactly once.",
                "dependency_roles": []} for role in roles]}

        def draft(model, instructions, prompt):
            payload = json.loads(prompt)
            if payload["technology_id"] == "HW-01":
                return {"checks": []}
            self.assertTrue(payload["evidence"])
            source = payload["evidence"][0]
            self.assertEqual(source["doc_id"], "SW-01")
            return {"checks": [
                {"level": level, "status": "met", "evidence_ids": [source["id"]],
                 "reason": "OFFLINE TEST ONLY: synthetic stage proposal for contract testing."}
                for level in range(1, 5)]}

        def audit(payload, *, model):
            return {"checks": [
                {"item_id": item["item_id"], "verdict": "supported",
                 "reason": "OFFLINE TEST ONLY: synthetic semantic approval, not source evaluation.",
                 "evidence_ids": list(item["evidence"])}
                for item in payload["items"]]}

        def report(markdown, output_dir, *, model, draft, attribution_first):
            self.assertTrue(draft)
            self.assertTrue(attribution_first)
            parsed_reports.append(parse_report_input(
                markdown, allow_unreviewed=draft, allow_attributed_draft=attribution_first))
            # Hash-checkable offline bytes; no model generation or compilation.
            output_dir.mkdir(parents=True, exist_ok=True)
            tex, pdf = output_dir / "OFFLINE-TEST-PLACEHOLDER.tex", output_dir / "OFFLINE-TEST-PLACEHOLDER.pdf"
            tex.write_text("% OFFLINE TEST ONLY: report boundary\n")
            pdf.write_bytes(b"%PDF-OFFLINE-TEST-ONLY\n")
            return {"tex_path": str(tex), "pdf_path": str(pdf)}

        with ExitStack() as stack:
            stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
            stack.enter_context(patch.dict(os.environ, {
                "OPENAI_API_KEY": "offline-test-placeholder", "TAVILY_API_KEY": "offline-test-placeholder"}))
            mocks = {
                "planner": stack.enter_context(patch("pipeline.planner._respond", side_effect=plan)),
                "domain": stack.enter_context(patch("pipeline.runtime.run_domain",
                    return_value=portable_role("domain"))),
                "stakeholders": stack.enter_context(patch("pipeline.runtime.run_stakeholders",
                    return_value={**portable_role("stakeholders"), "execution_status": "unknown"})),
                "market": stack.enter_context(patch("pipeline.runtime.run_market",
                    return_value=portable_role("market"))),
                "draft": stack.enter_context(patch("pipeline.trl._respond", side_effect=draft)),
                "audit": stack.enter_context(patch("team_review.review.call_trl_grounding", side_effect=audit)),
                "report": stack.enter_context(patch("pipeline.reporting.generate_report", side_effect=report)),
            }
            yield mocks, parsed_reports

    def run_cli(self, output, *, resume=False, rerun=()):
        argv = ["pipeline", "--input", str(ROOT / "config/pipeline.json"),
                "--output", str(output), "--model", "offline-test", "--as-of", "2026-10-07",
                "--draft", "--stop-after", "report"]
        if resume:
            argv.append("--resume")
        if rerun:
            argv.extend(["--rerun", *rerun])
        with patch.object(sys, "argv", argv), redirect_stdout(StringIO()):
            self.assertEqual(main(), 0)

    def test_cli_draft_delivers_final_trl_to_real_report_parser(self):
        with tempfile.TemporaryDirectory(prefix="trl-pipeline-") as directory, self.boundaries() as (mocks, parsed):
            output = Path(directory)
            self.run_cli(output)
            manifest = json.loads((output / "run.json").read_text())
            self.assertEqual(manifest["engine"], "orchestrator-workers")
            self.assertEqual(manifest["status"], "stopped")
            self.assertEqual(manifest["stop_after"], "report")
            state = json.loads((output / "state.result.json").read_text())
            self.assertEqual(set(state["accepted_refs"]), {"domain", "stakeholders", "market"})
            self.assertEqual(len(state["tasks"]), 3)
            self.assertEqual(len(state["task_outcomes"]), 3)
            self.assertTrue(all(outcome["status"] == "finished" for outcome in state["task_outcomes"].values()))
            self.assertTrue((output / "plans/plan-1.json").exists())
            self.assertTrue((output / "trl.output.json").exists())
            self.assertTrue((output / "review.output.json").exists())
            self.assertTrue((output / "report.output.json").exists())
            self.assertNotIn("quality_ref", state)
            self.assertEqual(mocks["planner"].call_count, 1)
            self.assertEqual(mocks["domain"].call_count, 1)
            self.assertTrue(mocks["domain"].call_args.kwargs["scoped"])
            self.assertEqual(mocks["draft"].call_count, 2)
            self.assertEqual(mocks["audit"].call_count, 1)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0].trl_assessments["SW-01"]["level"], 4)
            self.assertIsNone(parsed[0].trl_assessments["HW-01"]["level"])
            self.assertEqual(parsed[0].trl_assessments["SW-01"]["citation_keys"], ["SW01_RDKV"])
            review_input = json.loads((output / "review.input.json").read_text())
            for role in ("domain", "market", "stakeholders"):
                self.assertEqual(review_input["assessments"][role]["status"], "unknown")

    def test_resume_reuses_all_outputs_without_provider_calls(self):
        with tempfile.TemporaryDirectory(prefix="trl-pipeline-resume-") as directory, self.boundaries() as (mocks, parsed):
            output = Path(directory)
            self.run_cli(output)
            first_markdown = (output / "review.output.md").read_text()
            for mock in mocks.values():
                mock.reset_mock()
            self.run_cli(output, resume=True)
            for boundary, mock in mocks.items():
                self.assertEqual(mock.call_count, 0, boundary)
            self.assertEqual(len(parsed), 1)
            self.assertEqual((output / "review.output.md").read_text(), first_markdown)
            reparsed = parse_report_input(first_markdown, allow_unreviewed=True, allow_attributed_draft=True)
            self.assertEqual(reparsed.trl_assessments["SW-01"]["level"], 4)

    def test_explicit_report_rerun_preserves_research_and_trl_but_rebuilds_report(self):
        with tempfile.TemporaryDirectory(prefix="trl-ow-rerun-") as directory, self.boundaries() as (mocks, parsed):
            output = Path(directory)
            self.run_cli(output)
            for mock in mocks.values():
                mock.reset_mock()
            self.run_cli(output, resume=True, rerun=("report",))
            for boundary in ("planner", "domain", "stakeholders", "market", "draft", "audit"):
                self.assertEqual(mocks[boundary].call_count, 0, boundary)
            self.assertEqual(mocks["report"].call_count, 1)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[-1].trl_assessments["SW-01"]["level"], 4)

    def test_reporting_code_change_preserves_valid_unchanged_worker_outputs(self):
        from pipeline.artifacts import stage_fingerprint as actual_stage_fingerprint
        with tempfile.TemporaryDirectory(prefix="trl-components-") as directory, self.boundaries() as (mocks, parsed):
            output = Path(directory)
            self.run_cli(output)
            accepted = json.loads((output / "state.result.json").read_text())["accepted_refs"]
            for mock in mocks.values(): mock.reset_mock()
            # Simulate a changed reporting/Judge component, while the actual
            # role providers, prompts, input identity and locked dependencies stay.
            def changed_reporting(root, name):
                return ("changed-reporting-code" if name.startswith(("report", "quality"))
                        else actual_stage_fingerprint(root, name))
            with patch("pipeline.graph.fingerprint", return_value="changed-reporting-code"), patch(
                    "pipeline.graph.stage_fingerprint", side_effect=changed_reporting):
                self.run_cli(output,resume=True)
            for boundary in ("planner", "domain", "stakeholders", "market", "draft", "audit"):
                self.assertEqual(mocks[boundary].call_count,0,boundary)
            self.assertEqual(json.loads((output / "state.result.json").read_text())["accepted_refs"],accepted)
            self.assertEqual(mocks["report"].call_count,1)


if __name__ == "__main__":
    unittest.main()
