"""Domain context comes from upstream and stays separated through the real graph."""

from copy import deepcopy

import pytest

from stakeholder_agent.config import AgentConfig
from stakeholder_agent.legacy import run_detailed, run_stakeholder
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

DOMAINS = [
    {"id": "D-MOBILE", "name": "휴대형 기기", "scenario": "인터넷 없이 현장 문서를 요약하는 상황"},
    {"id": "D-LAB", "name": "연구실 서버", "scenario": "공유 연구 서버에서 장문 실험을 처리하는 상황"},
]
REQUEST = "현장 기기와 연구실 서버에 같은 기술을 적용할 때 누가 이득과 부담을 갖는지 비교해 줘."
OBJECTIVE = "구매 추천 없이 이해관계자별 편익과 부담 조건을 비교한다."
CONSTRAINTS = "실제 도입 여부를 추정하지 않는다. 원문 근거를 유지한다."
SW_QUOTE = "The RDKV paper describes a software method for reducing KV cache memory."
HW_QUOTE = "The Photonic-CXL paper proposes a shared memory appliance for inference."
WEB_QUOTE = "RDKV and Photonic-CXL implementation details are evaluated with documented methods and results."
WEB_URL = "https://example.org/rdkv-photonic-cxl-study"


def input_markdown(domains=None, search_limit=6):
    domains = DOMAINS if domains is None else domains
    rows = "\n".join(f"| {d['id']} | {d['name']} | {d['scenario']} |" for d in domains)
    return f"""# 이해관계자 에이전트 입력

## 실행 정보

| 항목 | 값 |
| --- | --- |
| schema_version | 0.2 |
| run_id | domain-test |
| 조사 기준일 | 2026-09-21 |
| 언어 | 한국어 |
| 남은 검색 요청 한도 | {search_limit} |
| 남은 원문 조회 한도 | 10 |
| 남은 LLM 시도 한도 | 5 |

## 분석 요청

### 요청 맥락

- 최초 사용자 요청: {REQUEST}
- 분석 목적: {OBJECTIVE}
- 제약 조건: {CONSTRAINTS}

### 대상 도메인

| 도메인 ID | 도메인 | 사용 상황 |
| --- | --- | --- |
{rows}

## 기술 목록

| 기술 ID | 이름 | 구분 | 논문·버전·URL |
| --- | --- | --- | --- |
| SW-01 | RDKV | SW | RDKV v1, https://arxiv.org/abs/2605.08317v1 |
| HW-01 | Photonic-CXL | HW | Photonic-CXL v1, https://arxiv.org/abs/2607.27187v1 |

## 논문 기반 기술 요약

### SW-01

- 논문은 KV cache 압축 방법을 설명한다. [E-SW-001](#e-sw-001)

### HW-01

- 논문은 공유 메모리 확장 방법을 설명한다. [E-HW-001](#e-hw-001)

## 근거 목록

### E-SW-001

- 문서 ID: SW-01
- 원문: https://arxiv.org/abs/2605.08317v1
- 위치: Abstract
- 저자: Software researchers
- 발행일·버전: 2026-05-08 / v1
- 발췌: {SW_QUOTE}

### E-HW-001

- 문서 ID: HW-01
- 원문: https://arxiv.org/abs/2607.27187v1
- 위치: Abstract
- 저자: Hardware researchers
- 발행일·버전: 2026-07-29 / v1
- 발췌: {HW_QUOTE}

## 추가 요청 및 정보 공백

- 위 대상 도메인은 앞단에서 확정하여 전달한 목록이다.
"""


def claim(domain_id, tech_id="SW-01", text="근거가 있는 도메인별 관찰"):
    is_sw = tech_id == "SW-01"
    return Claim(domain_id=domain_id, tech_id=tech_id, group="operator", aspect="benefit",
                 kind="paper_report", text=text, condition="해당 입력 도메인에 대한 관찰",
                 source_scope="direct", supports=[Support(evidence_id="E-SW-001" if is_sw else "E-HW-001",
                                                           quote=SW_QUOTE if is_sw else HW_QUOTE)])


def assessment(claims=None, summary=None):
    return Assessment(claims=claims or [], summary=summary or [], implications=[], limitations=[], follow_up=[])


def question(domain_id, tech_id="SW-01", query="RDKV domain-specific evidence"):
    return SearchQuestion(domain_id=domain_id, tech_id=tech_id, group="operator", query=query,
                          reason="지정한 도메인의 주체별 근거를 확인한다")


def config(**overrides):
    return AgentConfig(**{"search_limit": 4, "fetch_limit": 4, "llm_limit": 5,
                          "repair_limit": 0, **overrides})


class Model:
    def __init__(self, draft=None, questions=None):
        self.draft = draft or assessment()
        self.plan = ResearchPlan(questions=questions or [])
        self.calls = []

    def generate(self, schema, system, payload):
        self.calls.append((schema.__name__, system, deepcopy(payload)))
        return {ResearchPlan: self.plan, Assessment: self.draft,
                Review: Review(rejected_claim_indices=[], issues=[], queries=[])}[schema].model_copy(deep=True)


class Web:
    def __init__(self, results=False):
        self.results = results
        self.search_calls = []
        self.fetch_calls = []

    def search(self, query, max_results=3):
        self.search_calls.append(query)
        return ([SearchHit(url=WEB_URL, title="RDKV and Photonic-CXL research")]
                if self.results else [])

    def fetch(self, url):
        self.fetch_calls.append(url)
        return SourcePage(url=url, title="RDKV and Photonic-CXL research", text=WEB_QUOTE,
                          publisher="Independent test research group", published_at="2026-09-01")


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Domain tests must not make real HTTP requests")

    monkeypatch.setattr("httpx.Client.request", blocked)
    monkeypatch.setattr("httpx.Client.stream", blocked)


def test_upstream_context_is_passed_unchanged_to_planning_analysis_and_review():
    model = Model(assessment([claim("D-MOBILE"), claim("D-LAB", "HW-01")]))
    state = run_detailed(input_markdown(), config=config(), model=model, web=Web())
    assert [name for name, _, _ in model.calls] == ["ResearchPlan", "Assessment", "Review"]
    for _, _, payload in model.calls:
        context = payload["analysis_context"]
        assert context["original_request"] == REQUEST
        assert context["objective"] == OBJECTIVE
        assert context["constraints"] == CONSTRAINTS
        assert context["domains"] == DOMAINS
        assert context["origin"] != "legacy_default"
    assert [domain.id for domain in state["parsed"].analysis_context.domains] == ["D-MOBILE", "D-LAB"]


def test_multi_domain_claims_stay_separate_and_ambiguous_or_unknown_ids_are_rejected():
    draft = assessment([
        claim("", text="도메인미지정주장을출력하면안됨"),
        claim("D-INVENTED", text="임의도메인주장을출력하면안됨"),
        claim("D-MOBILE", text="휴대형기기전용관찰표식"),
        claim("D-LAB", "HW-01", text="연구실서버전용관찰표식"),
    ], summary=[Insight(text="미지정주장요약", claim_indices=[0]),
                Insight(text="임의도메인요약", claim_indices=[1])])
    questions = [question("", query="DO NOT RUN MISSING DOMAIN"),
                 question("D-INVENTED", query="DO NOT RUN UNKNOWN DOMAIN")]
    model, web = Model(draft, questions), Web()
    state = run_detailed(input_markdown(), config=config(), model=model, web=web)
    assert {0, 1} <= set(state["rejected"])
    assert not {2, 3} & set(state["rejected"])
    for text in ["도메인미지정주장을출력하면안됨", "임의도메인주장을출력하면안됨", "미지정주장요약", "임의도메인요약"]:
        assert text not in state["output_md"]
    for text in ["휴대형기기전용관찰표식", "연구실서버전용관찰표식", "D-MOBILE", "D-LAB", "휴대형 기기", "연구실 서버"]:
        assert text in state["output_md"]
    assert all("DO NOT RUN" not in query for query in web.search_calls)
    assert all(q.domain_id in {"D-MOBILE", "D-LAB"} for q in state["plan"].questions)
    assert state["draft"].claims[2].domain_id == "D-MOBILE"
    assert state["draft"].claims[3].domain_id == "D-LAB"
    comparison = state["output_md"].split("## 이해관계자별 SW/HW 비교", 1)[1]
    comparison = comparison.split("## 이해 상충 및 관점 간 연결", 1)[0]
    mobile = comparison.split("### D-MOBILE · 휴대형 기기", 1)[1].split("### D-LAB", 1)[0]
    laboratory = comparison.split("### D-LAB · 연구실 서버", 1)[1]
    assert "휴대형기기전용관찰표식" in mobile
    assert "연구실서버전용관찰표식" not in mobile
    assert "연구실서버전용관찰표식" in laboratory
    assert "휴대형기기전용관찰표식" not in laboratory


def test_single_domain_backfills_missing_ids_without_extracting_extra_domains_from_request():
    draft = assessment([claim("", text="단일도메인에서유지할관찰")])
    model = Model(draft, [question("", query="RDKV preserve single-domain question")])
    state = run_detailed(input_markdown(DOMAINS[:1]), config=config(), model=model, web=Web())
    assert [domain.id for domain in state["parsed"].analysis_context.domains] == ["D-MOBILE"]
    assert state["draft"].claims[0].domain_id == "D-MOBILE"
    assert 0 not in state["rejected"]
    assert "단일도메인에서유지할관찰" in state["output_md"]
    assert all(q.domain_id == "D-MOBILE" for q in state["plan"].questions)
    assert any(q.query == "RDKV preserve single-domain question" for q in state["plan"].questions)


def test_fallback_searches_include_each_domains_name_and_both_technologies():
    web = Web()
    state = run_detailed(input_markdown(), config=config(), model=Model(), web=web)
    assert len(web.search_calls) == 4
    for domain in DOMAINS:
        for technology in ["RDKV", "Photonic-CXL"]:
            assert any(domain["name"] in query and technology in query
                       for query in web.search_calls)
    assert set(map(tuple, state["searched_pairs"])) == {
        (domain["id"], technology) for domain in DOMAINS for technology in ["SW-01", "HW-01"]
    }


def test_all_domains_share_the_existing_call_budget_and_unsearched_pairs_remain_visible():
    questions = [question(domain["id"], tech_id, f"{tech_id} {domain['id']} evidence {index}")
                 for domain in DOMAINS for tech_id in ["SW-01", "HW-01"] for index in range(5)]
    model, web = Model(questions=questions), Web(results=True)
    state = run_detailed(input_markdown(search_limit=2),
                         config=config(search_limit=6, fetch_limit=1, llm_limit=3), model=model, web=web)
    assert len(web.search_calls) <= 2
    assert len(web.fetch_calls) <= 1
    assert len(model.calls) <= 3
    assert state["budget"].used == {"search": len(web.search_calls), "fetch": len(web.fetch_calls),
                                     "llm": len(model.calls)}
    assert state["budget"].limits == {"search": 2, "fetch": 1, "llm": 3}
    attempted = set(map(tuple, state["searched_pairs"]))
    expected = {(d["id"], t) for d in DOMAINS for t in ["SW-01", "HW-01"]}
    for domain_id, tech_id in expected - attempted:
        assert any(domain_id in gap and tech_id in gap for gap in state["gaps"])
    assert state["status"] == "partial"


@pytest.mark.parametrize(("domains", "expected_status"), [(DOMAINS[:1], "completed"), (DOMAINS, "partial")])
def test_coverage_of_one_domain_cannot_complete_a_request_for_two(domains, expected_status):
    class FirstDomainCoverageModel(Model):
        def __init__(self):
            super().__init__()
            self.plan.stakeholders = [StakeholderTarget(
                id="operator", domain_id=domain["id"], name="해당 환경 운영자",
                reason="입력 도메인에서 기술을 운용할 주체") for domain in domains]

        def generate(self, schema, system, payload):
            if schema is Assessment:
                domain_id = payload["analysis_context"]["domains"][0]["id"]
                record = next(item for item in payload["evidence"] if item["url"] == WEB_URL)
                claims = [Claim(domain_id=domain_id, tech_id=tech_id, group="operator", aspect="evaluation",
                                kind="statement", text=f"검토된관찰 {domain_id} {tech_id}",
                                actor="Independent test research group", actor_relationship="observer",
                                condition="가짜 공급자 대신 통제된 테스트 자료", source_scope="direct",
                                supports=[Support(evidence_id=record["id"], quote=WEB_QUOTE)])
                          for tech_id in ["SW-01", "HW-01"]]
                self.draft = assessment(claims)
                self.draft.source_reviews = [WebSourceReview(
                    evidence_id=record["id"], document_type="research", perspective="independent_author",
                    relevance="direct", evidence_basis="methods_and_results", decision="use",
                    reasons=["독립적으로 통제한 테스트 자료"], limitations=[], basis_quotes=["Q001"],
                )]
            return super().generate(schema, system, payload)

    state = run_detailed(input_markdown(domains), config=config(), model=FirstDomainCoverageModel(),
                         web=Web(results=True))
    assert state["errors"] == []
    assert len(state["draft"].claims) == 2
    assert state["rejected"] == []
    assert state["execution_status"] == "completed"
    assert state["evidence_status"] == ("direct_available" if len(domains) == 1 else "limited")
    assert state["status"] == expected_status


def test_non_cloud_request_does_not_leak_the_previous_hardcoded_cloud_scope():
    model = Model(assessment([claim("D-MOBILE")]))
    output = run_stakeholder(input_markdown(DOMAINS[:1]), config=config(), model=model, web=Web())
    assert isinstance(output, str)
    assert "휴대형 기기" in output
    assert "인터넷 없이 현장 문서를 요약하는 상황" in output
    assert "cloud_datacenter" not in output
    assert "클라우드 데이터센터" not in output
    assert "클라우드·데이터센터 운영자" not in output


def test_offline_demo_handles_all_provided_domains_without_real_provider_calls():
    state = run_detailed(input_markdown(), config=config(), mode="fixture")
    assert state["errors"] == []
    assert "DEMO" in state["output_md"]
    valid_claims = [claim for index, claim in enumerate(state["draft"].claims) if index not in state["rejected"]]
    assert {claim.domain_id for claim in valid_claims} == {domain["id"] for domain in DOMAINS}
    for domain in DOMAINS:
        assert domain["name"] in state["output_md"]
