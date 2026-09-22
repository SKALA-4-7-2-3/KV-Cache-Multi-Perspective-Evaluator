"""관점 종합 → 의미 검사 → 필요 시 한 번 수정. 총 API 시도 최대 4회."""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from .contract import config_of, report_decision
from .schema import StrictModel, Text, Tech
from .grounding import (PROMPT_PATH as AUDIT_PROMPT, VERSION as AUDIT_VERSION,
                        GroundingError, audit_payload, call_grounding, fingerprint,
                        is_validated, validate_audit, conservative_issues)

PROMPT_PATH = Path(__file__).with_name("SYNTHESIS-PROMPT.md")
DEFAULT_MODEL = "gpt-4.1-mini"
RELATION_KINDS = ("agreement", "tension", "conditional", "joint")


def relation_source_gap(field, ids):
    """Check code-assigned reference coverage before asking a model for prose."""
    roles = {aid.split("/")[0] for aid in ids}
    techs = {aid.split("/")[1] for aid in ids}
    expected = {"SW-01"} if field.startswith("rdkv_") else {"HW-01"} if field.startswith("photonic_cxl_") else {"SW-01", "HW-01"}
    missing = []
    if len(ids) < 2:
        missing.append(f"연결 가능한 유효 평가가 {len(ids)}개로 최소 2개에 미달")
    if techs != expected:
        missing.append("유효 평가가 연결되지 않은 기술: " + ", ".join(sorted(expected - techs)))
    if field.endswith("opinion") and not {"market", "stakeholders", "domain"}.issubset(roles):
        missing.append("유효 평가가 연결되지 않은 관점: " + ", ".join(sorted({"market", "stakeholders", "domain"} - roles)))
    if (field == "agreement" or field.endswith("tension")) and len(roles) < 2:
        missing.append("서로 다른 두 관점의 유효 평가 연결이 필요함")
    return ("이번 입력의 관계 분석 보류: " + "; ".join(missing)
            + ". 관련 자료가 현실에 존재하지 않는다는 판정이 아니라 이번 입력의 연결 범위에 대한 설명입니다.") if missing else None


class SynthesisValidationError(ValueError):
    """코드가 정의한 비밀값 없는 진단만 보고서로 전달한다."""


class ModelOpinion(StrictModel):
    conclusion: Text
    explanation: Text
    conditions: list[Text] = Field(min_length=1)
    risks: list[Text]
    unknowns: list[Text]
    confidence: Literal["high", "medium", "low"]
    basis: Literal["inference"]
    recommendation: Literal[False]
    absolute_ranking: Literal[False]
    rd_kv_conditions: list[Text]
    photonic_cxl_conditions: list[Text]
    undecidable_conditions: list[Text]


class Opinion(ModelOpinion):
    kind: Literal["opinion", "agreement", "tension", "conditional", "joint"]
    technology_ids: list[Tech] = Field(min_length=1, max_length=2)
    source_assessment_ids: list[Text] = Field(min_length=2)
    evidence_ids: list[Text] = Field(min_length=1)


class RelationGap(StrictModel):
    kind: Literal["opinion", "agreement", "tension", "conditional", "joint"]
    technology_ids: list[Tech] = Field(min_length=1, max_length=2)
    reason: Text


class IntegratedOpinions(StrictModel):
    opinions: list[Opinion] = Field(max_length=8)
    unresolved_relations: list[RelationGap]
    limitations: list[Text]


class DeferredOpinion(StrictModel):
    reason: Text


class ModelSynthesis(StrictModel):
    """모델에는 전용 칸을 주고, 후단에는 기존 flat opinions 계약을 유지한다."""
    rdkv_opinion: ModelOpinion | DeferredOpinion
    photonic_cxl_opinion: ModelOpinion | DeferredOpinion
    agreement: ModelOpinion | DeferredOpinion
    rdkv_tension: ModelOpinion | DeferredOpinion
    photonic_cxl_tension: ModelOpinion | DeferredOpinion
    conditional: ModelOpinion | DeferredOpinion
    joint: ModelOpinion | DeferredOpinion
    limitations: list[Text]

    def flatten(self, payload):
        available = {a["assessment_id"]: a for a in payload["assessments"]}
        linked, pending = [], []
        for field, kind in (("rdkv_opinion", "opinion"), ("photonic_cxl_opinion", "opinion"),
                            ("agreement", "agreement"), ("rdkv_tension", "tension"),
                            ("photonic_cxl_tension", "tension"), ("conditional", "conditional"), ("joint", "joint")):
            opinion = getattr(self, field)
            ids = payload["relation_source_candidates"][field]
            techs = ["SW-01"] if field.startswith("rdkv_") else ["HW-01"] if field.startswith("photonic_cxl_") else ["SW-01", "HW-01"]
            source_gap = relation_source_gap(field, ids)
            if source_gap:
                pending.append({"kind": kind, "technology_ids": techs, "reason": source_gap})
                continue
            if isinstance(opinion, DeferredOpinion):
                pending.append({"kind": kind, "technology_ids": techs, "reason": opinion.reason})
                continue
            if not set(ids).issubset(available):
                raise SynthesisValidationError("종합 의견에 유효하지 않은 평가 ID가 있습니다.")
            # 고정 업무별 평가 묶음과 근거를 그대로 계승한다. 모델은 이 범위에서 문장만 작성한다.
            evidence_ids = sorted({eid for aid in ids for eid in available[aid]["evidence_ids"]})
            linked.append({**opinion.model_dump(mode="json"), "kind": kind, "technology_ids": techs,
                           "source_assessment_ids": ids, "evidence_ids": evidence_ids})
        return {"opinions": linked,
                "unresolved_relations": pending,
                "limitations": self.limitations}


def synthesis_payload(state, result):
    syn = result["synthesis"]
    assessments = []
    for row in syn["comparison_matrix"]:
        for tech in ("SW-01", "HW-01"):
            for item in row[tech]["items"]:
                assessments.append({"assessment_id": f"{row['perspective']}/{tech}/{item['criterion_id']}", **item,
                                    "usable": row[tech]["status"] != "failed" and item["judgment"] not in ("unknown", "failed") and bool(item["evidence_ids"])})
    cfg = config_of(state)
    stakeholder_item = "burdens" if cfg.get("stakeholder_rubric") == "operating_organization" else "developers"
    # 고정 업무별 검색 대상처럼, 모델에도 관련 평가 ID를 안내한다. 새로운 근거는 추가하지 않는다.
    requested = {
        "rdkv_opinion": ["market/SW-01/cost", f"stakeholders/SW-01/{stakeholder_item}", "domain/SW-01/domain_fit", "domain/SW-01/quality", "domain/SW-01/deployment"],
        "photonic_cxl_opinion": ["market/HW-01/cost", f"stakeholders/HW-01/{stakeholder_item}", "domain/HW-01/domain_fit", "domain/HW-01/hardware_dependency", "domain/HW-01/deployment"],
        "agreement": [f"{role}/{tech}/customer_value" for tech in ("SW-01", "HW-01") for role in ("market", "domain")],
        "rdkv_tension": ["technical/SW-01/validation_scope", "market/SW-01/cost", "domain/SW-01/quality", "domain/SW-01/deployment"],
        "photonic_cxl_tension": ["technical/HW-01/validation_scope", "market/HW-01/cost", "domain/HW-01/hardware_dependency", "domain/HW-01/deployment"],
        "conditional": [f"{role}/{tech}/{cid}" for tech in ("SW-01", "HW-01") for role, cid in (("market", "cost"), ("domain", "domain_fit"))],
        "joint": [f"{role}/{tech}/{cid}" for tech in ("SW-01", "HW-01") for role, cid in (("technical", "mechanism"), ("domain", "deployment"))],
    }
    usable_ids = {a["assessment_id"] for a in assessments if a["usable"]}
    candidates = {name: [aid for aid in ids if aid in usable_ids] for name, ids in requested.items()}
    return {"domain": cfg.get("normalized_domain"), "requirements": cfg.get("domain_requirements", {}),
            "relation_source_candidates": candidates,
            "unavailable_relation_fields": {name: reason for name, ids in candidates.items()
                                            if (reason := relation_source_gap(name, ids))},
            "assessments": [a for a in assessments if a["usable"]],
            "unconfirmed_assessments": [a for a in assessments if not a["usable"]], "trl": syn["trl"],
            "metric_comparisons": syn["metric_comparisons"],
            "evidence": {eid: state["evidence"][eid] for eid in syn["used_evidence_ids"]}}


def validate_opinions(value, payload):
    parsed = IntegratedOpinions.model_validate(value)
    available = {a["assessment_id"]: a for a in payload["assessments"]
                 if a["judgment"] not in ("unknown", "failed") and a["evidence_ids"]}
    for opinion in parsed.opinions:
        ids = set(opinion.source_assessment_ids)
        if not ids.issubset(available):
            raise SynthesisValidationError("종합 의견에 유효하지 않은 평가 ID가 있습니다.")
        if opinion.kind in ("opinion", "agreement", "tension") and len({i.split("/")[0] for i in ids}) < 2:
            raise SynthesisValidationError(f"{opinion.kind}: 관점 간 종합은 최소 두 관점을 연결해야 합니다.")
        source_techs = {i.split("/")[1] for i in ids}
        if set(opinion.technology_ids) != source_techs:
            raise SynthesisValidationError("종합 의견의 기술과 연결 평가가 다릅니다.")
        if (opinion.rd_kv_conditions and "SW-01" not in source_techs) or (opinion.photonic_cxl_conditions and "HW-01" not in source_techs):
            raise SynthesisValidationError("조건부 적합성에 다른 기술의 근거가 빠져 있습니다.")
        evidence = set(opinion.evidence_ids)
        pool = {e for aid in ids for e in available[aid]["evidence_ids"]}
        if not evidence.issubset(pool) or not all(evidence.intersection(available[i]["evidence_ids"]) for i in ids):
            raise SynthesisValidationError("새 의견의 근거가 연결한 상위 평가에서 전달되지 않았습니다.")
        if opinion.conclusion in {available[i]["conclusion"] for i in ids}:
            raise SynthesisValidationError("원문 평가 복사는 새 종합 의견이 아닙니다.")
        if opinion.kind == "opinion":
            for tech in opinion.technology_ids:
                roles = {i.split("/")[0] for i in ids if i.split("/")[1] == tech}
                if not {"market", "stakeholders", "domain"}.issubset(roles):
                    raise SynthesisValidationError("기술별 종합 의견에는 시장·이해관계자·도메인이 모두 필요합니다.")
    # 빈 유형을 성공으로 통과시키지 않는다. 근거가 부족하면 기술별 사유를 명시한다.
    for kind in ("opinion", *RELATION_KINDS):
        covered = {t for o in parsed.opinions if o.kind == kind for t in o.technology_ids}
        pending = [t for gap in parsed.unresolved_relations if gap.kind == kind for t in gap.technology_ids]
        if len(pending) != len(set(pending)) or covered.intersection(pending):
            raise SynthesisValidationError("동일 관계를 판정 완료와 미판정으로 동시에 표시할 수 없습니다.")
        missing = {"SW-01", "HW-01"} - covered - set(pending)
        if missing:
            # 유효한 나머지 의견을 버리지 않되, 모델 누락을 '근거 부족'이나 완료로 위장하지 않는다.
            parsed.unresolved_relations.append(RelationGap(
                kind=kind, technology_ids=sorted(missing),
                reason="모델이 해당 기술의 관계 분석을 제출하지 않음. 분석 누락이며 근거 부재 판정이 아님; 재검토 필요.",
            ))
    for opinion in parsed.opinions:
        if opinion.kind in ("conditional", "joint") and set(opinion.technology_ids) != {"SW-01", "HW-01"}:
            raise SynthesisValidationError("조건 비교와 병행 가설에는 두 기술의 근거가 필요합니다.")
        if opinion.kind != "joint" and re.search(r"병행|하이브리드|hybrid", opinion.conclusion, re.I):
            raise SynthesisValidationError("병행 결론은 joint에만 기록해 다른 섹션과 중복·모순을 방지합니다.")
    return parsed.model_dump(mode="json")


def call_openai(payload, *, model=DEFAULT_MODEL):
    from openai import OpenAI
    # .env 로딩은 CLI/호출자 책임. 이 함수는 비밀값·응답 원문을 로그에 남기지 않는다.
    with OpenAI(timeout=120, max_retries=0) as client:
        response = client.responses.parse(
            model=model, temperature=0, store=False, max_output_tokens=8000,
            instructions=PROMPT_PATH.read_text(encoding="utf-8"),
            input=json.dumps(payload, ensure_ascii=False), text_format=ModelSynthesis,
        )
    if response.status != "completed" or response.output_parsed is None:
        raise SynthesisValidationError("모델 응답이 거절되었거나 완성되지 않았습니다.")
    return response.output_parsed.flatten(payload)


def defer_rejected_opinions(candidate, checks, payload):
    """Withhold individual generated statements; never turn a rejection into support."""
    rejected = {c["item_id"] for c in checks if c["verdict"] != "supported"}
    if not rejected or "limitations" in rejected:
        return None
    retained, pending = [], list(candidate["unresolved_relations"])
    for index, opinion in enumerate(candidate["opinions"], 1):
        item_id = f"opinion_{index}"
        if item_id not in rejected:
            retained.append(opinion)
            continue
        reasons = [c["reason"] for c in checks if c["item_id"] == item_id and c["verdict"] != "supported"]
        pending.append({"kind": opinion["kind"], "technology_ids": opinion["technology_ids"],
                        "reason": "생성된 종합 문장이 자동 검토에서 표현 또는 근거 연결을 확인받지 못하여 이번 초안에서는 보류함. "
                                  "원자료 부재 판정이 아니라 모델 생성 결과의 검토 실패이며 후속 품질 검토가 필요함. " + " / ".join(reasons)})
    if not retained or len(retained) == len(candidate["opinions"]):
        return None
    return validate_opinions({**candidate, "opinions": retained, "unresolved_relations": pending}, payload)


def synthesize(state, result, generator=None, auditor=None):
    """주입 테스트는 generator와 auditor 모두 필요. 미검사 출력을 통과시키지 않는다."""
    if result["review"]["next"] == "repair" or report_decision(state, result, require_synthesis=False)["report_generation"] == "blocked":
        return {"status": "skipped", "opinions": [], "limitations": ["입력 차단 또는 재평가 대기"], "api_calls": 0}
    payload = synthesis_payload(state, result)
    model = config_of(state).get("synthesis_model", DEFAULT_MODEL)
    prompt_hash = hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()
    audit_hash = hashlib.sha256(AUDIT_PROMPT.read_bytes()).hexdigest()
    mode = "api" if generator is None else "injected-test"
    digest = fingerprint([payload, model, prompt_hash, audit_hash, AUDIT_VERSION, mode])
    cached = state.get("synthesis", {}).get("integrated", {})
    if cached.get("input_hash") == digest and is_validated(cached):
        try:
            validated = validate_opinions({k: cached[k] for k in ("opinions", "unresolved_relations", "limitations")}, payload)
            scoped = audit_payload(validated, payload)
            if conservative_issues(scoped):
                raise GroundingError("현재 보수적 단정 검사에서 기존 출력이 반려됨.")
            validate_audit({"checks": cached["semantic_validation"]["checks"]}, scoped)
            return {**cached, **validated, "cache_reused": True, "api_calls": 0,
                    "generation_calls": 0, "validation_calls": 0, "repair_attempts": 0}
        except ValueError:
            pass  # 불일치 캐시는 폐기하고 새로 생성·검사한다.
    metadata = {"model": model if generator is None else "injected-test-generator", "prompt_sha256": prompt_hash,
                "audit_prompt_sha256": audit_hash, "input_hash": digest, "api_calls": 0, "cache_reused": False,
                "generation_calls": 0, "validation_calls": 0, "repair_attempts": 0}
    attempts, feedback = [], None
    fast_report = config_of(state).get("fast_report") is True
    try:
        if (generator is None) != (auditor is None):
            raise SynthesisValidationError("테스트 주입에는 생성기와 의미 검사기를 모두 제공해야 합니다.")
        for round_no in range(1 if fast_report else 2):
            metadata["repair_attempts"] = round_no
            request = {**payload, "repair": feedback} if feedback else payload
            metadata["generation_calls"] += 1
            metadata["api_calls"] += int(generator is None)
            raw = call_openai(request, model=model) if generator is None else generator(request)
            try:
                validated = validate_opinions(raw, payload)
            except ValueError as exc:
                message = str(exc) if isinstance(exc, SynthesisValidationError) else "출력 스키마가 계약과 다릅니다."
                diagnostics = ([{"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]}
                                for e in exc.errors(include_input=False, include_url=False)]
                               if isinstance(exc, ValidationError) else [])
                attempts.append({"round": round_no, "status": "structural_rejected", "reason": message,
                                 "schema_errors": diagnostics, "candidate": raw})
                feedback = {"issues": [message], "schema_errors": diagnostics}
                continue
            scoped = audit_payload(validated, payload)
            rule_issues = conservative_issues(scoped)
            withholding_events = []
            if rule_issues:
                attempts.append({"round": round_no, "status": "rule_rejected", "checks": rule_issues,
                                 "candidate": validated})
                feedback = {"previous_candidate": validated, "issues": rule_issues}
                retained = defer_rejected_opinions(validated, rule_issues, payload) if fast_report else None
                if retained is None:
                    continue
                withholding_events.append({"stage": "rule_check", "rejected_checks": rule_issues})
                validated = retained
                scoped = audit_payload(validated, payload)
                scoped["processing_diagnostics"] = withholding_events
            metadata["validation_calls"] += 1
            metadata["api_calls"] += int(auditor is None)
            raw_audit = call_grounding(scoped, model=model) if auditor is None else auditor(scoped)
            audit = validate_audit(raw_audit, scoped)
            attempts.append({"round": round_no, **audit})
            if audit["status"] != "passed" and fast_report:
                rejected_checks = [c for c in audit["checks"] if c["verdict"] != "supported"]
                retained = defer_rejected_opinions(validated, rejected_checks, payload)
                if retained is not None:
                    withholding_events.append({"stage": "semantic_check", "rejected_checks": rejected_checks})
                    attempts.append({"round": round_no, "status": "partial_retention", "candidate": validated,
                                     "checks": rejected_checks})
                    validated = retained
                    scoped = audit_payload(validated, payload)
                    scoped["processing_diagnostics"] = withholding_events
                    metadata["validation_calls"] += 1
                    metadata["api_calls"] += int(auditor is None)
                    raw_audit = call_grounding(scoped, model=model) if auditor is None else auditor(scoped)
                    audit = validate_audit(raw_audit, scoped)
                    attempts.append({"round": round_no, "stage": "retained_candidate_audit", **audit})
            if audit["status"] == "passed":
                return {"status": "partial" if validated["unresolved_relations"] else "completed", **metadata, **validated,
                        "semantic_validation": {**audit, "version": AUDIT_VERSION,
                                                "seal": fingerprint([validated, audit["checks"]]), "attempts": attempts}}
            feedback = {"previous_candidate": validated,
                        "issues": [c for c in audit["checks"] if c["verdict"] != "supported"]}
        return {"status": "failed", **metadata, "opinions": [], "unresolved_relations": [],
                "limitations": ["제한된 자동 검토 안에서 입력과의 정합성을 확인하지 못해 종합 의견 전달을 차단했습니다."],
                "semantic_validation": {"status": "rejected", "version": AUDIT_VERSION, "attempts": attempts}}
    except Exception as exc:
        # API/검사기 장애는 사실 판단과 구분한다. 검사를 생략한 채 통과시키지 않는다.
        return {"status": "failed", **metadata, "opinions": [],
                "semantic_validation": {"status": "failed", "version": AUDIT_VERSION, "attempts": attempts},
                "limitations": [str(exc) if isinstance(exc, (SynthesisValidationError, GroundingError)) else
                                f"종합 생성/자동 검사 실패: {type(exc).__name__}. 원문 오류 내용은 비공개."]}
