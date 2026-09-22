"""8칸·인용·TRL·비교 조건을 검증한다. 네트워크/LLM 호출과 입력 변경은 없다."""

from collections import defaultdict
from itertools import product
from pydantic import ValidationError

from .rubric import COMMON_CRITERIA, CRITERIA, NOTICE, ROLES, TECHNOLOGIES, TRL, VERSION
from .schema import Assessment, Config, Document, Evidence, Issue, Review, RoleResult, Synthesis
from .contract import is_missing


def _unknown(criterion: str, reason: str) -> dict:
    return Assessment(
        criterion_id=criterion, judgment="unknown", conclusion="판단 보류",
        basis="inference", gaps=[reason],
    ).model_dump(mode="json")


def _metric_comparison(left: dict, right: dict) -> dict:
    keys = ("name", "unit", "model", "hardware", "baseline", "context_tokens", "concurrency", "workload", "method")
    different = [k for k in keys if left[k] != right[k]]
    missing = [k for k in keys if is_missing(left[k]) or is_missing(right[k])]
    return {
        "sw": left, "hw": right,
        "conditions_match": not different and not missing,
        "different_fields": different, "missing_fields": missing,
        "interpretation": (
            "구조화된 조건이 일치함. 실제 동등성은 사람이 확인한다. 자동 순위·배수 계산 없음."
            if not different and not missing else "지표 또는 조건이 달라 직접 수치 비교 불가."
        ),
    }


def review_node(state: dict) -> dict:
    """팀 LangGraph에 그대로 등록. {'review': ..., 'synthesis': ...}만 반환한다."""
    issues: list[Issue] = []
    requests: dict[str, list[str]] = defaultdict(list)
    blocked_roles = set()

    def flag(code, message, role=None, tech=None, criterion=None, repairable=False):
        issues.append(Issue(code=code, message=message, role=role, technology_id=tech,
                            criterion_id=criterion, repairable=repairable))
        query = f"{tech or role}/{criterion or 'input'}: {message}"
        if repairable and role and query not in requests[role]:
            requests[role].append(query)

    previous = state.get("review", {})
    previous = previous if isinstance(previous, dict) else {}
    round_no = previous.get("round", 0) if isinstance(previous, dict) else 0
    if type(round_no) is not int or round_no not in (0, 1):
        flag("invalid_round", "review.round는 0 또는 1이어야 한다.")
        round_no = 1
    try:
        config = Config.model_validate(state.get("config", {}))
        if config.rubric_version not in (VERSION, "review-rubric-1.0"):
            flag("rubric_version", "입력과 검수 코드의 Rubric 버전이 다르다.")
    except ValidationError:
        flag("invalid_config", "config의 run_id·domain·requirements 형식을 확인한다.")
        config = Config(run_id="invalid", domain="미확인")

    documents: dict[str, Document] = {}
    raw_docs = state.get("documents", {})
    if isinstance(raw_docs, dict):
        for doc_id, raw in raw_docs.items():
            try:
                documents[doc_id] = Document.model_validate(raw)
            except ValidationError:
                flag("invalid_document", "문서 메타데이터 형식을 확인한다.")
    for tech in TECHNOLOGIES:
        doc = documents.get(tech)
        if not doc or doc.kind != "paper" or doc.version != "v1":
            flag("required_document", "선정 논문 2편의 v1 메타데이터가 필요하다.", tech=tech)
    unique_pages = {}
    for doc in documents.values():
        unique_pages[doc.sha256] = max(unique_pages.get(doc.sha256, 0), doc.pages)
    if sum(unique_pages.values()) > 200:
        flag("page_limit", "문서 합계가 200쪽을 초과한다.")
    fatal = bool(issues)

    # 오류 원문에는 키·요청 본문이 섞일 수 있어 내용은 그대로 복사하지 않는다.
    raw_errors = state.get("errors", {})
    if isinstance(raw_errors, dict):
        for error in raw_errors.values():
            if isinstance(error, dict):
                error_round = error.get("round", round_no)
                if error.get("resolved") or (type(error_round) is int and error_round < round_no):
                    continue  # 이전 회차 이력은 보존하되 현재 회차의 실행 오류로 중복 판정하지 않는다.
                role = error.get("role") if error.get("role") in ROLES else None
                if role and not error.get("retryable", False):
                    blocked_roles.add(role)
                flag("upstream_error", "상위 노드가 실행 오류를 보고했다.", role=role,
                     repairable=bool(error.get("retryable")) and not error.get("fatal", False))
                fatal = fatal or bool(error.get("fatal"))

    evidence: dict[str, Evidence] = {}
    raw_evidence = state.get("evidence", {})
    if isinstance(raw_evidence, dict):
        for eid, raw in raw_evidence.items():
            try:
                item = Evidence.model_validate(raw)
                doc = documents.get(item.doc_id)
                valid = (
                    eid == item.id and doc is not None and item.verified_source
                    and (not item.synthetic or config.demo)
                    and (item.page is not None or bool(item.location and item.location.strip()))
                    and (doc.kind != "paper" or item.page is not None)
                    and (item.page is None or item.page <= doc.pages)
                    and (doc.kind == "paper" or doc.source_type is not None)
                )
                if valid:
                    evidence[eid] = item
            except ValidationError:
                pass  # 실제로 인용된 잘못된 근거만 아래에서 해당 역할의 오류로 기록한다.

    def refs_valid(ids, tech):
        return bool(ids) and all(eid in evidence and tech in evidence[eid].technology_ids for eid in ids)

    def assess_trl(cell, tech):
        level, used, checks = None, set(), []
        if not cell.trl_checks:
            flag("trl_missing", "단계별 TRL 근거가 없어 숫자를 보류한다.", "technical", tech,
                 "maturity", True)
        if any(n not in TRL for n in cell.trl_checks):
            flag("trl_level", "TRL 체크 키는 1~9여야 한다.", "technical", tech, "maturity", True)
        consecutive = True
        for n, (criterion, requirement) in TRL.items():
            check = cell.trl_checks.get(n)
            status = check.status if check else "unknown"
            ids = list(check.evidence_ids) if check else []
            reason = check.reason if check else "해당 단계 근거 미입력"
            # v1의 성숙도를 평가하므로 일반 CXL/양자화·최신 웹 자료의 성숙도를 대입하지 않는다.
            valid = refs_valid(ids, tech) and all(evidence[eid].doc_id == tech for eid in ids)
            if (ids or status != "unknown") and not valid:
                status, ids, reason = "unknown", [], "v1 원문의 유효한 근거가 없다."
                flag("trl_citation", f"TRL {n} 판정의 v1 근거를 보완한다.", "technical", tech, "maturity", True)
            if status == "met" and n >= 7:
                methods = {evidence[eid].method for eid in ids}
                allowed = {"qualification", "operational"} if n == 8 else {"operational"}
                if not methods.intersection(allowed):
                    status, reason = "unknown", "실제 운용/완성 시스템 검증 근거를 확인하지 못했다."
                    flag("trl_environment", f"TRL {n}에 필요한 운용·검증 증거를 확인한다.", "technical", tech, "maturity", True)
            if status == "met" and consecutive:
                level = n
                used.update(ids)
            else:
                if status == "met":
                    flag("trl_gap", f"TRL {n} 이전 단계의 필수 조건이 미확인이다.", "technical", tech, "maturity", True)
                consecutive = False
            checks.append({"level": n, "criterion": criterion, "required_evidence": requirement,
                           "status": status, "reason": reason, "evidence_ids": ids})
        return {"level": level, "basis_version": "v1", "checks": checks,
                "evidence_ids": sorted(used),
                "next_unconfirmed": next((c for c in checks if c["status"] != "met"), None),
                "notice": NOTICE}

    normalized: dict[str, dict] = {}
    trl_results, used_ids = {}, set()
    input_cells = 0
    assessments = state.get("assessments", {})
    assessments = assessments if isinstance(assessments, dict) else {}
    for role in ROLES:
        normalized[role] = {}
        result = None
        if not fatal:
            try:
                result = RoleResult.model_validate(assessments.get(role, {}))
                stale = round_no == 1 and role in previous.get("dirty_roles", []) and result.round != 1
                if result.round > round_no or stale:
                    flag("stale_round", "재평가 대상 역할의 최신 회차 결과가 필요하다.", role, repairable=True)
                    result = None
            except ValidationError:
                flag("role_schema", "역할 결과의 스키마 또는 필수 필드가 잘못되었다.", role, repairable=True)
        for tech in TECHNOLOGIES:
            cell = result.results.get(tech) if result else None
            usable = cell is not None and result.status != "failed" and cell.status != "failed"
            if usable:
                input_cells += 1
            else:
                if not fatal:
                    flag("missing_cell", "해당 기술의 평가 결과가 없거나 역할 실행이 실패했다.", role, tech, repairable=True)
                normalized[role][tech] = {"status": "failed", "items": [
                    _unknown(c, "평가 결과 없음 또는 실패") for c in CRITERIA[role]
                ]}
                continue

            found = defaultdict(list)
            for item in cell.items:
                found[item.criterion_id].append(item)
            for cid in found.keys() - CRITERIA[role].keys():
                flag("unknown_criterion", "Rubric에 없는 criterion_id는 종합에서 제외한다.", role, tech, cid, True)
            items = []
            for cid in CRITERIA[role]:
                candidates = found[cid]
                if len(candidates) != 1:
                    flag("criterion_count", "필수 기준별 결과는 정확히 1개여야 한다.", role, tech, cid, True)
                    items.append(_unknown(cid, "평가 항목 누락 또는 중복"))
                    continue
                item = candidates[0]
                problems = []
                known = item.judgment not in ("unknown", "failed")
                if known and not refs_valid(item.evidence_ids, tech):
                    problems.append("판정에 해당 기술의 검증 가능한 출처가 필요하다.")
                if item.evidence_ids and not refs_valid(item.evidence_ids, tech):
                    problems.append("인용 ID·기술 연결·페이지·원문 확보 상태를 확인한다.")
                if known and not item.conditions:
                    problems.append("판정의 적용 조건이 필요하다.")
                if known and item.basis == "unknown":
                    problems.append("확정 평가에는 사실·추론 구분이 필요하다.")
                if known and item.basis == "opinion" and not item.attributed_to:
                    problems.append("실제 의견(opinion)은 발언 주체와 원문 근거가 필요하다.")
                if item.judgment in ("met", "favorable", "unfavorable") and cid not in config.requirements:
                    problems.append("목표 요구값이 없으므로 충족(met)을 판정할 수 없다.")
                if item.judgment in ("met", "favorable", "unfavorable") and (item.analysis_scope != "selected_domain" or item.domain_relevance != "direct"):
                    problems.append("선택 도메인의 직접 관련성 없이 favorable/unfavorable을 판정할 수 없다.")
                if any(not refs_valid(m.evidence_ids, tech) for m in item.metrics):
                    problems.append("정량 수치에 유효한 출처가 필요하다.")
                metric_gaps = []
                for metric in item.metrics:
                    experiments = {"gpu_experiment", "hardware_measurement", "emulation", "simulation"}
                    source_methods = {evidence[eid].method for eid in metric.evidence_ids if eid in evidence} & experiments
                    if metric.method in experiments and source_methods and metric.method not in source_methods:
                        problems.append("정량 지표와 Evidence의 검증 방식이 충돌한다. 실측·GPU 실험·에뮬레이션·시뮬레이션을 확인한다.")
                    missing = [key for key in (
                        "model", "hardware", "baseline", "context_tokens", "concurrency", "workload", "method"
                    ) if is_missing(getattr(metric, key))]
                    if missing:
                        metric_gaps.append(f"{metric.name}: {', '.join(missing)} 미확인. 값은 원문 보고로 보존하되 직접 비교·요구 충족 판정에는 쓰지 않는다.")
                for problem in problems:
                    flag("invalid_assessment", problem, role, tech, cid, True)
                for query in item.need_more:
                    flag("need_more", query, role, tech, cid, True)
                if problems:
                    items.append(_unknown(cid, " / ".join(dict.fromkeys(problems))))
                    continue
                clean = item.model_dump(mode="json")
                clean["evidence_ids"] = list(dict.fromkeys(item.evidence_ids + [eid for m in item.metrics for eid in m.evidence_ids]))
                clean["gaps"] = list(dict.fromkeys(item.gaps + metric_gaps))
                if metric_gaps and item.judgment in ("met", "favorable", "unfavorable"):
                    clean.update(judgment="unknown", conclusion="실험 조건 부족으로 요구 충족 판단 보류", basis="unknown", confidence="unavailable")
                if item.judgment in ("unknown", "failed"):
                    # 유효 출처가 있어도 판단 불가로 표시된 내용은 확정 결론으로 재사용하지 않는다.
                    clean["conclusion"] = "판단 보류"
                    clean["gaps"] = clean["gaps"] or ["판정에 필요한 자료 부족"]
                    # 유효한 수치는 평가 결론과 분리해 원문 보고값으로 보존한다.
                    if item.judgment == "failed":
                        clean["metrics"] = []
                    clean["basis"] = "unknown"
                    clean["confidence"] = "unavailable"
                items.append(clean)
            if role == "technical":
                trl = assess_trl(cell, tech)
                trl_results[tech] = trl
                used_ids.update(eid for check in trl["checks"] for eid in check["evidence_ids"] if eid in evidence)
                for item in items:
                    if item["criterion_id"] == "maturity":
                        item.update(judgment="conditional" if trl["level"] else "unknown",
                                    conclusion=f"공개 근거로 확인한 TRL {trl['level']} (추정)" if trl["level"] else "TRL 판단 보류",
                                    basis="inference" if trl["level"] else "unknown",
                                    conditions=["선정 논문 v1에 기록된 검증 범위"],
                                    evidence_ids=trl["evidence_ids"], metrics=[])
                        if trl["level"] is None:
                            item["gaps"] = list(dict.fromkeys(item["gaps"] + ["TRL 단계 근거 미확인"]))
            unknown = result.status == "unknown" or cell.status == "unknown" or any(i["judgment"] in ("unknown", "failed") for i in items)
            normalized[role][tech] = {"status": "unknown" if unknown else "completed", "items": items}
            for item in items:
                used_ids.update(item["evidence_ids"])
                for metric in item["metrics"]:
                    used_ids.update(metric["evidence_ids"])

    comparisons, differences, metrics = [], [], []
    for cid, label in COMMON_CRITERIA.items():
        row = {"criterion_id": cid, "label": label}
        for tech in TECHNOLOGIES:
            entries = [{"role": role, **item} for role in ROLES for item in normalized[role][tech]["items"] if item["criterion_id"] == cid]
            row[tech] = entries
            known = [entry for entry in entries if entry["judgment"] not in ("unknown", "failed")]
            if len({entry["judgment"] for entry in known}) > 1:
                differences.append({"technology_id": tech, "criterion_id": cid, "entries": known,
                                    "note": "관점별 판정 차이. 조건 차이인지 실제 모순인지 사람이 확인한다."})
        comparisons.append(row)
    for role in ROLES:
        left = [m for item in normalized[role]["SW-01"]["items"] for m in item["metrics"]]
        right = [m for item in normalized[role]["HW-01"]["items"] for m in item["metrics"]]
        metrics.extend({"role": role, **_metric_comparison(a, b)} for a, b in product(left, right))

    gaps = [i.message for i in issues]
    gaps.extend(f"{role}/{tech}/{item['criterion_id']}: {gap}"
                for role in ROLES for tech in TECHNOLOGIES
                for item in normalized[role][tech]["items"] for gap in item["gaps"])
    has_unknown = any(normalized[r][t]["status"] != "completed" for r in ROLES for t in TECHNOLOGIES)
    status = "failed" if fatal else "partial" if gaps or has_unknown else "completed"
    if not fatal and input_cells == 0:
        status = "failed"
    dirty = [role for role in ROLES if requests.get(role) and role not in blocked_roles] if round_no == 0 and not fatal else []
    if "technical" in dirty:
        dirty = [role for role in ROLES if role not in blocked_roles]
        for role in dirty:
            if role == "technical":
                continue
            requests[role].append("갱신된 기술 결과에 기반해 재평가한다.")
    if round_no == 1 and any(i.repairable for i in issues):
        gaps.append("재평가 1회 한도에 도달했다. 미확인 사항을 남기고 종료한다.")
    references = []
    for doc_id, doc in documents.items():
        ids = sorted(eid for eid in used_ids if evidence[eid].doc_id == doc_id)
        if ids:
            references.append({"doc_id": doc_id, **doc.model_dump(mode="json"),
                               "evidence": [{"id": eid, "page": evidence[eid].page,
                                             "location": evidence[eid].location} for eid in ids]})
    review = Review(
        round=round_no, status=status, next="repair" if dirty else "render", input_cells=input_cells,
        dirty_roles=dirty, repair_requests={r: requests[r][:2] for r in dirty}, checks=issues,
        gaps=list(dict.fromkeys(gaps)), rubric_version=VERSION,
    )
    summaries = []
    for tech, name in TECHNOLOGIES.items():
        fit = next(i for i in normalized["domain"][tech]["items"] if i["criterion_id"] == "domain_fit")
        if fit["judgment"] != "unknown":
            summaries.append(f"{name}: {'; '.join(fit['conditions'])} 조건에서 {fit['conclusion']} [{', '.join(fit['evidence_ids'])}]")
        else:
            summaries.append(f"{name}: 선정 도메인의 적합성은 근거 부족 또는 실행 실패로 판단 보류.")
    summaries.append(
        ("[DUMMY: 실제 평가 아님] " if config.demo else "")
        + f"유효 입력 {input_cells}/8칸, 상태 {status}. 지표·조건 차이와 미확인 사항을 보존하며 총점 순위는 만들지 않는다. "
        + NOTICE
    )
    synthesis = Synthesis(
        comparison_matrix=[{"perspective": role, **normalized[role]} for role in ROLES],
        by_criterion=comparisons, view_differences=differences, metric_comparisons=metrics,
        trl=trl_results, used_evidence_ids=sorted(used_ids), references=references,
        summary=summaries,
        disclaimer=NOTICE + " 형식·인용 검사는 주장의 진실성을 보증하지 않으며 핵심 결론은 사람이 원문과 대조한다.",
        demo=(config.demo or (isinstance(raw_evidence, dict) and any(isinstance(e, dict) and e.get("synthetic") is True for e in raw_evidence.values()))
              or (isinstance(state.get("assessments"), dict) and any(isinstance(r, dict) and r.get("demo") is True for r in state["assessments"].values()))),
    )
    return {"review": review.model_dump(mode="json"), "synthesis": synthesis.model_dump(mode="json")}


def route_after_review(state: dict) -> str:
    return state["review"]["next"]


def prepare_repair(state: dict) -> dict:
    """상위 역할이 재검색·재평가할 회차를 준비한다. 검색 자체는 해당 담당이 수행한다."""
    review = state["review"]
    if review["next"] != "repair" or review["round"] != 0:
        raise ValueError("재평가는 review가 요청한 1회만 가능하다.")
    return {"review": {**review, "round": 1, "next": "render"}}
