from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from kv_domain_agent.adapters import adapt_paper_analyses
from kv_domain_agent.agent import DomainEvaluator, InputContractError, OutputContractError
from kv_domain_agent.mock_model import DeterministicMockModel
from kv_domain_agent.models import DomainCriterion
from kv_domain_agent.node import make_domain_node
from kv_domain_agent.state import merge_role_assessments, merge_strict_by_key


ROOT = Path(__file__).resolve().parents[1]


def load_state():
    return json.loads((ROOT / "examples" / "input_state.json").read_text(encoding="utf-8"))


class CapturingModel(DeterministicMockModel):
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return super().invoke(messages)


class InventingModel(DeterministicMockModel):
    def invoke(self, messages):
        output = super().invoke(messages)
        output["assessments"][0]["criteria"][0]["evidence_ids"] = ["MADE-UP-ID"]
        return output


class CrossTechnologyCitationModel(DeterministicMockModel):
    def invoke(self, messages):
        output = super().invoke(messages)
        sw = next(item for item in output["assessments"] if item["technology_id"] == "SW-01")
        capacity = next(item for item in sw["criteria"] if item["criterion_id"] == "capacity")
        capacity.update(
            {
                "judgment": "conditional",
                "target_alignment": "partial",
                "basis": "fact",
                "evidence_ids": ["DEMO-HW-CAP-001"],
            }
        )
        return output


def sample_paper_analysis(*, title: str, evidence_id: str, text: str):
    return {
        "schema_version": "1.1.0",
        "status": "succeeded",
        "paper": {
            "paper_id": f"paper-{evidence_id}",
            "title": title,
            "arxiv_id": None,
            "authors": [],
            "page_count": 1,
            "source_hash": "hash",
            "source_path": "paper.pdf",
            "abstract": "abstract",
        },
        "analysis": {
            "technical_overview": {
                "problem_definition": [],
                "core_approach": [
                    {
                        "claim_type": "author_claim",
                        "confidence": 0.9,
                        "context_evidence_ids": [],
                        "evidence_ids": [evidence_id],
                        "text": text,
                    }
                ],
                "novelty": [],
            },
            "scope": {
                "evaluated_settings": [
                    {
                        "claim_type": "author_claim",
                        "confidence": 0.9,
                        "context_evidence_ids": [],
                        "evidence_ids": [evidence_id],
                        "text": "long-context LLM inference on GPU",
                    }
                ],
                "operating_conditions": [],
                "target_tasks": [],
                "out_of_scope": [],
            },
            "limitations": {
                "author_stated": [],
                "generalization_constraints": [],
                "compute_constraints": [],
                "data_constraints": [],
                "reproducibility_constraints": [],
                "inferred": [],
            },
        },
        "evidence_registry": [
            {
                "evidence_id": evidence_id,
                "chunk_id": evidence_id,
                "content_hash": "hash",
                "content_kind": "text",
                "document_id": "raw-document",
                "page": 1,
                "section": "Abstract",
                "snippet": text,
                "source_kind": "paper",
            }
        ],
        "quality": {},
        "run": {"finished_at": "2026-09-21T00:00:00Z"},
        "diagnostics": [],
    }


class DomainAgentTests(unittest.TestCase):
    def test_offline_run_has_two_technologies_and_ten_criteria(self):
        result = DomainEvaluator(DeterministicMockModel(), allow_demo=True).evaluate(load_state())
        self.assertEqual(len(result.assessments), 2)
        for technology in result.assessments:
            self.assertEqual(
                {item.criterion_id for item in technology.criteria},
                set(DomainCriterion),
            )

    def test_only_referenced_evidence_is_sent_to_model(self):
        state = load_state()
        state["evidence"]["UNREFERENCED"] = {
            "id": "UNREFERENCED",
            "doc_id": "X",
            "excerpt": "must not reach the domain model",
            "criterion_ids": [],
        }
        model = CapturingModel()
        DomainEvaluator(model, allow_demo=True).evaluate(state)
        payload = json.loads(model.messages[-1][1])
        self.assertNotIn("UNREFERENCED", payload["evidence"])

    def test_invented_evidence_id_is_rejected(self):
        with self.assertRaises(OutputContractError):
            DomainEvaluator(InventingModel(), allow_demo=True).evaluate(load_state())

    def test_cross_technology_evidence_is_rejected(self):
        with self.assertRaises(OutputContractError):
            DomainEvaluator(CrossTechnologyCitationModel(), allow_demo=True).evaluate(load_state())

    def test_demo_evidence_is_blocked_in_real_execution(self):
        with self.assertRaises(InputContractError):
            DomainEvaluator(DeterministicMockModel()).evaluate(load_state())

    def test_no_evidence_returns_unknown_without_calling_model(self):
        state = load_state()
        state["evidence"] = {}

        class MustNotRun:
            def invoke(self, _):
                raise AssertionError("model should not be called")

        result = DomainEvaluator(MustNotRun()).evaluate(state)
        self.assertEqual(result.status.value, "unknown")
        self.assertTrue(
            all(
                criterion.judgment.value == "unknown"
                for technology in result.assessments
                for criterion in technology.criteria
            )
        )

    def test_node_writes_only_its_role_key(self):
        update = make_domain_node(
            structured_model=DeterministicMockModel(), allow_demo=True
        )(load_state())
        self.assertEqual(set(update["assessments"]), {"domain"})

    def test_node_converts_bad_input_to_failed_state(self):
        state = load_state()
        del state["config"]["domain"]
        update = make_domain_node(structured_model=DeterministicMockModel())(state)
        self.assertEqual(update["assessments"]["domain"]["status"], "failed")
        self.assertEqual(len(update["errors"]), 1)

    def test_reducers_are_idempotent_and_reject_same_round_conflicts(self):
        left = {"domain": {"round": 0, "value": "a"}}
        self.assertEqual(merge_role_assessments(left, copy.deepcopy(left)), left)
        with self.assertRaises(ValueError):
            merge_role_assessments(left, {"domain": {"round": 0, "value": "b"}})
        self.assertEqual(
            merge_role_assessments(left, {"domain": {"round": 1, "value": "b"}}),
            {"domain": {"round": 1, "value": "b"}},
        )
        with self.assertRaises(ValueError):
            merge_strict_by_key({"E1": {"x": 1}}, {"E1": {"x": 2}})

    def test_adapter_normalizes_unmodified_paper_analysis_outputs(self):
        state = adapt_paper_analyses(
            load_state(),
            sw_analysis=sample_paper_analysis(
                title="RDKV",
                evidence_id="ev-sw",
                text="RDKV reduces KV cache memory on a GPU and reports accuracy.",
            ),
            hw_analysis=sample_paper_analysis(
                title="Photonic-CXL",
                evidence_id="ev-hw",
                text="A photonic CXL appliance provides shared memory for LLM inference.",
            ),
        )
        self.assertEqual(state["assessments"]["technical"]["status"], "completed")
        self.assertEqual(
            set(state["evidence"]),
            {"SW-01::ev-sw", "HW-01::ev-hw"},
        )
        self.assertFalse(any(item["is_demo"] for item in state["evidence"].values()))
        result = DomainEvaluator(DeterministicMockModel()).evaluate(state)
        self.assertEqual(len(result.assessments), 2)
        self.assertTrue(any(item.status.value == "completed" for item in result.assessments))


if __name__ == "__main__":
    unittest.main()
