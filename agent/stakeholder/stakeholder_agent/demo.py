"""Explicit offline fixtures demonstrate the contract, never external opinions."""

from .models import (
    GROUPS,
    Assessment,
    Claim,
    Insight,
    ResearchPlan,
    Review,
    SearchQuestion,
    StakeholderTarget,
    Support,
)


class DemoWeb:
    def search(self, query, max_results=3):
        return []

    def fetch(self, url):
        raise RuntimeError("오프라인 데모는 웹 원문을 조회하지 않습니다.")


class DemoModel:
    def generate(self, schema, system, payload):
        context = payload["analysis_context"]
        domains = context["domains"]
        if schema is ResearchPlan:
            # This deterministic fixture only demonstrates that additional
            # context can change selection. Production selection is the LLM plan.
            extra = context.get("additional_context", "") + " ".join(context.get("extra_fields", {}).values())
            roles = ["operator", "developer", "supplier", "observer"]
            if "고객" in extra and ("SLA" in extra or "요금" in extra):
                roles.append("customer")
            targets = []
            for domain in domains:
                for role in roles:
                    name = GROUPS[role]
                    reason = f'{domain["name"]}의 {domain["scenario"]}에서 {name} 관점을 확인하는 데모 후보'
                    if role == "customer":
                        reason = "추가 맥락에서 기업 고객의 SLA·요금에 대한 우려를 요청함"
                    if role == "operator" and "구매" in extra:
                        name = "도입·운영 및 구매 담당자"
                        reason = "운영 조건과 함께 추가 맥락의 구매 절차·조달 장벽을 확인하는 데모 후보"
                    targets.append(StakeholderTarget(id=role, domain_id=domain["id"], name=name, reason=reason,
                                                     priority="conditional" if role == "customer" else "core"))
            return ResearchPlan(stakeholders=targets, questions=[SearchQuestion(
                tech_id=tech["id"], domain_id=domain["id"], group="operator",
                query=f'{tech["name"]} {domain["name"]} deployment feedback',
                reason="오프라인 흐름 검증용 질문")
                for domain in domains for tech in payload["technologies"]])
        if schema is Review:
            return Review(rejected_claim_indices=[], issues=[], queries=[])
        if schema is Assessment:
            claims, summary = [], []
            for domain in domains:
                indices = []
                for tech in payload["technologies"]:
                    records = [e for e in payload["evidence"] if tech["id"] in e["tech_ids"]]
                    if not records:
                        continue
                    record = records[0]
                    quote = next(iter(record["quote_options"].values()))
                    indices.append(len(claims))
                    claims.append(Claim(
                        tech_id=tech["id"], domain_id=domain["id"], group="operator",
                        aspect="evaluation", kind="paper_report", text=quote,
                        condition=f'{domain["name"]}: 입력 논문 발췌이며 이해관계자의 실제 평가나 환경 검증이 아님',
                        source_scope="direct", supports=[Support(evidence_id=record["id"], quote=quote)]))
                if indices:
                    summary.append(Insight(text="외부 평가는 조사하지 않은 오프라인 데모이며 논문 근거만 전달합니다.",
                                           claim_indices=indices))
            return Assessment(claims=claims[:payload["max_claims"]], summary=summary, implications=[],
                              limitations=["실제 LLM 및 외부 검색을 사용하지 않은 연결 검증용 데모입니다."],
                              follow_up=["live 모드에서 선정한 주체들의 실제 평가·발언을 조사해야 합니다."])
        raise ValueError("Unsupported demo schema")
