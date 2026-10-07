"""Offline integration of the real OW graph, artifact store, bridge and checkpoint.

The saved research bundle is real checked-in input. Perspective judgments,
report bytes and Quality decisions here are synthetic control fixtures. They do
not measure source quality, maturity, or the quality of a compiled report.
"""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import ROOT
from pipeline.contracts import CATALOG, all_cells
from pipeline.inputs import load_inputs
from pipeline.planner import create_plan
from pipeline.research_input import load_saved_research
from pipeline.worker_adapters import merge_role_result


TARGET = {"role": "market", "technology_id": "HW-01", "criterion_id": "standardization"}


def portable_role(role, *, marker="prior", cells=None):
    """Match runtime's portable schemas, including the actual domain wrapper."""
    selected = {(c["technology_id"], c["criterion_id"])
                for c in (cells if cells is not None else all_cells([role]))}
    if role == "domain":
        rows = []
        for technology in ("SW-01", "HW-01"):
            criteria = [{"criterion_id": criterion, "judgment": "unknown",
                         "target_alignment": "unknown", "basis": "none", "evidence_ids": [],
                         "conclusion": f"OFFLINE {marker}: {technology}/{criterion}",
                         "rationale": "Synthetic unknown fixture; no research performed.",
                         "conditions": [], "gaps": ["Offline fixture"], "need_more": []}
                        for criterion in CATALOG[role] if (technology, criterion) in selected]
            if criteria:
                rows.append({"technology_id": technology, "technology_name": technology,
                             "status": "unknown", "criteria": criteria,
                             "overall_summary": "Offline unknown", "key_tradeoffs": []})
        return {"assessments": {"domain": {"role": "domain", "status": "unknown",
                "round": 0, "assessments": rows, "domain_name": "Offline cloud",
                "cross_technology_tradeoffs": [], "unresolved_questions": [],
                "disclaimer": "OFFLINE TEST ONLY"}}}
    if role == "market":
        return {"result": {"status": "unknown", "execution_status": "completed",
                "assessments": [{"tech_id": technology, "criterion_id": criterion,
                    "judgment": f"OFFLINE {marker}: {technology}/{criterion}",
                    "basis": "unknown", "relation_to_technology": "exact", "evidence_ids": [],
                    "conditions": [], "metric": None, "gaps": ["Offline fixture"],
                    "verdict": "unknown", "citations": [], "context_findings": [],
                    "generation_method": "model_synthesis", "supporting_materials": []}
                    for technology in ("SW-01", "HW-01") for criterion in CATALOG[role]
                    if (technology, criterion) in selected]},
                "evidence": {}, "sources": {}, "claims": {}, "offline_test_only": True}
    return {"execution_status": "completed", "result": {"by_technology": {
            technology: {"claims": [], "gaps": [f"OFFLINE {marker}: {technology}"]}
            for technology in ("SW-01", "HW-01")
            if (technology, "stakeholder_impact") in selected}},
            "evidence": {}, "offline_test_only": True}


class OfflineBoundaries:
    """Only model/tool/generation boundaries are fake; routing runs unchanged."""

    def __init__(self, *, routes=("passed",), fail_roles=(), dependencies=None):
        self.routes = list(routes)
        self.fail_roles = set(fail_roles)
        self.dependencies = dependencies or {}
        self.plans, self.workers, self.reviews, self.trls = [], [], [], []
        self.reports, self.qualities, self.parsed_reports = [], [], []

    def planner(self, cells, **kwargs):
        self.plans.append(deepcopy({"cells": cells, **kwargs}))

        def respond(instructions, prompt, model):
            payload = json.loads(prompt)
            eligible = payload["eligible_cells"]
            roles = list(dict.fromkeys(cell["role"] for cell in eligible))
            return {"tasks": [{"role": role,
                    "active_cells": [{k: v for k, v in cell.items() if k != "role"}
                                     for cell in eligible if cell["role"] == role],
                    "reason": "OFFLINE TEST ONLY: group the requested cells by their owner.",
                    "dependency_roles": []}
                    for role in roles]}

        tasks = create_plan(cells, responder=respond, **kwargs)
        # Production planning rejects cross-role dependencies because current
        # workers cannot consume another role's result. A few graph-control
        # tests inject them explicitly to exercise blocked/resume mechanics.
        ids = {task["role"]: task["task_id"] for task in tasks}
        for task in tasks:
            task["dependency_ids"] = [ids[role]
                                      for role in self.dependencies.get(task["role"], [])]
        return tasks

    def worker(self, task, bundle, request, **kwargs):
        self.workers.append(deepcopy(task))
        if task["role"] in self.fail_roles:
            raise ValueError("OFFLINE TEST ONLY: terminal provider failure")
        return portable_role(task["role"], marker=f"revision-{task['plan_revision']}",
                             cells=task["active_cells"])

    def trl(self, state, **kwargs):
        self.trls.append(deepcopy(state))
        # Real bridge already supplies explicit unknown levels. No TRL is invented.
        return deepcopy(state["assessments"]["technical"])

    def review(self, state, **kwargs):
        from pipeline.review_bridge import run_review
        self.reviews.append(deepcopy(state))
        return run_review(state, **kwargs)

    def report(self, markdown, output_dir, **kwargs):
        from report_agent.parser import parse_report_input
        self.reports.append({"markdown": markdown, "options": deepcopy(kwargs)})
        self.parsed_reports.append(parse_report_input(markdown,
            allow_unreviewed=kwargs["draft"], allow_attributed_draft=kwargs["attribution_first"]))
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        tex, pdf = output_dir / "offline.tex", output_dir / "offline.pdf"
        tex.write_text("% OFFLINE TEST ONLY: report generation boundary\n")
        pdf.write_bytes(b"%PDF-OFFLINE-TEST-ONLY\n")
        return {"tex_path": str(tex), "pdf_path": str(pdf)}

    def quality(self, **kwargs):
        self.qualities.append(deepcopy(kwargs))
        route = self.routes[min(len(self.qualities) - 1, len(self.routes) - 1)]
        requests = []
        if route == "report_repair":
            requests = [{"target": "report", "role": None, "technology_ids": [],
                         "criterion_ids": [], "claim_ids": [], "evidence_ids": [],
                         "instructions": "OFFLINE TEST ONLY: repair this report's wording."}]
        elif route == "upstream_replan":
            requests = [{"target": "upstream", "role": "market", "technology_ids": ["HW-01"],
                         "criterion_ids": ["standardization"], "claim_ids": [], "evidence_ids": [],
                         "instructions": "OFFLINE TEST ONLY: recheck HW standardization."}]
        elif route == "technical_replan":
            route = "upstream_replan"
            requests = [{"target": "upstream", "role": "technical", "technology_ids": ["SW-01"],
                         "criterion_ids": ["maturity"], "claim_ids": [], "evidence_ids": [],
                         "instructions": "OFFLINE TEST ONLY: recheck the TRL justification."}]
        return {"route": route, "attempt": kwargs["attempt"], "repair_requests": requests,
                "failure_type": None if route == "passed" else "offline_synthetic_feedback",
                "offline_test_only": True}


class ScopedExecutionValidationTests(unittest.TestCase):
    def test_actual_domain_wrapper_replaces_only_active_criterion(self):
        prior = portable_role("domain")
        before = deepcopy(prior)
        cells = [{"technology_id": "HW-01", "criterion_id": "quality"}]
        incoming = portable_role("domain", marker="repair", cells=cells)
        merged = merge_role_result("domain", prior, incoming, cells)
        rows = merged["assessments"]["domain"]["assessments"]
        old_rows = before["assessments"]["domain"]["assessments"]
        self.assertEqual(rows[0], old_rows[0])
        for current, old in zip(rows[1]["criteria"], old_rows[1]["criteria"]):
            self.assertEqual(current, incoming["assessments"]["domain"]["assessments"][0]["criteria"][0]
                             if current["criterion_id"] == "quality" else old)
        self.assertEqual(prior, before)

    def test_requested_domain_cell_cannot_be_satisfied_by_an_unrelated_row(self):
        prior = portable_role("domain")
        incoming = portable_role("domain", cells=[{"technology_id": "HW-01", "criterion_id": "capacity"}])
        with self.assertRaises(ValueError):
            merge_role_result("domain", prior, incoming,
                              [{"technology_id": "HW-01", "criterion_id": "quality"}])


class OrchestrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        request, _, saved, mode = load_inputs(ROOT / "config/pipeline.json")
        assert mode == "saved"
        cls.saved_request, cls.saved_bundle = request, load_saved_research(saved)

    def setUp(self):
        from pipeline.graph import PipelineContext, build_graph, initial_state
        self.PipelineContext, self.build_graph, self.initial_state = PipelineContext, build_graph, initial_state
        self.directory = tempfile.TemporaryDirectory(prefix="ow-offline-")
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        # The actual Review must never request an online auditor for unknown TRL.
        guard = patch("team_review.review.call_trl_grounding",
                      side_effect=AssertionError("Offline fixture unexpectedly requested a live TRL audit"))
        guard.start()
        self.addCleanup(guard.stop)

    def context(self, fake, **options):
        return self.PipelineContext(output_dir=self.output,
            bundle=deepcopy(self.saved_bundle), request=deepcopy(self.saved_request),
            run_id="offline-ow", as_of="2026-10-07", model="offline-test", draft=True,
            worker=fake.worker, planner=fake.planner, review=fake.review, trl=fake.trl,
            report=fake.report, quality=fake.quality, **options)

    def accepted(self, context):
        return {role: context.store.put(f"fixtures/{role}.json", portable_role(role)) for role in CATALOG}

    def test_judge_model_change_rejudges_without_repeating_research_or_report(self):
        fake = OfflineBoundaries()
        context = self.context(fake)
        first = self.invoke(context, accepted=self.accepted(context))
        self.assertEqual(fake.qualities[-1]["model"], "offline-test")
        changed = self.context(fake, judge_model="offline-independent-judge")
        second = self.invoke(changed, accepted=first["accepted_refs"])
        self.assertEqual(second["phase"], "content_quality_pass")
        self.assertEqual(fake.qualities[-1]["model"], "offline-independent-judge")
        self.assertEqual(len(fake.qualities), 2)
        self.assertEqual(len(fake.reports), 1)
        self.assertEqual(len(fake.reviews), 1)
        self.assertEqual(len(fake.trls), 1)
        limited = self.context(fake, judge_model="offline-independent-judge", max_judge_calls=32)
        third = self.invoke(limited, accepted=second["accepted_refs"])
        self.assertEqual(third["phase"], "content_quality_pass")
        self.assertEqual(fake.qualities[-1]["max_judge_calls"], 32)
        self.assertEqual(len(fake.qualities), 3)
        self.assertEqual(len(fake.reports), 1)

    def invoke(self, context, *, accepted=None, pending=None, **kwargs):
        graph = self.build_graph(context)
        result = graph.invoke(self.initial_state(context, accepted_refs=accepted,
                              pending_cells=pending), {"recursion_limit": 60}, **kwargs)
        return result

    def test_complete_prior_requires_zero_workers_and_still_runs_report_quality(self):
        fake = OfflineBoundaries()
        context = self.context(fake)
        refs = self.accepted(context)
        result = self.invoke(context, accepted=refs)
        self.assertEqual(fake.workers, [])
        self.assertEqual(result["accepted_refs"], refs)
        self.assertEqual(result["phase"], "content_quality_pass")
        self.assertEqual((len(fake.reports), len(fake.qualities)), (1, 1))
        self.assertEqual(len(fake.parsed_reports), 1)

    def test_missing_market_hw_standardization_dispatches_only_that_cell(self):
        fake = OfflineBoundaries()
        context = self.context(fake, stop_after="market")
        refs = self.accepted(context)
        prior = context.store.get(refs["market"])
        result = self.invoke(context, accepted=refs, pending=[TARGET])
        self.assertEqual(len(fake.workers), 1)
        self.assertEqual(fake.workers[0]["role"], "market")
        self.assertEqual(fake.workers[0]["active_cells"], [{k: v for k, v in TARGET.items() if k != "role"}])
        self.assertEqual(result["accepted_refs"]["domain"], refs["domain"])
        self.assertEqual(result["accepted_refs"]["stakeholders"], refs["stakeholders"])
        merged = context.store.get(result["accepted_refs"]["market"])
        old_rows = {(r["tech_id"], r["criterion_id"]): r for r in prior["result"]["assessments"]}
        for row in merged["result"]["assessments"]:
            key = row["tech_id"], row["criterion_id"]
            if key == ("HW-01", "standardization"):
                self.assertIn("revision-1", row["judgment"])
            else:
                self.assertEqual(row, old_rows[key])
        self.assertEqual(result["phase"], "stopped")

    def test_failed_worker_is_terminal_and_join_preserves_successful_roles(self):
        fake = OfflineBoundaries(fail_roles={"market"})
        context = self.context(fake, max_replans=0)
        result = self.invoke(context)
        self.assertEqual(Counter(t["role"] for t in fake.workers), Counter(CATALOG.keys()))
        statuses = {outcome["role"]: outcome["status"] for outcome in result["task_outcomes"].values()}
        self.assertEqual(statuses, {"domain": "finished", "stakeholders": "finished", "market": "failed"})
        self.assertEqual(set(result["accepted_refs"]), {"domain", "stakeholders"})
        self.assertEqual(result["phase"], "review_required")
        self.assertEqual(result["termination_reason"], "worker_failure_limit")
        self.assertEqual(fake.reports, [])
        events = [json.loads(line) for line in (self.output / "events.jsonl").read_text().splitlines()]
        self.assertTrue(any(e.get("event") == "join_complete" and e["terminal_tasks"] == 3 for e in events))

    def test_failed_dependency_is_blocked_without_starting_its_worker(self):
        fake = OfflineBoundaries(fail_roles={"domain"}, dependencies={"market": ["domain"]})
        context = self.context(fake, max_replans=0)
        result = self.invoke(context)
        self.assertEqual({t["role"] for t in fake.workers}, {"domain", "stakeholders"})
        outcomes = {o["role"]: o for o in result["task_outcomes"].values()}
        self.assertEqual(outcomes["market"]["status"], "blocked_dependency")
        self.assertEqual(outcomes["market"]["dependency_ids"], [outcomes["domain"]["task_id"]])
        self.assertEqual(result["phase"], "review_required")

    def test_real_domain_failed_wrapper_is_terminal_failure_not_an_accepted_role(self):
        fake = OfflineBoundaries()
        original_worker = fake.worker

        def returned_failure(task, bundle, request, **kwargs):
            output = original_worker(task, bundle, request, **kwargs)
            if task["role"] == "domain":
                output["assessments"]["domain"]["status"] = "failed"
                output["errors"] = {"offline-error": {"role": "domain", "type": "InputContractError",
                    "retryable": False, "message": "OFFLINE TEST ONLY: actual node failure envelope"}}
            return output

        fake.worker = returned_failure
        context = self.context(fake, max_replans=0)
        result = self.invoke(context)
        outcomes = {o["role"]: o for o in result["task_outcomes"].values()}
        self.assertEqual(outcomes["domain"]["status"], "failed")
        self.assertNotIn("domain", result["accepted_refs"])
        self.assertEqual(result["phase"], "review_required")
        self.assertEqual(fake.reports, [])

    def test_report_repair_runs_two_quality_checks_without_researching_again(self):
        fake = OfflineBoundaries(routes=("report_repair", "passed"))
        context = self.context(fake)
        refs = self.accepted(context)
        result = self.invoke(context, accepted=refs)
        self.assertEqual(fake.workers, [])
        self.assertEqual((len(fake.reviews), len(fake.reports), len(fake.qualities)), (1, 2, 2))
        self.assertEqual([q["attempt"] for q in fake.qualities], [1, 2])
        self.assertIn("revision_feedback", fake.reports[1]["options"])
        self.assertEqual(fake.reports[1]["options"]["revision_candidate"],
                         "% OFFLINE TEST ONLY: report generation boundary\n")
        self.assertEqual(result["phase"], "content_quality_pass")
        self.assertEqual(result["accepted_refs"], refs)

    def test_upstream_quality_request_replans_exact_market_cell_and_preserves_other_roles(self):
        fake = OfflineBoundaries(routes=("upstream_replan", "passed"))
        context = self.context(fake)
        refs = self.accepted(context)
        result = self.invoke(context, accepted=refs)
        self.assertEqual(len(fake.workers), 1)
        self.assertEqual(fake.plans[1]["cells"], [TARGET])
        self.assertEqual(fake.workers[0]["plan_revision"], 2)
        self.assertEqual(fake.workers[0]["operation"], "reassess")
        self.assertEqual(fake.workers[0]["feedback"], ["OFFLINE TEST ONLY: recheck HW standardization."])
        self.assertEqual(result["accepted_refs"]["domain"], refs["domain"])
        self.assertEqual(result["accepted_refs"]["stakeholders"], refs["stakeholders"])
        self.assertEqual(len(fake.qualities), 2)
        self.assertEqual(result["phase"], "content_quality_pass")

    def test_quality_repair_stops_at_explicit_attempt_bound(self):
        fake = OfflineBoundaries(routes=("report_repair",))
        context = self.context(fake, max_quality_attempts=2)
        result = self.invoke(context, accepted=self.accepted(context))
        self.assertEqual((len(fake.reports), len(fake.qualities)), (2, 2))
        self.assertEqual(result["phase"], "failed_quality")
        self.assertEqual(result["termination_reason"], "quality_attempt_limit")

    def test_quality_trl_feedback_regenerates_technical_without_perspective_workers(self):
        fake = OfflineBoundaries(routes=("technical_replan", "passed"))
        context = self.context(fake)
        refs = self.accepted(context)
        result = self.invoke(context, accepted=refs)
        self.assertEqual(fake.workers, [])
        self.assertEqual([plan["cells"] for plan in fake.plans], [[], []])
        self.assertEqual(len(fake.trls), 2)
        self.assertEqual(fake.trls[-1]["config"]["trl_feedback"],
                         ["OFFLINE TEST ONLY: recheck the TRL justification."])
        self.assertEqual(result["accepted_refs"], refs)
        self.assertEqual(len(fake.qualities), 2)
        self.assertEqual(result["phase"], "content_quality_pass")

    def test_sqlite_resume_keeps_finished_parallel_workers_and_runs_only_waiting_dependency(self):
        from pipeline.checkpoint import SQLiteCheckpoint
        fake = OfflineBoundaries(dependencies={"market": ["domain"]})
        context = self.context(fake)
        checkpoint_path = self.output / "checkpoint.sqlite"
        config = {"configurable": {"thread_id": context.run_id}, "max_concurrency": 2,
                  "recursion_limit": 60}
        saver = SQLiteCheckpoint(checkpoint_path)
        graph = self.build_graph(context, checkpointer=saver)
        partial = graph.invoke(self.initial_state(context), config, interrupt_after=["worker"])
        self.assertEqual({o["role"] for o in partial["task_outcomes"].values()}, {"domain", "stakeholders"})
        self.assertTrue(graph.get_state(config).next)
        saver.close()
        before = deepcopy(fake.workers)
        restored = SQLiteCheckpoint(checkpoint_path)
        try:
            fresh_context = self.context(fake)
            resumed_graph = self.build_graph(fresh_context, checkpointer=restored)
            result = resumed_graph.invoke(None, config)
            self.assertEqual(fake.workers[:len(before)], before)
            self.assertEqual([t["role"] for t in fake.workers[len(before):]], ["market"])
            self.assertEqual(len(fake.plans), 1)
            self.assertEqual(result["phase"], "content_quality_pass")
            self.assertFalse(resumed_graph.get_state(config).next)
            self.assertEqual(len(fake.qualities), 1)
        finally:
            restored.close()

    def test_nested_role_graphs_do_not_write_model_objects_to_root_checkpoint(self):
        """Real role graphs stay local when invoked inside the persisted root graph."""
        from langgraph.graph import END, START, StateGraph
        from market_agent.node import run_market
        from market_agent.parser import read_input
        from market_agent.providers import AdaptiveFixtureAnalyst, FixtureWeb
        from stakeholder_agent.agent import run_stakeholder
        from stakeholder_agent.demo import DemoModel, DemoWeb
        from pipeline.checkpoint import SQLiteCheckpoint

        market_input = read_input(
            ROOT / "agent/market/market_agent/fixtures/input.md")

        def run_nested(_state):
            stakeholder = run_stakeholder(
                deepcopy(self.saved_bundle["papers"]), request=deepcopy(self.saved_request),
                as_of="2026-10-07", run_id="offline-nested", mode="fixture",
                model=DemoModel(), web=DemoWeb())
            market = run_market(
                market_input, FixtureWeb(), AdaptiveFixtureAnalyst(), mode="fixture")
            return {"status": {
                "stakeholder": stakeholder["execution_status"],
                "market": market["result"].execution_status,
            }}

        builder = StateGraph(dict)
        builder.add_node("roles", run_nested)
        builder.add_edge(START, "roles")
        builder.add_edge("roles", END)
        saver = SQLiteCheckpoint(self.output / "nested-checkpoint.sqlite")
        try:
            graph = builder.compile(checkpointer=saver)
            result = graph.invoke({"status": "starting"}, {
                "configurable": {"thread_id": "nested-role-fixture"}})
            self.assertEqual(result["status"], {
                "stakeholder": "completed", "market": "completed"})
        finally:
            saver.close()


if __name__ == "__main__":
    unittest.main()
