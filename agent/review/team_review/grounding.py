"""생성 의견과 연결된 입력의 의미 대조. 검색 없이 별도 모델 호출로 검사한다."""
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from .schema import StrictModel, Text

PROMPT_PATH = Path(__file__).with_name("GROUNDING-PROMPT.md")
VERSION = "grounding-v3"


def conservative_issues(payload):
    """놓치기 쉬운 고위험 단정은 보수적으로 반려. 의미 검사의 대체물이 아니다."""
    issues = []
    for item in payload["items"]:
        if item["item_id"] == "limitations":
            continue
        opinion = item["content"]
        prose = " ".join(str(opinion[k]) for k in ("conclusion", "explanation", "risks"))
        if (not payload.get("attribution_first") and opinion["kind"] == "tension"
                and not re.search(r"절감|확장|완화|처리량|개선|편익|효율", opinion["conclusion"])):
            issues.append({"item_id": item["item_id"], "verdict": "unsupported", "evidence_ids": [],
                           "reason": "상충 결론에 기대 편익이 빠지고 제약만 나열됨. 입력의 편익과 그 실현을 제한하는 조건을 함께 써야 함."})
        if opinion["kind"] == "agreement" and "메모리 용량 확장" in prose and not re.search(r"절감|압축|데이터량 감소", prose):
            issues.append({"item_id": item["item_id"], "verdict": "unsupported", "evidence_ids": [],
                           "reason": "두 기술 모두 메모리 용량 확장이라고 일반화함. RDKV 데이터량 절감과 HW 공간 확장을 구분하고 공통점은 KV 병목 완화로 한정."})
        reactions = re.search(r"(?:운영자|개발자|고객)[^.。\n]{0,80}(?:인지|지지|선호|우려|인정)(?:한다|했다|함)", prose)
        direct_reaction = any(a["assessment_id"].startswith("stakeholders/") and a["basis"] in ("fact", "opinion")
                              and a.get("attributed_to") and a.get("technology_relevance") == "direct"
                              for a in item["assessments"])
        if reactions and not direct_reaction:
            issues.append({"item_id": item["item_id"], "verdict": "unsupported", "evidence_ids": [],
                           "reason": f"당사자 반응을 단정함: {reactions[0]}. 연결 평가는 직접 발언 근거가 아니다. 조건부 해석으로 수정."})
        excerpts = " ".join(e["excerpt"] for e in item["evidence"].values())
        # 실제 미완료를 논문이 명시한 HW-pending 같은 근거와, 단순 자료 공백을 구별한다.
        explicit_pending = re.search(r"remains? pending|not (?:yet )?(?:been )?(?:validated|tested|deployed)|미완료|미실시", excerpts, re.I)
        if not explicit_pending:
            for sentence in re.split(r"[.。\n]", prose):
                if re.search(r"검증 미완료|실증 미완료|검증되지 않았|검증이 이루어지지|호환성 미검증", sentence) and not re.search(r"제공(?:된)? 자료|제공(?:된)? 근거|자료에서|자료 부족|여부.*미확인", sentence):
                    issues.append({"item_id": item["item_id"], "verdict": "unsupported", "evidence_ids": [],
                                   "reason": "미확인 자료를 실제 미검증/미완료로 바꾼 표현. 직접 근거가 없으면 '제공 자료에서 검증 여부 미확인'으로 한정."})
                    break
        eligible = opinion["rd_kv_conditions"] + opinion["photonic_cxl_conditions"]
        if any(re.search(r"검증 완료 전|허용치 미확인 상태", condition) for condition in eligible):
            issues.append({"item_id": item["item_id"], "verdict": "unsupported", "evidence_ids": [],
                           "reason": "검증 전/허용치 미확인 상태를 적합 조건에 넣음. 판단 보류는 undecidable_conditions로, 적합 조건은 확인해야 할 요건으로 구분."})
    return issues


class GroundingError(ValueError):
    """비밀값 없는 검사 진단."""


class Check(StrictModel):
    item_id: Text
    verdict: Literal["supported", "unsupported", "uncertain"]
    reason: Text
    evidence_ids: list[Text]


class Audit(StrictModel):
    checks: list[Check]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def audit_payload(candidate, source):
    assessments = {a["assessment_id"]: a for a in source["assessments"]}
    annotated = source.get("attribution_first") is True
    items = []
    for index, opinion in enumerate(candidate["opinions"], 1):
        items.append({"item_id": f"opinion_{index}", "content": opinion,
                      "assessments": [assessments[aid] for aid in opinion["source_assessment_ids"]
                                      if not annotated or aid in assessments],
                      "evidence": {eid: source["evidence"][eid] for eid in opinion["evidence_ids"]
                                   if not annotated or eid in source["evidence"]}})
    items.append({"item_id": "limitations", "content": {k: candidate[k] for k in ("limitations", "unresolved_relations")},
                  "assessments": source["assessments"], "evidence": source["evidence"]})
    return {"domain": source["domain"], "requirements": source["requirements"],
            "user_request": source.get("user_request", ""),
            "unconfirmed_assessments": source["unconfirmed_assessments"], "trl": source["trl"],
            "metric_comparisons": source["metric_comparisons"], "items": items,
            **({"attribution_first": True, "collected_sources": source.get("collected_sources", []),
                "upstream_draft_findings": source.get("upstream_draft_findings", []),
                "upstream_review_notes": source.get("upstream_review_notes", []),
                "usable_source_reports": source.get("usable_source_reports", [])}
               if annotated else {})}


def annotate_audit(value, payload):
    """Keep valid per-item feedback and report malformed links without rejecting the draft."""
    expected = {item["item_id"]: item for item in payload["items"]}
    checks, diagnostics, seen = [], [], set()
    raw_checks = value.get("checks", []) if isinstance(value, dict) else []
    if not isinstance(raw_checks, list):
        raw_checks = []
    for raw in raw_checks:
        try:
            check = Check.model_validate(raw).model_dump(mode="json")
        except ValueError:
            diagnostics.append({"item_id": "semantic_response", "stage": "semantic_response",
                                "verdict": "uncertain", "reason": "의미 검사 응답의 일부 항목 형식을 읽을 수 없음.",
                                "evidence_ids": []})
            continue
        item_id = check["item_id"]
        if item_id not in expected or item_id in seen:
            diagnostics.append({**check, "stage": "semantic_response", "verdict": "uncertain",
                                "reason": "의미 검사에 알려지지 않았거나 중복된 의견 ID가 있음. " + check["reason"],
                                "evidence_ids": [], "reported_evidence_ids": check["evidence_ids"]})
            continue
        seen.add(item_id)
        invalid = sorted(set(check["evidence_ids"]) - set(expected[item_id]["evidence"]))
        if invalid:
            diagnostics.append({**check, "stage": "semantic_response", "verdict": "uncertain",
                                "reason": "검사기가 의견의 연결 범위 밖 근거 ID를 반환함. 원래 의견은 보존하며 연결 확인이 필요함.",
                                "evidence_ids": [], "invalid_evidence_ids": invalid})
            check = {**check, "verdict": "uncertain", "reason": "검사 근거 연결 미확인. " + check["reason"],
                     "evidence_ids": [eid for eid in check["evidence_ids"] if eid not in invalid]}
        if item_id != "limitations" and check["verdict"] == "supported" and not check["evidence_ids"]:
            check = {**check, "verdict": "uncertain", "reason": "검사 응답에 연결 근거가 없음. " + check["reason"]}
        checks.append(check)
    for item_id in expected.keys() - seen:
        diagnostics.append({"item_id": item_id, "stage": "semantic_response", "verdict": "uncertain",
                            "reason": "이 항목의 의미 검사 응답이 누락됨. 원래 의견은 보존함.", "evidence_ids": []})
    return {"status": "review_required", "checks": checks, "diagnostics": diagnostics,
            "raw_checks": raw_checks}


def validate_audit(value, payload):
    audit = Audit.model_validate(value)
    expected = {item["item_id"]: item for item in payload["items"]}
    ids = [check.item_id for check in audit.checks]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise GroundingError("의미 검사 항목이 누락되거나 중복되었습니다.")
    for check in audit.checks:
        if not set(check.evidence_ids).issubset(expected[check.item_id]["evidence"]):
            raise GroundingError("의미 검사에 연결 범위 밖의 근거가 있습니다.")
        if check.item_id != "limitations" and check.verdict == "supported" and not check.evidence_ids:
            raise GroundingError("근거 없는 의미 검사 통과는 허용하지 않습니다.")
    return {"status": "passed" if all(c.verdict == "supported" for c in audit.checks) else "rejected",
            **audit.model_dump(mode="json")}


def call_grounding(payload, *, model):
    from openai import OpenAI
    with OpenAI(timeout=120, max_retries=0) as client:
        response = client.responses.parse(
            model=model, temperature=0, store=False, max_output_tokens=4500,
            instructions=PROMPT_PATH.read_text(encoding="utf-8") + (
                "\n이번 실행은 출처 귀속을 우선하는 초안이다. collected_sources는 웹 URL과 서지 정보다. "
                "usable_source_reports는 실제 수집한 본문 발췌다. 해당 발췌를 출처에 귀속한 설명과 "
                "조건부 해석은 검토에 활용하되 strict evidence로 승격하지 않는다. "
                "URL만으로 본문 내용을 확인했다고 판단하지 않는다. 상위 분석과 연결 근거에서 "
                "출처가 보고한 내용과 작성자의 해석을 구분해 검토한다. 각 항목에 제공된 evidence의 "
                "키만 evidence_ids에 반환한다. 수집 자료의 source_id를 evidence_id로 대체하지 않는다. "
                "출처의 확인 범위를 명시한 조건부 해석이나 편익 없는 제약 설명 자체는 오류가 아니다. "
                "확인되지 않은 문장은 uncertain과 사유로 표시한다."
                if payload.get("attribution_first") else ""),
            input=json.dumps(payload, ensure_ascii=False), text_format=Audit,
        )
    if response.status != "completed" or response.output_parsed is None:
        raise GroundingError("의미 검사 응답이 거절되었거나 완성되지 않았습니다.")
    return response.output_parsed.model_dump(mode="json")


def is_validated(integrated):
    """편집된 결과/검사 기록이나 구버전 캐시를 통과 결과로 재사용하지 않는다."""
    validation = integrated.get("semantic_validation", {})
    if integrated.get("status") not in ("completed", "partial") or validation.get("status") != "passed":
        return False
    candidate = {k: integrated.get(k, []) for k in ("opinions", "unresolved_relations", "limitations")}
    if not candidate["opinions"] or validation.get("version") != VERSION:
        return False
    checks = validation.get("checks", [])
    expected = {f"opinion_{i}" for i in range(1, len(candidate["opinions"]) + 1)} | {"limitations"}
    try:
        parsed = Audit.model_validate({"checks": checks})
    except ValueError:
        return False
    return (len(checks) == len(expected) and {c.item_id for c in parsed.checks} == expected
            and all(c.verdict == "supported" for c in parsed.checks)
            and validation.get("seal") == fingerprint([candidate, checks]))
