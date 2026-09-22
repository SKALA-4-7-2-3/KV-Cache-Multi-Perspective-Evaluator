"""report-input-v1의 단일 상태 판정. 형식 검사와 의미 검수를 구별한다."""

from datetime import datetime, timezone
from .rubric import CRITERIA, ROLES, TECHNOLOGIES, VERSION as RUBRIC_VERSION, criteria_for

VERSION = "report-input-v1"
SECTIONS = (
    "보고서 컨텍스트", "기술 선정 정보", "핵심 평가 요약 재료", "관점별 평가",
    "TRL 판정 결과", "관점 간 종합", "미확인 사항 및 한계", "도메인 요구조건",
    "근거 인덱스", "REFERENCE CANDIDATES", "출력 완결성 및 보고서 전달 규칙", "SELF VALIDATION",
)
REQUIREMENTS = {
    "context_tokens": "목표 문맥 길이", "concurrency": "예상 동시 사용자 또는 동시 요청 수",
    "ttft": "TTFT 목표", "tpot": "TPOT 목표", "quality": "허용 가능한 품질 손실",
    "gpu_memory": "GPU 메모리 제약", "energy": "에너지 제약", "cost": "비용 제약",
    "prefix_cache_hit_rate": "prefix cache 재사용률",
    "gpu_model": "배포 대상 GPU", "input_output_token_ratio": "입력 토큰 대비 출력 토큰 비율",
}


def is_missing(value):
    return value is None or (isinstance(value, str) and value.strip().lower() in
                             ("", "unknown", "tbd", "unspecified", "미확인"))


def domain_requirement(config, key):
    value = (config.get("domain_requirements") or {}).get(key)
    return "TBD" if value is None or value == "" else value


def evidence_independence(value):
    # 기존 공급자/제3자 표기는 호환한다. unknown을 author로 바꾸지 않는다.
    return {"vendor": "author", "third_party": "independent"}.get(value, value or "unknown")


def evidence_method(value):
    return value if value in {"gpu_experiment", "hardware_measurement", "emulation", "simulation", "analysis", "statement"} else "unknown"


def config_of(state):
    config = state.get("config", {})
    return config if isinstance(config, dict) else {}


def report_decision(state, result, *, require_synthesis=True):
    """내부 completed/repair와 외부 complete/blocked를 혼용하지 않는다."""
    rev, syn = result["review"], result["synthesis"]
    config = config_of(state)
    blocked, warnings = [], list(rev["gaps"])
    normalized = config.get("normalized_domain")
    if not isinstance(normalized, dict) or not all(isinstance(normalized.get(k), str) and normalized[k].strip()
                                                  for k in ("id", "name")):
        blocked.append("정규화된 도메인 id/name이 누락되었다.")
    if not config.get("raw_domain_input"):
        warnings.append("사용자 원문 도메인 입력 미제공. 정규화 문장으로 대체하지 않았다.")
    if rev["status"] == "failed":
        blocked.append("입력·실행 오류로 유효한 종합 결과를 만들 수 없다.")
    if rev["next"] == "repair":
        warnings.append("재평가 대기 중이다. 최종 보고서는 보완 후 최신 MD를 사용한다.")
    assessments = state.get("assessments", {})
    assessments = assessments if isinstance(assessments, dict) else {}
    for role in ROLES:
        if role not in assessments:
            blocked.append(f"관점 전체 누락: {role}")
    for tech in TECHNOLOGIES:
        if not any(isinstance(r, dict) and tech in r.get("results", {}) for r in assessments.values()):
            blocked.append(f"기술 전체 누락: {tech}")
    if any(c["code"] == "role_schema" for c in rev["checks"]):
        blocked.append("앞 Agent 출력 형식을 읽을 수 없다.")
    evidence = state.get("evidence", {}) or {}
    rows = syn["comparison_matrix"]
    cells = [r[t] for r in rows for t in TECHNOLOGIES]
    items = [i for cell in cells for i in cell["items"]]
    for row in rows:
        if all(row[t]["status"] == "failed" or all(i["judgment"] == "failed" for i in row[t]["items"]) for t in TECHNOLOGIES):
            blocked.append(f"한 관점의 평가 전체가 failed다: {row['perspective']}")
    for tech in TECHNOLOGIES:
        if all(r[tech]["status"] == "failed" or all(i["judgment"] == "failed" for i in r[tech]["items"]) for r in rows):
            blocked.append(f"한 기술의 평가 전체가 failed다: {tech}")
    unknown = sum(i["judgment"] == "unknown" for cell in cells if cell["status"] != "failed" for i in cell["items"])
    failed = sum(cell["status"] == "failed" or i["judgment"] == "failed" for cell in cells for i in cell["items"])
    criteria = criteria_for(config)
    structural_cells = sum({i["criterion_id"] for i in row[t]["items"]} == set(criteria[row["perspective"]]) for row in rows for t in TECHNOLOGIES)
    if unknown or failed:
        warnings.append("미확인 항목 또는 실패 결과가 있다.")
    if any(is_missing(domain_requirement(config, k)) for k in REQUIREMENTS):
        warnings.append("도메인 목표값 일부가 TBD다.")
    if any(t["next_unconfirmed"] and t["next_unconfirmed"]["status"] == "unknown" for t in syn["trl"].values()):
        warnings.append("TRL 상위 단계 근거가 미확인이다.")
    if not any(evidence_independence(evidence[e].get("independence")) == "independent" for e in syn["used_evidence_ids"]):
        warnings.append("독립 검증 근거가 확인되지 않았다.")
    if any(i.get("confidence", "unavailable") == "unavailable" for i in items):
        warnings.append("일부 근거 신뢰도는 상위 Agent가 평가하지 않았다.")
    integrated = syn.get("integrated", {})
    from .grounding import is_validated
    semantic_passed = is_validated(integrated)
    semantic_status = integrated.get("semantic_validation", {}).get("status", "not_run")
    if semantic_status == "passed" and not semantic_passed:
        semantic_status = "rejected"
    if require_synthesis and not semantic_passed:
        blocked.append("종합 의견의 자동 의미 검사가 미실행·실패·반려되었거나 검사 후 내용이 변경되었다.")
    if integrated.get("status") != "completed":
        warnings.append("새 종합 의견이 미완료다. 미실행/실패를 완료로 표시하지 않는다.")
    if integrated.get("unresolved_relations"):
        warnings.append("일치·상충·조건 비교·병행 중 일부 분석이 미완료다. 명시된 사유에서 자료 부족과 모델 누락을 구분한다.")
    if any(i.get("domain_relevance", "unclear") == "unclear" for i in items):
        warnings.append("일부 평가의 선택 도메인 관련성이 미확인이다.")
    status = "failed" if blocked else "partial" if warnings else "complete"
    gate = {"failed": "blocked", "partial": "allowed_with_gaps", "complete": "allowed"}[status]
    return {
        "schema_version": VERSION, "rubric_version": RUBRIC_VERSION,
        "reference_schema_version": "reference-v1", "content_language": "ko",
        "stakeholder_rubric": config.get("stakeholder_rubric", "actor_groups"),
        "run_id": str(config.get("run_id", "invalid")), "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_as_of": config.get("evaluation_as_of") or datetime.now().astimezone().date().isoformat(),
        "review_status": status, "report_generation": gate, "human_review_required": True,
        "human_review_scope": "final_submission_only",
        "semantic_validation_status": semantic_status,
        "sw_technology_id": "SW-01", "hw_technology_id": "HW-01",
        "valid_perspective_cells": f"{structural_cells}/8", "valid_criterion_blocks": f"{len(items)-failed}/46",
        "unknown_count": unknown, "failed_count": failed,
        "evidence_count": len(syn["used_evidence_ids"]), "reference_candidate_count": len(syn["references"]),
        "blocking_issues": list(dict.fromkeys(blocked)), "warnings": list(dict.fromkeys(warnings)),
    }


def route_to_report(state):
    """LangGraph 조건부 edge: 재평가 / 후단 보고서 / 진단 종료."""
    if state["review"]["next"] == "repair":
        return "repair"
    return "diagnostic" if report_decision(state, state)["report_generation"] == "blocked" else "report"
