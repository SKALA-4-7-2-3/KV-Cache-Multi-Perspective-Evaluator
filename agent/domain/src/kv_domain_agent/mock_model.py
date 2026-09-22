"""Deterministic offline model used for wiring checks, not substantive evaluation."""

from __future__ import annotations

import json
from typing import Any

from .models import DomainCriterion


class DeterministicMockModel:
    """Return conservative results based only on evidence criterion tags."""

    def invoke(self, messages: Any) -> dict[str, Any]:
        payload = json.loads(messages[-1][1])
        evidence = payload["evidence"]
        technologies = payload["technical"]["technologies"]
        requirements = {
            item["criterion_id"]: item for item in payload["domain"]["requirements"]
        }

        assessments = []
        for technology in technologies:
            allowed_for_tech = set(technology["evidence_ids"])
            criteria = []
            for criterion in DomainCriterion:
                matching_ids = [
                    evidence_id
                    for evidence_id, item in evidence.items()
                    if evidence_id in allowed_for_tech
                    and criterion.value in item.get("criterion_ids", [])
                ]
                if matching_ids:
                    judgment = "conditional"
                    alignment = "partial"
                    conclusion = "공유 근거는 적용 가능성을 시사하지만 실배포 판단에는 추가 검증이 필요합니다."
                    rationale = "오프라인 모의 실행은 근거 태그 연결과 스키마만 검증합니다."
                    basis = "fact"
                    gaps = ["실제 요구조건과 동일한 환경의 재현 측정 필요"]
                else:
                    judgment = "unknown"
                    alignment = "unknown"
                    conclusion = "공유 근거만으로 판단할 수 없습니다."
                    rationale = "이 기준에 연결된 근거가 없습니다."
                    basis = "none"
                    gaps = ["기준별 근거 없음"]
                criteria.append(
                    {
                        "criterion_id": criterion.value,
                        "judgment": judgment,
                        "target_alignment": alignment,
                        "conclusion": conclusion,
                        "rationale": rationale,
                        "conditions": [requirements[criterion.value]["target"]],
                        "evidence_ids": matching_ids,
                        "basis": basis,
                        "gaps": gaps,
                        "need_more": [f"{criterion.value}의 동일 조건 측정 자료"],
                    }
                )
            assessments.append(
                {
                    "technology_id": technology["technology_id"],
                    "technology_name": technology["name"],
                    "status": "completed" if any(x["evidence_ids"] for x in criteria) else "unknown",
                    "criteria": criteria,
                    "overall_summary": "모의 실행 결과이며 기술 결론으로 사용하면 안 됩니다.",
                    "key_tradeoffs": ["근거 범위와 목표 환경의 일치 여부"],
                }
            )
        return {
            "role": "domain",
            "round": payload["round"],
            "status": "completed",
            "domain_name": payload["domain"]["name"],
            "assessments": assessments,
            "cross_technology_tradeoffs": ["모의 실행에서는 실제 기술 우열을 판단하지 않습니다."],
            "unresolved_questions": ["실제 기술 조사 결과로 다시 실행해야 합니다."],
            "disclaimer": "공개·공유 근거 기반의 조건부 평가이며 실제 배포 검증이 아닙니다.",
        }

