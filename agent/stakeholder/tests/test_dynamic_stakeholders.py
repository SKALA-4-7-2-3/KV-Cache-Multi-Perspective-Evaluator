"""The real graph selects relevant roles without manufacturing opinions or coverage."""

from copy import deepcopy

import pytest
from test_domains import DOMAINS, HW_QUOTE, SW_QUOTE, config, input_markdown

from stakeholder_agent.legacy import run_detailed
from stakeholder_agent.models import (
    Assessment,
    Claim,
    Insight,
    ResearchPlan,
    Review,
    SearchQuestion,
    StakeholderTarget,
    Support,
    WebSourceReview,
)
from stakeholder_agent.providers import SearchHit, SourcePage

WEB_URL = "https://example.org/rdkv-photonic-cxl-opinion"
WEB_QUOTE = (
    "Example Research Group reports that RDKV and Photonic-CXL each require "
    "integration testing before production use."
)


def target(role="site-ops", domain_id="D-MOBILE", name="현장 시스템 운영팀", priority="core"):
    return StakeholderTarget(id=role, domain_id=domain_id, name=name,
                             reason=f"{domain_id} 사용 상황에서 {name}의 조건을 조사한다.",
                             priority=priority)


def selected_roles(domain_id="D-MOBILE"):
    return [target(domain_id=domain_id),
            target("runtime-team", domain_id, "런타임 통합 개발팀"),
            target("external-reviewer", domain_id, "독립 기술 평가자")]


def question(domain_id="D-MOBILE", tech_id="SW-01", role="site-ops", suffix="initial"):
    return SearchQuestion(domain_id=domain_id, tech_id=tech_id, group=role,
                          query=f"{domain_id} {tech_id} {role} {suffix}", reason="실제 평가 확인")


def observation(domain_id="D-MOBILE", tech_id="SW-01", role="site-ops", text="운영 검토 표식"):
    return Claim(domain_id=domain_id, tech_id=tech_id, group=role, aspect="adoption_condition",
                 kind="inference", text=text, condition="입력 논문 범위의 조건부 검토",
                 source_scope="direct", supports=[Support(
                     evidence_id="E-SW-001" if tech_id == "SW-01" else "E-HW-001",
                     quote=SW_QUOTE if tech_id == "SW-01" else HW_QUOTE)])


def draft(claims=None, summary=None):
    return Assessment(claims=claims or [], summary=summary or [], implications=[],
                      limitations=[], follow_up=[])


def named_statement(payload, *, domain_id="D-MOBILE", tech_id="SW-01", role="site-ops"):
    record = next(item for item in payload["evidence"] if item["url"] == WEB_URL)
    return Claim(domain_id=domain_id, tech_id=tech_id, group=role, aspect="evaluation",
                 kind="statement", text=f"Example Research Group의 통합 시험 필요 평가 {tech_id}",
                 actor="Example Research Group", actor_relationship="observer",
                 condition="작성자에게 귀속된 평가이며 실제 도입의 증거가 아님",
                 source_scope="direct", supports=[Support(evidence_id=record["id"], quote=WEB_QUOTE)])


class Model:
    def __init__(self, roles=None, questions=None, result=None, repair_questions=None):
        self.roles = selected_roles() if roles is None else roles
        self.questions = questions if questions is not None else [
            question(tech_id=tech_id) for tech_id in ("SW-01", "HW-01")]
        self.result = result or draft()
        self.repair_questions = repair_questions or []
        self.calls = []

    def generate(self, schema, system, payload):
        self.calls.append((schema.__name__, system, deepcopy(payload)))
        if schema is ResearchPlan:
            result = ResearchPlan(stakeholders=self.roles, questions=self.questions)
        elif schema is Assessment:
            result = self.result(payload) if callable(self.result) else self.result
            result = result.model_copy(deep=True)
            result.source_reviews = [WebSourceReview(
                evidence_id=record["id"], document_type="commentary", perspective="independent_author",
                relevance="direct", evidence_basis="opinion", decision="limited",
                reasons=["명시된 작성자의 기술 평가"], limitations=["실제 도입 사례나 독립 실증이 아님"],
                basis_quotes=[WEB_QUOTE]) for record in payload["evidence"] if record["url"] == WEB_URL]
        else:
            result = Review(rejected_claim_indices=[], issues=[], queries=self.repair_questions)
        return result.model_copy(deep=True)


class Web:
    def __init__(self, results=False, failed=False):
        self.results, self.failed = results, failed
        self.search_calls, self.fetch_calls = [], []

    def search(self, query, max_results=3):
        self.search_calls.append(query)
        if self.failed:
            raise TimeoutError("controlled test failure")
        return [SearchHit(url=WEB_URL, title="RDKV and Photonic-CXL opinion")] if self.results else []

    def fetch(self, url):
        self.fetch_calls.append(url)
        return SourcePage(url=url, title="RDKV and Photonic-CXL opinion", text=WEB_QUOTE,
                          publisher="Example Research Group", published_at="2026-09-01")


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Dynamic stakeholder tests must not make real HTTP requests")

    monkeypatch.setattr("httpx.Client.request", blocked)
    monkeypatch.setattr("httpx.Client.stream", blocked)


def test_three_selected_roles_do_not_expand_to_the_old_fixed_customer_grid():
    model = Model(result=draft([observation()]))
    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(), model=model, web=Web())
    assert state["errors"] == []
    assert state["rejected"] == []
    assert [role.id for role in state["plan"].stakeholders] == [role.id for role in selected_roles()]
    assert len(state["coverage"]) == 3 * 2
    assert "customer" not in {row["group"] for row in state["coverage"]}
    assert "도입 조직·서비스 이용자" not in state["output_md"]
    for role in selected_roles():
        assert role.name in state["output_md"]
    assert model.calls[0][2]["selected_stakeholders"] == []
    for _, _, payload in model.calls[1:]:
        assert payload["selected_stakeholders"] == [role.model_dump() for role in selected_roles()]
    assert state["execution_status"] == "completed"
    assert state["evidence_status"] == "limited"
    assert state["status"] == "partial"


def test_extra_sla_context_reaches_every_model_stage_and_can_select_a_conditional_role():
    class ContextualModel(Model):
        def generate(self, schema, system, payload):
            if schema is ResearchPlan and "SLA" in payload["analysis_context"]["extra_fields"].get("추가 검토", ""):
                self.roles = selected_roles() + [target("contract-customer", name="계약상 SLA 책임자",
                                                        priority="conditional")]
            return super().generate(schema, system, payload)

    source = input_markdown(DOMAINS[:1]).replace(
        "### 대상 도메인", "- 추가 검토: SLA 책임 주체를 검토하되 실제 계약·채택을 가정하지 않는다.\n\n"
        "### 참고 요청\n\n향후 클라우드 이전 가능성은 참고어이며 대상 도메인 추가 요청이 아니다.\n\n### 대상 도메인")
    model = ContextualModel()
    state = run_detailed(source, config=config(), model=model, web=Web())
    assert state["errors"] == []
    assert [domain.id for domain in state["parsed"].analysis_context.domains] == ["D-MOBILE"]
    for _, _, payload in model.calls:
        context = payload["analysis_context"]
        assert context["extra_fields"] == {"추가 검토": "SLA 책임 주체를 검토하되 실제 계약·채택을 가정하지 않는다."}
        assert "참고어이며 대상 도메인 추가 요청이 아니다" in context["additional_context"]
        assert context["domains"] == DOMAINS[:1]
        assert payload["max_claims"] == 12
        assert "selected_stakeholders" in payload
    assert [role.id for role in state["plan"].stakeholders][-1] == "contract-customer"
    assert state["plan"].stakeholders[-1].priority == "conditional"
    assert "계약상 SLA 책임자" in state["output_md"]
    assert len(state["coverage"]) == 4 * 2
    assert state["evidence_status"] == "unavailable"


def test_roles_are_domain_local_and_invalid_selection_queries_and_claims_cannot_leak():
    roles = selected_roles() + [target("lab-maintainer", "D-LAB", "연구 서버 관리자")]
    roles += [target("SITE-OPS"), target("bad/id", "D-MOBILE", "잘못된 역할"),
              target("invented", "D-INVENTED", "없는 도메인 역할"),
              target("unnamed", name=" "),
              target("unexplained").model_copy(update={"reason": " "})]
    claims = [observation(text="현장 운영 검토"),
              observation("D-LAB", "HW-01", "lab-maintainer", "연구 서버 검토"),
              observation("D-LAB", role="site-ops", text="다른 도메인 역할을 잘못 사용"),
              observation(role="invented", text="선정하지 않은 역할을 잘못 사용")]
    queries = [question(), question("D-LAB", "HW-01", "lab-maintainer"),
               question("D-LAB", role="site-ops", suffix="MUST-NOT-SEARCH"),
               question(role="invented", suffix="MUST-NOT-SEARCH")]
    model, web = Model(roles, queries, draft(claims)), Web()
    state = run_detailed(input_markdown(), config=config(), model=model, web=web)
    selected = [(role.domain_id, role.id) for role in state["plan"].stakeholders]
    assert len(selected) == len(set(selected)) == 4
    assert ("D-LAB", "site-ops") not in selected
    assert all(role_id not in {"bad/id", "invented"} for _, role_id in selected)
    assert state["rejected"] == [2, 3]
    assert all("MUST-NOT-SEARCH" not in query for query in web.search_calls)
    assert "현장 운영 검토" in state["output_md"]
    assert "연구 서버 검토" in state["output_md"]
    assert "다른 도메인 역할을 잘못 사용" not in state["output_md"]
    assert "선정하지 않은 역할을 잘못 사용" not in state["output_md"]
    assert {(row["domain_id"], row["group"]) for row in state["coverage"]} == set(selected)


def test_a_domain_without_selection_gets_only_an_explicit_fallback():
    state = run_detailed(input_markdown(), config=config(), model=Model(), web=Web())
    assert state["selection_origin"] == "mixed"
    mobile = [role.id for role in state["plan"].stakeholders if role.domain_id == "D-MOBILE"]
    laboratory = [role.id for role in state["plan"].stakeholders if role.domain_id == "D-LAB"]
    assert mobile == [role.id for role in selected_roles()]
    assert set(laboratory) == {"operator", "developer", "supplier", "observer"}
    assert any("D-LAB" in gap and "선정" in gap for gap in state["gaps"])
    assert state["execution_status"] == "partial"


def test_successful_empty_searches_and_unsearched_roles_have_distinct_coverage():
    web = Web()
    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(search_limit=2), model=Model(), web=web)
    assert len(web.search_calls) == 2
    assert len(state["research_log"]) == 2
    assert all(event["status"] == "searched" for event in state["research_log"])
    for row in state["coverage"]:
        assert row["evidence_status"] == "unavailable"
        assert row["claim_indices"] == []
        assert row["search_status"] == ("searched" if row["group"] == "site-ops" else "not_searched")
    assert state["execution_status"] == "completed"
    assert state["evidence_status"] == "unavailable"
    assert state["status"] == "partial"


def test_failed_searches_are_not_reported_as_successful_empty_searches():
    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(search_limit=2),
                         model=Model(), web=Web(failed=True))
    assert all(event["status"] == "failed" for event in state["research_log"])
    assert {row["search_status"] for row in state["coverage"] if row["group"] == "site-ops"} == {"failed"}
    assert state["execution_status"] == "partial"
    assert state["evidence_status"] == "unavailable"


def test_named_external_evaluations_and_analytical_conditions_are_rendered_separately():
    def result(payload):
        return draft([named_statement(payload), named_statement(payload, tech_id="HW-01"),
                      observation(role="runtime-team", text="논문에서 도출한 통합 확인 조건")])

    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(),
                         model=Model(result=result), web=Web(results=True))
    assert state["errors"] == []
    assert state["rejected"] == []
    assert len(state["draft"].claims) == 3
    assert state["execution_status"] == "completed"
    assert state["evidence_status"] == "direct_available"
    assert state["status"] == "completed"
    section = state["output_md"].split("## 이해관계자별 SW/HW 비교", 1)[1].split("## 이해 상충", 1)[0]
    statements, analytical = section.split("#### 논문 기반 영향·검토 사항", 1)
    assert "Example Research Group의 통합 시험 필요 평가" in statements
    assert "논문에서 도출한 통합 확인 조건" not in statements
    assert "논문에서 도출한 통합 확인 조건" in analytical
    assert "분석적 추론" in analytical
    assert {row["evidence_status"] for row in state["coverage"] if row["group"] == "site-ops"} == {"direct"}
    assert next(row for row in state["coverage"] if row["group"] == "runtime-team" and row["tech_id"] == "SW-01")["evidence_status"] == "inference_only"


def test_missing_actor_or_relationship_cannot_become_a_confirmed_evaluation_or_summary():
    def result(payload):
        unnamed = named_statement(payload).model_copy(update={"actor": "", "text": "주체 없는 가짜 평가"})
        unrelated = named_statement(payload).model_copy(update={"actor_relationship": "unspecified",
                                                                 "text": "관계 없는 가짜 평가"})
        return draft([unnamed, unrelated, observation()], summary=[
            Insight(text="주체 없는 가짜 요약", claim_indices=[0]),
            Insight(text="관계 없는 가짜 요약", claim_indices=[1])])

    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(),
                         model=Model(result=result), web=Web(results=True))
    assert state["rejected"] == [0, 1]
    assert state["evidence_status"] == "limited"
    assert state["status"] == "partial"
    for text in ("주체 없는 가짜 평가", "관계 없는 가짜 평가", "주체 없는 가짜 요약", "관계 없는 가짜 요약"):
        assert text not in state["output_md"]
    assert "운영 검토 표식" in state["output_md"]


def test_named_family_statements_remain_limited_instead_of_completing_direct_coverage():
    def result(payload):
        return draft([named_statement(payload, tech_id=tech_id).model_copy(update={"source_scope": "family"})
                      for tech_id in ("SW-01", "HW-01")])

    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(),
                         model=Model(result=result), web=Web(results=True))
    assert state["errors"] == []
    assert state["rejected"] == []
    assert state["execution_status"] == "completed"
    assert state["evidence_status"] == "limited"
    assert state["status"] == "partial"
    own = [row for row in state["coverage"] if row["group"] == "site-ops"]
    assert {row["evidence_status"] for row in own} == {"family"}
    assert "관련 기술 계열" in state["output_md"]


def test_repeating_one_technical_observation_across_roles_does_not_create_more_findings():
    claims = [observation(), observation(role="runtime-team")]
    model = Model(result=draft(claims, summary=[Insight(text="중복 관찰에서 만든 요약", claim_indices=[1])]))
    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(), model=model, web=Web())
    assert state["rejected"] == [1]
    assert "중복 관찰에서 만든 요약" not in state["output_md"]
    runtime = [row for row in state["coverage"] if row["group"] == "runtime-team"]
    assert all(row["claim_indices"] == [] and row["evidence_status"] == "unavailable" for row in runtime)


def test_multiple_domains_and_repair_share_the_existing_budget():
    roles = selected_roles() + selected_roles("D-LAB")
    queries = [question(domain["id"], tech_id, role.id)
               for domain in DOMAINS for tech_id in ("SW-01", "HW-01")
               for role in selected_roles(domain["id"])]
    repairs = [question(domain["id"], tech_id, "external-reviewer", "repair")
               for domain in DOMAINS for tech_id in ("SW-01", "HW-01")]
    model, web = Model(roles, queries, repair_questions=repairs), Web(results=True)
    state = run_detailed(input_markdown(), config=config(search_limit=6, fetch_limit=10, repair_limit=1),
                         model=model, web=web)
    assert state["budget"].used == {"search": 6, "fetch": 1, "llm": 5}
    assert len(web.search_calls) == 6
    assert len(web.fetch_calls) == 1
    assert len(model.calls) == 5
    assert state["round"] == 1
    assert len(state["coverage"]) == 2 * 2 * 3
    for _, _, payload in model.calls:
        assert payload["max_claims"] == 24
        assert payload["analysis_context"]["domains"] == DOMAINS
    assert set(map(tuple, state["searched_pairs"])) == {
        (domain["id"], tech_id) for domain in DOMAINS for tech_id in ("SW-01", "HW-01")}


def test_repeated_queries_do_not_consume_slots_before_later_distinct_queries():
    initial_sw, initial_hw = question(), question(tech_id="HW-01")
    queries = [initial_sw, initial_hw,
               initial_sw.model_copy(update={"reason": "같은 검색을 다시 제안"}),
               question(role="runtime-team"), question(role="external-reviewer")]
    repairs = [initial_sw, initial_hw,
               question(role="runtime-team", suffix="repair"),
               question(tech_id="HW-01", role="external-reviewer", suffix="repair")]
    web = Web()
    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(search_limit=6, repair_limit=1),
                         model=Model(questions=queries, repair_questions=repairs), web=web)
    assert len(web.search_calls) == len(set(web.search_calls)) == 6
    assert web.search_calls[-2:] == [item.query for item in repairs[-2:]]
    assert state["budget"].used == {"search": 6, "fetch": 0, "llm": 5}
    assert state["round"] == 1
