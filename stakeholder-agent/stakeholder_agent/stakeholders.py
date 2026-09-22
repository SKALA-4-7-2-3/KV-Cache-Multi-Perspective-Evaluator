"""Validate selected roles and describe coverage without inventing missing opinions."""

import re

from .models import GROUPS, StakeholderTarget

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,95}\Z", re.ASCII)


def operating_organizations(domains):
    """One decision-making organization per requested domain, not a role inventory."""
    return [StakeholderTarget(
        id="operator", domain_id=domain.id,
        name=f"{domain.name}의 LLM 추론 서비스 운영 조직",
        reason="이 조직의 기대 이익, 도입 및 운영 부담, 우려 사항과 도입 검토 조건을 비교한다.",
    ) for domain in domains]


def select_targets(candidates, domains):
    """Accept bounded model selections; a missing domain gets an explicit fallback."""
    domain_ids = {d.id for d in domains}
    targets, issues, seen = [], [], set()
    for target in candidates:
        key = (target.domain_id, target.id.casefold())
        if (target.domain_id not in domain_ids or not _ID.fullmatch(target.id)
                or not target.name.strip() or not target.reason.strip()):
            issues.append("입력 도메인·역할 ID·이름·선정 이유가 유효하지 않은 조사 대상을 제외했습니다.")
        elif key in seen:
            issues.append(f"중복 조사 대상 제외: {target.domain_id}/{target.id}")
        elif sum(t.domain_id == target.domain_id for t in targets) >= 8:
            issues.append(f"{target.domain_id}: 실행 한도상 역할군 8개를 넘는 선정은 보류했습니다.")
        else:
            seen.add(key)
            targets.append(target)
    selected_count = len(targets)
    missing = [d for d in domains if not any(t.domain_id == d.id for t in targets)]
    for domain in missing:
        issues.append(f"{domain.id}: 역할 선정안을 확보하지 못해 기본 조사 후보를 사용합니다. 입력 맞춤 선정 미완료.")
        for role in ("operator", "developer", "supplier", "observer"):
            targets.append(StakeholderTarget(
                id=role, domain_id=domain.id, name=GROUPS[role],
                reason="선정안 미확보로 사용한 기본 후보. 이 역할의 적합성은 추가 확인이 필요합니다."))
    origin = "model" if not missing else ("mixed" if selected_count else "fallback")
    return targets, origin, list(dict.fromkeys(issues))


def coverage_for(parsed, plan, indexed_claims, research_log):
    """Search attempts and evidence availability are independent, observable facts."""
    rows = []
    for target in plan.stakeholders:
        for tech in parsed.technologies:
            own = [(i, c) for i, c in indexed_claims if c.domain_id == target.domain_id
                   and c.tech_id == tech.id and c.group == target.id and c.kind != "unknown"]
            events = [e for e in research_log if e["domain_id"] == target.domain_id
                      and e["tech_id"] == tech.id and e["group"] == target.id]
            search_status = ("searched" if any(e["status"] == "searched" for e in events)
                             else "failed" if events else "not_searched")
            statements = [c for _, c in own if c.kind == "statement" and c.actor.strip()]
            level = ("direct" if any(c.source_scope == "direct" for c in statements)
                     else "family" if statements else "inference_only" if own else "unavailable")
            rows.append({"domain_id": target.domain_id, "tech_id": tech.id, "group": target.id,
                         "search_status": search_status, "evidence_status": level,
                         "claim_indices": [i for i, _ in own]})
    return rows


def aggregate_evidence_status(parsed, coverage):
    required = {(d.id, t.id) for d in parsed.analysis_context.domains for t in parsed.technologies}
    direct = {(r["domain_id"], r["tech_id"]) for r in coverage if r["evidence_status"] == "direct"}
    if required and required <= direct:
        # This label says both technologies have directly related observations,
        # not that every role was investigated or the statements are true.
        return "direct_available"
    return "limited" if any(r["evidence_status"] != "unavailable" for r in coverage) else "unavailable"
