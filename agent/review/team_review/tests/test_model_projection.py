"""Model-only size reduction; fixtures and API stubs do not test model accuracy."""
import hashlib
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from team_review import review_node
from team_review.demo import make_input
from team_review.grounding import audit_payload, validate_audit
from team_review import synthesize as module
from team_review.tests.test_synthesize import fake_generator, fake_auditor


class ModelProjectionTests(unittest.TestCase):
    def payload(self):
        state = make_input()
        state["config"].update(attribution_first=True, usable_source_reports=[{
            "source_id": "market:source-1", "evidence_id": "source-1",
            "reference_id": "web-1", "citation_key": "web1", "role": "market",
            "title": "Long original", "url": "https://example.invalid/source",
            "technology_ids": ["HW-01"], "excerpt": "원문 전체\n" * 250_000,
        }])
        return module.synthesis_payload(state, review_node(state))

    def test_large_source_is_manifest_only_and_canonical_payload_is_unchanged(self):
        payload = self.payload()
        before = deepcopy(payload)
        projected = module.model_payload(payload)
        self.assertEqual(payload, before)
        self.assertNotIn("usable_source_reports", projected)
        source = payload["usable_source_reports"][0]
        manifest = projected["source_manifest"][0]
        self.assertEqual(manifest["source_id"], source["source_id"])
        self.assertEqual(manifest["technology_ids"], ["HW-01"])
        self.assertEqual(manifest["excerpt_sha256"], hashlib.sha256(source["excerpt"].encode()).hexdigest())
        self.assertEqual(manifest["excerpt_chars"], len(source["excerpt"]))
        self.assertNotIn("excerpt", manifest)
        self.assertIn("사실 근거가 아니다", projected["model_input_contract"])
        self.assertLess(len(json.dumps(projected, ensure_ascii=False)), 450_000)

    def test_evidence_conditions_and_unknowns_are_not_truncated_or_reclassified(self):
        payload = self.payload()
        first = next(iter(payload["evidence"].values()))
        first["excerpt"] = "사용 근거의 마지막 조건\n" * 10_000
        payload["assessments"][0].update(judgment="unknown", conditions=["검증 선행"],
            counter_evidence=["반대 근거"], gaps=["자료 공백"])
        projected = module.model_payload(payload)
        for key in ("evidence", "assessments", "unconfirmed_assessments", "trl",
                    "relation_source_candidates", "requirements", "metric_comparisons"):
            self.assertEqual(projected[key], payload[key])

    def test_changed_source_identity_changes_manifest_without_reusing_old_identity(self):
        payload = self.payload()
        changed = deepcopy(payload)
        changed["usable_source_reports"][0].update(url="https://example.invalid/changed",
            technology_ids=["SW-01"], excerpt="다른 실제 원문")
        old = module.model_payload(payload)["source_manifest"][0]
        new = module.model_payload(changed)["source_manifest"][0]
        self.assertNotEqual(old["url"], new["url"])
        self.assertNotEqual(old["technology_ids"], new["technology_ids"])
        self.assertNotEqual(old["excerpt_sha256"], new["excerpt_sha256"])

    def test_semantic_registry_preserves_every_scoped_record_and_missing_links(self):
        payload = self.payload()
        candidate = fake_generator(payload)
        candidate["opinions"][0]["evidence_ids"].append("missing-evidence")
        candidate["opinions"][0]["source_assessment_ids"].append("market/HW-01/missing")
        scoped = audit_payload(candidate, payload)
        before = deepcopy(scoped)
        projected = module.model_payload(scoped)
        self.assertEqual(scoped, before)
        for original, item in zip(scoped["items"], projected["items"], strict=True):
            self.assertEqual(item["content"], original["content"])
            self.assertEqual([projected["assessment_registry"][aid] for aid in item["assessment_ids"]],
                             original["assessments"])
            self.assertEqual({eid: projected["evidence_registry"][eid] for eid in item["evidence_ids"]},
                             original["evidence"])
        self.assertEqual(projected["items"][0]["missing_evidence_ids"], ["missing-evidence"])
        self.assertEqual(projected["items"][0]["missing_assessment_ids"], ["market/HW-01/missing"])
        bad_audit = fake_auditor(scoped)
        bad_audit["checks"][0]["evidence_ids"] = ["missing-evidence"]
        with self.assertRaises(ValueError):
            validate_audit(bad_audit, scoped)

    def test_inconsistent_shared_records_fail_instead_of_silently_replacing_evidence(self):
        payload = self.payload()
        scoped = audit_payload(fake_generator(payload), payload)
        scoped["items"][0] = deepcopy(scoped["items"][0])
        next(iter(scoped["items"][0]["evidence"].values()))["excerpt"] = "conflicting original"
        with self.assertRaises(ValueError):
            module.model_payload(scoped)

    def test_generation_transmits_projection_but_flattens_against_full_original(self):
        payload = self.payload()
        captured, flattened = [], []
        def parse(**kwargs):
            captured.append(json.loads(kwargs["input"]))
            return SimpleNamespace(status="completed", output_parsed=SimpleNamespace(
                flatten=lambda original: (flattened.append(original) or {"opinions": []})))
        client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
        # Special methods are looked up on the type, not the instance.
        class ClientContext:
            def __enter__(self):
                return client
            def __exit__(self, *_):
                return None
        with patch("pipeline.governance.openai_client", return_value=ClientContext()):
            module.call_openai(payload)
        self.assertTrue("usable_source_reports" not in captured[0])
        self.assertIs(flattened[0], payload)
        self.assertIn("excerpt", flattened[0]["usable_source_reports"][0])

    def test_semantic_transport_uses_projection_and_keeps_original_validation_input(self):
        payload = self.payload()
        scoped = audit_payload(fake_generator(payload), payload)
        with patch("team_review.synthesize._call_grounding", return_value={"checks": []}) as transport:
            module.call_grounding(scoped, model="test-model")
        transmitted = transport.call_args.args[0]
        self.assertNotIn("usable_source_reports", transmitted)
        self.assertIn("evidence_registry", transmitted)
        self.assertIn("usable_source_reports", scoped)


if __name__ == "__main__":
    unittest.main()
