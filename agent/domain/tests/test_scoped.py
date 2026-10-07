import json
from pathlib import Path

from kv_domain_agent.agent import DomainEvaluator


ROOT = Path(__file__).resolve().parents[1]


class ScopedModel:
    def __init__(self):
        self.payload = None

    def invoke(self, messages):
        self.payload = json.loads(messages[1][1])
        evidence_id = self.payload["allowed_evidence_ids_by_technology"]["SW-01"][0]
        return {"role": "domain", "round": 0, "status": "completed",
                "domain_name": self.payload["domain"]["name"],
                "assessments": [{"technology_id": "SW-01", "technology_name": "RDKV",
                    "status": "completed", "criteria": [{"criterion_id": "capacity",
                    "judgment": "conditional", "target_alignment": "partial",
                    "conclusion": "선택 셀", "rationale": "선택 근거", "conditions": [],
                    "evidence_ids": [evidence_id], "basis": "fact", "gaps": [], "need_more": []}],
                    "overall_summary": "선택 셀만 평가", "key_tradeoffs": []}],
                "cross_technology_tradeoffs": [], "unresolved_questions": [],
                "disclaimer": "공개·공유 근거 기반의 조건부 평가이며 실제 배포 검증이 아님"}


def test_scoped_domain_payload_and_output_contain_only_requested_cell():
    state = json.loads((ROOT / "examples/input_state.json").read_text())
    state["worker_scope"] = {"active_cells": [
        {"technology_id": "SW-01", "criterion_id": "capacity"}],
        "feedback": ["capacity 조건을 다시 확인"],
        "prior_cells": {"SW-01/capacity": {"judgment": "unknown"}}}
    model = ScopedModel()
    output = DomainEvaluator(model, allow_demo=True).evaluate(state)
    assert [(row.technology_id, [item.criterion_id.value for item in row.criteria])
            for row in output.assessments] == [("SW-01", ["capacity"])]
    assert [row["technology_id"] for row in model.payload["technical"]["technologies"]] == ["SW-01"]
    assert [row["criterion_id"] for row in model.payload["domain"]["requirements"]] == ["capacity"]
    assert model.payload["feedback"] == ["capacity 조건을 다시 확인"]
    assert model.payload["previous_accepted_cells"] == {
        "SW-01/capacity": {"judgment": "unknown"}}
