"""Offline TRL draft tests; fixtures do not assert either paper's real maturity."""

from copy import deepcopy
from importlib import import_module
from importlib.util import find_spec
import json
import unittest

import pipeline  # Registers the existing agent packages without importing research.
from team_review import review_node
from team_review.demo import make_input
from team_review.schema import RoleResult


TECHNOLOGIES = ("SW-01", "HW-01")
STAGE_EXCERPTS = {
    1: "The paper documents the basic mathematical principle of the mechanism.",
    2: "The algorithm and architecture define the technical concept and application purpose.",
    3: "A controlled experiment confirms the core hypothesis and reports its test conditions.",
    4: "Implemented core components are integrated and validated in a laboratory GPU test.",
    5: "Representative QA workloads validate the integrated components in the target environment.",
    6: "An integrated system prototype is demonstrated at representative scale.",
    7: "Simulation predicts a prototype's operation; no actual operational pilot was conducted.",
}


def make_state():
    """Reuse Review's shape, with canonical inherited-source records like the bridge."""
    state = make_input()
    state["config"].update(demo=False, source_reuse=True)
    state["evidence"] = {}
    for tech in TECHNOLOGIES:
        document = state["documents"][tech]
        document["title"] = f"TEST FIXTURE ONLY: {tech}"
        for level, excerpt in STAGE_EXCERPTS.items():
            eid = f"fixture-{tech}-stage-{level}"
            state["evidence"][eid] = {
                "id": eid, "doc_id": tech, "technology_ids": [tech],
                "excerpt": excerpt, "page": 1, "location": f"Test stage {level}",
                "method": "simulation" if level == 7 else "gpu_experiment" if level >= 3 else "analysis",
                "verified_source": False, "synthetic": False,
                "collected_at": "2026-09-21T18:00:00+09:00",
                "independence": "author", "technology_relevance": "direct",
                "source_verification": "inherited_source_record",
                "provenance": {"source_hash": document["sha256"],
                               "source_run_status": "succeeded", "original_evidence_id": eid},
            }
        for role in state["assessments"].values():
            for item in role["results"][tech]["items"]:
                item.update(evidence_ids=[f"fixture-{tech}-stage-1"], metrics=[])
        cell = state["assessments"]["technical"]["results"][tech]
        cell["trl_checks"] = {
            level: {"status": "unknown", "reason": "Original research has no stage-level TRL draft.",
                    "evidence_ids": []}
            for level in range(1, 10)
        }
        maturity = next(item for item in cell["items"] if item["criterion_id"] == "maturity")
        maturity.update(judgment="unknown", basis="unknown", conclusion="TRL 판단 보류",
                        evidence_ids=[], gaps=["No stage-level draft in the saved research."])
    # build_review_state already serializes the full Review schema, including defaults.
    state["assessments"]["technical"] = RoleResult.model_validate(
        state["assessments"]["technical"]).model_dump(mode="json")
    return state


def prompt_payload(prompt):
    """Accept a JSON prompt, including a JSON object following a short preamble."""
    decoder = json.JSONDecoder()
    for offset, char in enumerate(prompt):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(prompt[offset:])
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("technology_id") in TECHNOLOGIES:
            return value
    raise AssertionError("The model prompt must identify its technology with technology_id.")


class DraftResponder:
    """Fake only the model boundary; select real canonical IDs supplied in the prompt."""

    def __init__(self, checks):
        self.checks = checks
        self.calls = []

    def __call__(self, instructions, prompt):
        payload = prompt_payload(prompt)
        tech = payload["technology_id"]
        self.calls.append((tech, instructions, payload))
        return {"checks": deepcopy(self.checks(tech, payload))}


def met_through(tech, last):
    return [{"level": level, "status": "met", "reason": STAGE_EXCERPTS[level],
             "evidence_ids": [f"fixture-{tech}-stage-{level}"]}
            for level in range(1, last + 1)]


def add_operational_web_evidence(state, tech, *, identified=True, target_version="v1"):
    """An offline collector fixture explicitly supplies identity; no default certification."""
    state["config"]["trl_evidence_policy"] = "selected_implementation"
    doc_id, eid = f"fixture-web-{tech}", f"fixture-{tech}-operational"
    state["documents"][doc_id] = {
        **state["documents"][tech], "title": f"TEST FIXTURE ONLY: {tech} pilot",
        "url": f"https://example.invalid/{tech}/pilot", "kind": "web", "pages": None,
        "source_type": "official_product", "version": "collected-excerpt",
    }
    provenance = {"collector": "offline-test", "quote_matched": True}
    if identified:
        provenance.update(target_technology_id=tech, target_version=target_version,
                          target_identity_verified=True)
    state["evidence"][eid] = {
        "id": eid, "doc_id": doc_id, "technology_ids": [tech],
        "excerpt": "The selected v1 implementation's integrated prototype operated in an actual QA pilot.",
        "page": None, "location": "Test pilot record", "method": "operational",
        "synthetic": False, "verified_source": False, "collected_at": "2026-09-21T18:00:00+09:00",
        "technology_relevance": "direct", "source_verification": "collected_excerpt",
        "provenance": provenance,
    }
    return eid


def fake_supported_trl_auditor(payload):
    """Offline semantic-auditor boundary; fixture text is not a real TRL judgment."""
    return {"checks": [
        {"item_id": item["item_id"], "verdict": "supported",
         "reason": "Offline fixture auditor accepts this supplied stage-specific test evidence.",
         "evidence_ids": list(item["evidence"])}
        for item in payload["items"]
    ]}


class TRLAssessmentTests(unittest.TestCase):
    def generate(self, state, responder):
        self.assertIsNotNone(find_spec("pipeline.trl"),
                             "pipeline.trl must add the missing technical TRL draft stage")
        module = import_module("pipeline.trl")
        self.assertTrue(hasattr(module, "generate_trl_assessment"))
        result = module.generate_trl_assessment(state, model="offline-test", responder=responder)
        RoleResult.model_validate(result)
        return result

    def reviewed(self, state, technical):
        forwarded = deepcopy(state)
        forwarded["assessments"]["technical"] = technical
        return review_node(forwarded, trl_auditor=fake_supported_trl_auditor)["synthesis"]["trl"]

    def check(self, technical, tech, level):
        checks = technical["results"][tech]["trl_checks"]
        return checks[level] if level in checks else checks[str(level)]

    def test_saved_research_without_a_draft_cannot_produce_a_numeric_trl(self):
        state = make_state()
        trl = review_node(state)["synthesis"]["trl"]
        for tech in TECHNOLOGIES:
            self.assertIsNone(trl[tech]["level"])
            self.assertEqual([row["status"] for row in trl[tech]["checks"]], ["unknown"] * 9)

    def test_four_grounded_stages_reach_review_as_level_four(self):
        state = make_state()
        original = deepcopy(state)

        def draft(tech, payload):
            available = json.dumps(payload, ensure_ascii=False)
            for level in range(1, 5):
                self.assertIn(f"fixture-{tech}-stage-{level}", available)
                self.assertIn(STAGE_EXCERPTS[level], available)
            return met_through(tech, 4)

        responder = DraftResponder(draft)
        result = self.generate(state, responder)
        self.assertCountEqual([call[0] for call in responder.calls], TECHNOLOGIES)
        self.assertEqual(len(responder.calls), 2)
        self.assertEqual(state, original)
        for tech, trl in self.reviewed(state, result).items():
            self.assertEqual(trl["level"], 4, tech)
            self.assertEqual(trl["next_unconfirmed"]["level"], 5)
            maturity = next(item for item in result["results"][tech]["items"]
                            if item["criterion_id"] == "maturity")
            self.assertEqual(maturity["basis"], "inference")
            self.assertTrue(maturity["evidence_ids"])

    def test_model_draft_without_semantic_approval_cannot_produce_a_numeric_trl(self):
        state = make_state()
        result = self.generate(state, DraftResponder(lambda tech, payload: met_through(tech, 4)))
        forwarded = deepcopy(state)
        forwarded["assessments"]["technical"] = result
        reviewed = review_node(forwarded)["synthesis"]["trl"]
        for tech in TECHNOLOGIES:
            self.assertIsNone(reviewed[tech]["level"])
            self.assertEqual(reviewed[tech]["checks"][0]["status"], "unknown")

    def test_met_without_evidence_is_downgraded_before_review(self):
        state = make_state()
        responder = DraftResponder(lambda tech, payload: [
            {"level": 1, "status": "met", "reason": "Model asserts success without a source.",
             "evidence_ids": []}])
        result = self.generate(state, responder)
        for tech in TECHNOLOGIES:
            check = self.check(result, tech, 1)
            self.assertEqual(check["status"], "unknown")
            self.assertTrue(check["reason"].strip())
            self.assertEqual(check["evidence_ids"], [])
            self.assertIsNone(self.reviewed(state, result)[tech]["level"])

    def test_other_technology_evidence_cannot_support_a_stage(self):
        state = make_state()
        responder = DraftResponder(lambda tech, payload: [
            {"level": 1, "status": "met", "reason": STAGE_EXCERPTS[1],
             "evidence_ids": [f"fixture-{'HW-01' if tech == 'SW-01' else 'SW-01'}-stage-1"]}])
        result = self.generate(state, responder)
        for tech in TECHNOLOGIES:
            self.assertEqual(self.check(result, tech, 1)["status"], "unknown")
            self.assertEqual(self.check(result, tech, 1)["evidence_ids"], [])
            self.assertIsNone(self.reviewed(state, result)[tech]["level"])

    def test_stage_seven_simulation_is_not_operational_evidence(self):
        state = make_state()
        result = self.generate(state, DraftResponder(lambda tech, payload: met_through(tech, 7)))
        for tech in TECHNOLOGIES:
            self.assertEqual(self.check(result, tech, 7)["status"], "unknown")
            self.assertEqual(self.reviewed(state, result)[tech]["level"], 6)

    def test_identified_same_version_operational_source_can_support_stage_seven(self):
        state = make_state()
        ids = {tech: add_operational_web_evidence(state, tech) for tech in TECHNOLOGIES}

        def draft(tech, payload):
            self.assertIn(ids[tech], json.dumps(payload))
            return met_through(tech, 6) + [{
                "level": 7, "status": "met", "reason": state["evidence"][ids[tech]]["excerpt"],
                "evidence_ids": [ids[tech]]}]

        result = self.generate(state, DraftResponder(draft))
        for tech in TECHNOLOGIES:
            self.assertEqual(self.check(result, tech, 7)["status"], "met")
            self.assertEqual(self.reviewed(state, result)[tech]["level"], 7)

    def test_operational_source_without_identity_or_with_wrong_version_is_excluded(self):
        for metadata in ({"identified": False}, {"target_version": "v2"}):
            with self.subTest(metadata=metadata):
                state = make_state()
                ids = {tech: add_operational_web_evidence(state, tech, **metadata)
                       for tech in TECHNOLOGIES}

                def draft(tech, payload):
                    self.assertNotIn(ids[tech], json.dumps(payload))
                    return met_through(tech, 6) + [{
                        "level": 7, "status": "met", "reason": "Adjacent source asserts actual operation.",
                        "evidence_ids": [ids[tech]]}]

                result = self.generate(state, DraftResponder(draft))
                for tech in TECHNOLOGIES:
                    self.assertEqual(self.check(result, tech, 7)["status"], "unknown")
                    self.assertEqual(self.check(result, tech, 7)["evidence_ids"], [])
                    self.assertEqual(self.reviewed(state, result)[tech]["level"], 6)

    def test_omitted_stages_are_explicit_unknown_and_do_not_bridge_a_gap(self):
        state = make_state()
        result = self.generate(state, DraftResponder(lambda tech, payload: [
            met_through(tech, 1)[0], met_through(tech, 3)[2]]))
        for tech in TECHNOLOGIES:
            checks = result["results"][tech]["trl_checks"]
            self.assertEqual({int(level) for level in checks}, set(range(1, 10)))
            for level in (2, 4, 5, 6, 7, 8, 9):
                check = self.check(result, tech, level)
                self.assertEqual(check["status"], "unknown")
                self.assertEqual(check["evidence_ids"], [])
                self.assertTrue(check["reason"].strip())
            self.assertEqual(self.reviewed(state, result)[tech]["level"], 1)

    def test_explicit_not_met_and_missing_draft_remain_distinct(self):
        state = make_state()
        reason = "The paper explicitly states that the basic mechanism principle was not established."
        for tech in TECHNOLOGIES:
            state["evidence"][f"fixture-{tech}-stage-1"]["excerpt"] = reason
        result = self.generate(state, DraftResponder(lambda tech, payload: [
            {"level": 1, "status": "not_met", "reason": reason,
             "evidence_ids": [f"fixture-{tech}-stage-1"]}]))
        for tech in TECHNOLOGIES:
            self.assertEqual(self.check(result, tech, 1)["status"], "not_met")
            self.assertEqual(self.check(result, tech, 2)["status"], "unknown")
            self.assertIsNone(self.reviewed(state, result)[tech]["level"])

    def test_empty_draft_preserves_mechanism_and_validation_scope(self):
        state = make_state()
        original = deepcopy(state)
        result = self.generate(state, DraftResponder(lambda tech, payload: []))
        self.assertEqual(state, original)
        for tech in TECHNOLOGIES:
            before = {item["criterion_id"]: item for item in
                      original["assessments"]["technical"]["results"][tech]["items"]}
            after = {item["criterion_id"]: item for item in result["results"][tech]["items"]}
            for criterion in ("mechanism", "validation_scope"):
                self.assertEqual(after[criterion], before[criterion])
            self.assertEqual(after["maturity"]["judgment"], "unknown")
            self.assertEqual(after["maturity"]["basis"], "unknown")
            for level in range(1, 10):
                self.assertEqual(self.check(result, tech, level)["status"], "unknown")
            self.assertIsNone(self.reviewed(state, result)[tech]["level"])


if __name__ == "__main__":
    unittest.main()
