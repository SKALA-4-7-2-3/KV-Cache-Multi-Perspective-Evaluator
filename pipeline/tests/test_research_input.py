from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import research_input as research


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "rag/examples/results"


class ResearchProjectionTests(unittest.TestCase):
    def make_input(self):
        dossier = {
            "paper": {"paper_id": "paper-1", "title": "Test paper"},
            "analysis": {section: {"not_reported": []} for section in research._FIELD_ORDER},
            "claims": [],
        }
        run = {"schema_version": "1.0.0", "run": {"job_id": "test-run"}}
        return dossier, run, {}

    def add_claim(self, dossier, evidence, section, field, name, size=1_000, evidence_id=None):
        eid = evidence_id or name
        claim = {"text": name, "claim_type": "paper_reported", "evidence_ids": [eid],
                 "context_evidence_ids": [], "confidence": 0.9}
        dossier["analysis"][section].setdefault(field, []).append(claim)
        dossier["claims"].append({"claim_id": name, **claim})
        evidence.setdefault(eid, {
            "evidence_id": eid, "document_id": "paper-1", "source_kind": "paper",
            "snippet": "x" * size, "content_hash": "source-hash", "content_kind": "text",
            "locator": {"physical_page": 1, "section_path": [section]},
        })

    def assert_complete_references(self, paper, evidence):
        registry = {item["evidence_id"]: item for item in paper["evidence_registry"]}
        self.assertEqual(len(registry), len(paper["evidence_registry"]))
        for section in paper["analysis"].values():
            for field, rows in section.items():
                if field == "not_reported":
                    continue
                for claim in rows:
                    for eid in research._refs(claim):
                        self.assertIn(eid, registry)
        for eid, item in registry.items():
            self.assertEqual(item, research._paper_evidence(evidence[eid]))

    def test_fields_from_one_facet_do_not_starve_later_facets(self):
        dossier, run, evidence = self.make_input()
        for index, field in enumerate(research._FIELD_ORDER["technical_overview"]):
            self.add_claim(dossier, evidence, "technical_overview", field, f"overview-{index}")
        self.add_claim(dossier, evidence, "scope", "target_tasks", "scope")
        self.add_claim(dossier, evidence, "limitations", "author_stated", "limitation")
        original = deepcopy(dossier)
        with patch.object(research, "PAPER_CONTEXT_CHARS", 6_000):
            paper, manifest = research._project_paper(dossier, run, evidence)
        for section in research._FIELD_ORDER:
            self.assertTrue(any(rows for field, rows in paper["analysis"][section].items()
                                if field != "not_reported"), section)
        self.assertLessEqual(research._size(paper), 6_000)
        self.assertTrue(manifest["excluded_analysis"])
        self.assert_complete_references(paper, evidence)
        self.assertEqual(dossier, original)

    def test_oversized_first_claim_does_not_hide_a_later_fitting_claim(self):
        dossier, run, evidence = self.make_input()
        self.add_claim(dossier, evidence, "technical_overview", "problem_definition", "large", 10_000)
        self.add_claim(dossier, evidence, "technical_overview", "core_approach", "small", 300)
        self.add_claim(dossier, evidence, "scope", "target_tasks", "scope", 300)
        self.add_claim(dossier, evidence, "limitations", "author_stated", "limitation", 300)
        with patch.object(research, "PAPER_CONTEXT_CHARS", 4_000):
            paper, manifest = research._project_paper(dossier, run, evidence)
        self.assertIn("small", manifest["included_claim_ids"])
        self.assertIn("large", manifest["excluded_claim_ids"])
        self.assertIn({"path": "analysis.technical_overview.problem_definition[0]",
                       "reason": "bounded_context_budget"}, manifest["excluded_analysis"])
        self.assert_complete_references(paper, evidence)

    def test_shared_evidence_is_preserved_once(self):
        dossier, run, evidence = self.make_input()
        for section, field in [("technical_overview", "core_approach"),
                               ("scope", "target_tasks"), ("limitations", "author_stated")]:
            self.add_claim(dossier, evidence, section, field, section, 1_000, "shared")
        with patch.object(research, "PAPER_CONTEXT_CHARS", 3_000):
            paper, manifest = research._project_paper(dossier, run, evidence)
        self.assertEqual(manifest["included_evidence_ids"], ["shared"])
        self.assertEqual(len(manifest["included_claim_ids"]), 3)
        self.assert_complete_references(paper, evidence)

    def test_both_saved_results_fit_and_keep_all_three_facets(self):
        request = json.loads((ROOT / "config/pipeline.json").read_text())["request"]
        for name in ["technical-bge-e2e-two-papers", "technical-long-context-qa-datacenter"]:
            with self.subTest(result=name):
                bundle = research.load_saved_research(RESULTS / name)
                self.assertEqual(len(bundle["papers"]), 2)
                for paper, manifest in zip(bundle["papers"], bundle["context_manifest"]["papers"]):
                    self.assertLessEqual(research._size(paper), research.PAPER_CONTEXT_CHARS)
                    for section in research._FIELD_ORDER:
                        self.assertTrue(any(rows for field, rows in paper["analysis"][section].items()
                                            if field != "not_reported"), section)
                    self.assert_complete_references(paper, bundle["evidence"])
                    dossier = next(d for d in bundle["dossiers"]
                                   if d["paper"]["paper_id"] == paper["paper"]["paper_id"])
                    source_paths = {f"analysis.{section}.{field}[{index}]"
                                    for section, field, index, _ in research._analysis_rows(dossier)}
                    included = set(manifest["included_analysis_paths"])
                    excluded = {row["path"] for row in manifest["excluded_analysis"]}
                    self.assertEqual(source_paths, included | excluded)
                    self.assertFalse(included & excluded)
                state = research.to_domain_state(bundle, request, run_id="test-run", as_of="2026-09-22")
                self.assertEqual(len(state["assessments"]["technical"]["technologies"]), 2)
                self.assertLessEqual(state["context_manifest"]["domain_input_chars"],
                                     research.DOMAIN_CONTEXT_CHARS)

    def test_tampered_artifacts_are_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "evidence.json").write_text("[]")
            (root / "run.json").write_text(json.dumps({
                "schema_version": "1.0.0", "status": "succeeded",
                "artifacts": [{"path": "evidence.json", "sha256": "invalid"}],
            }))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                research.load_saved_research(root)


if __name__ == "__main__":
    unittest.main()
