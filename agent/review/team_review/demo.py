"""합성 입력만 만드는 테스트 도구. 논문 실험 결과나 실측치를 나타내지 않는다."""

from copy import deepcopy
from hashlib import sha256

from .rubric import CRITERIA, DOMAIN, ROLES, TECHNOLOGIES, VERSION

SCENARIOS = ("normal", "no_evidence", "tool_failure", "bad_citation", "retry_limit", "fatal_error")


def make_input(scenario: str = "normal") -> dict:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    state = {
        "config": {"run_id": f"demo-{scenario}", "domain": DOMAIN, "demo": True, "rubric_version": VERSION,
                   "raw_domain_input": DOMAIN, "normalized_domain": {"id": "cloud-long-qa", "name": DOMAIN},
                   "evaluation_as_of": "2026-09-21"},
        "documents": {}, "evidence": {}, "assessments": {}, "errors": {},
        "review": {"round": 0, "dirty_roles": list(ROLES)},
    }
    for tech, name in TECHNOLOGIES.items():
        state["documents"][tech] = {
            "title": f"[DUMMY] {name} 구조 검사용 가상 문서", "url": f"https://example.invalid/{tech}",
            "version": "v1", "pages": 2, "sha256": sha256(f"dummy-{tech}".encode()).hexdigest(),
            "kind": "paper", "published_at": None, "retrieved_at": "2026-09-21T18:00:00+09:00",
        }
        eid = f"DUMMY-{tech}-p1"
        state["evidence"][eid] = {
            "id": eid, "doc_id": tech, "technology_ids": [tech],
            "excerpt": "[DUMMY] 입출력 검사용 합성 발췌. 실제 논문 근거가 아님.",
            "page": 1, "location": "가상 절", "method": "analysis",
            "verified_source": True, "synthetic": True, "collected_at": "2026-09-21T18:00:00+09:00",
        }
    for role in ROLES:
        result = {"round": 0, "status": "completed", "results": {}}
        for tech in TECHNOLOGIES:
            eid = f"DUMMY-{tech}-p1"
            items = [{
                "criterion_id": cid, "judgment": "conditional",
                "conclusion": f"[DUMMY] {tech}/{cid}의 조건부 판단 예시.",
                "conditions": ["가상 테스트 환경에서만 유효"], "evidence_ids": [eid],
                "basis": "inference", "gaps": [], "need_more": [], "metrics": [],
            } for cid in CRITERIA[role]]
            checks = {}
            if role == "technical":
                # TRL 1은 순수 테스트 값. 두 기술의 실제 성숙도를 판정한 것이 아니다.
                checks = {1: {"status": "met", "reason": "[DUMMY] 1단계 통과 사례", "evidence_ids": [eid]}}
                for n in range(2, 10):
                    checks[n] = {"status": "unknown", "reason": "[DUMMY] 상위 단계 미확인", "evidence_ids": []}
                items[1]["metrics"] = [{
                    "name": "decode_speedup" if tech == "SW-01" else "ttft_speedup",
                    "value": 2.0 if tech == "SW-01" else 3.0, "unit": "x", "evidence_ids": [eid],
                    "model": "DUMMY-MODEL", "hardware": "DUMMY-HARDWARE", "baseline": "DUMMY-BASELINE",
                    "context_tokens": 100, "concurrency": 1, "workload": "DUMMY-QA",
                    "method": "gpu_experiment" if tech == "SW-01" else "simulation",
                }]
            result["results"][tech] = {"status": "completed", "items": items, "trl_checks": checks}
        state["assessments"][role] = result

    if scenario == "no_evidence":
        state["evidence"] = {}
        for role in ROLES:
            for cell in state["assessments"][role]["results"].values():
                cell["status"] = "unknown"
                for item in cell["items"]:
                    item.update(judgment="unknown", evidence_ids=[], metrics=[],
                                conclusion="판단 보류", gaps=["검색 결과 없음"])
                for check in cell["trl_checks"].values():
                    check.update(status="unknown", evidence_ids=[], reason="원문 근거 미확인")
    if scenario == "tool_failure":
        state["assessments"]["market"] = {"round": 0, "status": "failed", "results": {}}
        state["errors"]["market-timeout"] = {"role": "market", "round": 0, "retryable": True, "fatal": False}
    if scenario in ("bad_citation", "retry_limit"):
        state["assessments"]["market"]["results"]["SW-01"]["items"][0]["evidence_ids"] = ["invented-id"]
    if scenario == "retry_limit":
        state["review"] = {"round": 1, "dirty_roles": ["market"]}
        state["assessments"]["market"]["round"] = 1
    if scenario == "fatal_error":
        state["errors"]["authentication"] = {"role": "technical", "round": 0, "retryable": False, "fatal": True}
    return deepcopy(state)
