from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from stakeholder_agent.contracts import InputError, parse_input, render_output
from stakeholder_agent.models import (
    OUTPUT_SECTIONS,
    Assessment,
    Budget,
    Claim,
    Evidence,
    Insight,
    ResearchPlan,
    Review,
    StakeholderTarget,
    Support,
)

SAMPLE = Path(__file__).resolve().parent / "fixtures/legacy-input.md"


@pytest.fixture
def input_md():
    return SAMPLE.read_text(encoding="utf-8")


def claim(evidence_id="E-SW-001", **kwargs):
    fields = {"tech_id": "SW-01", "group": "operator", "aspect": "benefit", "kind": "inference",
              "text": "서비스 편익을 검토할 수 있다.", "condition": "워크로드별 검증이 필요하다.",
              "source_scope": "direct", "supports": [Support(evidence_id=evidence_id, quote="제거와 양자화")]}
    fields.update(kwargs)
    return Claim(**fields)


def assessment(claims, summary=None, implications=None):
    return Assessment(claims=claims, summary=summary or [], implications=implications or [],
                      limitations=[], follow_up=[])


def section_names(markdown):
    tokens = MarkdownIt("commonmark").parse(markdown)
    return [tokens[i + 1].content for i, token in enumerate(tokens)
            if token.type == "heading_open" and token.tag == "h2"]


def test_parse_sample_preserves_versions_provenance_and_limits(input_md):
    parsed = parse_input(input_md)
    assert parsed.run_id == "demo"
    assert parsed.as_of == "2026-09-21"
    assert parsed.requested_limits == {"search": 6, "fetch": 10, "llm": 5}
    assert parsed.technologies[0].url == "https://arxiv.org/abs/2605.08317v1"
    assert "arXiv:2607.27187v1" in parsed.technologies[1].paper
    assert parsed.evidence["E-SW-001"].tech_ids == ["SW-01"]
    assert parsed.evidence["E-HW-001"].location == "Abstract"
    assert parsed.evidence["E-SW-001"].published_at == "2026-05-08 / v1"
    assert parsed.evidence["E-SW-001"].retrieved_at == "미표기"
    assert "Junkai Zhang" in parsed.evidence["E-SW-001"].publisher
    assert "기업의 지지" in parsed.metadata["추가 요청 및 정보 공백"]
    assert not parsed.gaps


@pytest.mark.parametrize("value", ["-1", "1.5", "+2", "one", "", "1_000", "１２"])
def test_malformed_budget_is_rejected(input_md, value):
    with pytest.raises(InputError, match="정수"):
        parse_input(input_md.replace("| 남은 검색 요청 한도 | 6 |", f"| 남은 검색 요청 한도 | {value} |"))


def test_zero_and_omitted_budgets_are_distinct(input_md):
    parsed = parse_input(input_md.replace("| 남은 검색 요청 한도 | 6 |", "| 남은 검색 요청 한도 | 0 |")
                         .replace("| 남은 LLM 시도 한도 | 5 |\n", ""))
    assert parsed.requested_limits == {"search": 0, "fetch": 10}


def test_huge_budget_still_raises_contract_error(input_md):
    with pytest.raises(InputError, match="정수"):
        parse_input(input_md.replace("| 남은 검색 요청 한도 | 6 |", "| 남은 검색 요청 한도 | " + "9" * 5000 + " |"))


@pytest.mark.parametrize("replacement", ["mobile", "on_device", "cloud_datacenter or mobile"])
def test_invalid_scope_rejected(input_md, replacement):
    with pytest.raises(InputError, match="cloud_datacenter"):
        parse_input(input_md.replace("| domain | cloud_datacenter |", f"| domain | {replacement} |"))


@pytest.mark.parametrize("value", ["2026-02-30", "2026-2-3", "today", ""])
def test_invalid_or_missing_as_of_date_not_invented(input_md, value):
    with pytest.raises(InputError, match="날짜"):
        parse_input(input_md.replace("| 조사 기준일 | 2026-09-21 |", f"| 조사 기준일 | {value} |"))


def test_missing_run_id_generated_and_marked(input_md):
    parsed = parse_input(input_md.replace("| run_id | demo |\n", ""))
    assert parsed.run_id.startswith("auto-")
    assert parsed.metadata["run_id 생성 방식"] == "입력 누락으로 자동 생성"
    assert "입력 누락으로 자동 생성" in render_output({"parsed": parsed, "status": "partial"})


@pytest.mark.parametrize("value", ["a/b", "hello_world", "한글", "x](https://evil.test)"])
def test_unsafe_run_ids_rejected(input_md, value):
    with pytest.raises(InputError, match="run_id"):
        parse_input(input_md.replace("| run_id | demo |", f"| run_id | {value} |"))


def test_duplicate_evidence_and_anchor_collision_rejected(input_md):
    duplicate = "\n### e-sw-001\n\n- 문서 ID: SW-01\n"
    with pytest.raises(InputError, match="충돌"):
        parse_input(input_md.replace("## 추가 요청 및 정보 공백", duplicate + "\n## 추가 요청 및 정보 공백"))
    with pytest.raises(InputError, match="근거 ID"):
        parse_input(input_md.replace("### E-SW-001", "### bad/id"))
    with pytest.raises(InputError, match="출력 주장"):
        parse_input(input_md.replace("### E-SW-001", "### STK-demo-C001"))


def test_unknown_technology_mapping_rejected(input_md):
    with pytest.raises(InputError, match="기술 목록에 없습니다"):
        parse_input(input_md.replace("- 문서 ID: SW-01", "- 문서 ID: UNKNOWN"))


def test_requires_exactly_one_sw_and_one_hw(input_md):
    with pytest.raises(InputError, match="SW 한 개와 HW 한 개"):
        parse_input(input_md.replace("| Photonic-CXL | HW |", "| Photonic-CXL | SW |"))


def test_missing_source_content_keeps_identified_technologies_as_partial(input_md):
    incomplete = input_md.replace("- 위치: Abstract", "- 위치:")
    parsed = parse_input(incomplete)
    assert len(parsed.technologies) == 2
    assert parsed.evidence == {}
    assert any("원문 위치" in gap for gap in parsed.gaps)


def test_missing_evidence_entries_is_a_gap_not_input_failure(input_md):
    start = input_md.index("## 근거 목록")
    end = input_md.index("## 추가 요청 및 정보 공백")
    parsed = parse_input(input_md[:start] + "## 근거 목록\n\n" + input_md[end:])
    assert not parsed.evidence
    assert len(parsed.gaps) == 2


def test_code_blocks_and_quoted_headings_cannot_override_contract(input_md):
    fake = "\n```markdown\n## 실행 정보\n\n| 항목 | 값 |\n| --- | --- |\n| domain | mobile |\n```\n"
    fake += "\n> ## 실행 정보\n>\n> | 항목 | 값 |\n> | --- | --- |\n> | domain | mobile |\n"
    assert parse_input(fake + input_md).metadata["domain"] == "cloud_datacenter"
    fenced_evidence = "\n~~~md\n### FAKE-ID\n\n- 문서 ID: SW-01\n~~~\n"
    parsed = parse_input(input_md.replace("## 추가 요청 및 정보 공백", fenced_evidence + "\n## 추가 요청 및 정보 공백"))
    assert set(parsed.evidence) == {"E-SW-001", "E-HW-001"}


def test_fixed_output_sections_for_failed_input():
    output = render_output({"parsed": None, "status": "failed", "errors": ["입력 오류"]})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "| status | failed |" in output
    assert "입력 오류" in output
    assert "실제 출력 주장에 인용된 근거가 없습니다" in output


def test_only_cited_references_and_original_claim_indices_survive_rejection(input_md):
    parsed = parse_input(input_md)
    draft = assessment(
        [claim(text="삭제할 주장"), claim(text="유지할 주장", tech_id="HW-01", evidence_id="E-HW-001")],
        summary=[Insight(text="삭제할 요약", claim_indices=[0]), Insight(text="유지할 요약", claim_indices=[1])],
        implications=[Insight(text="두 주장에 의존하는 시사점", claim_indices=[0, 1])],
    )
    output = render_output({"parsed": parsed, "evidence": parsed.evidence, "draft": draft,
                            "rejected": [0], "status": "partial"})
    assert "삭제할 주장" not in output
    assert "삭제할 요약" not in output
    assert "두 주장에 의존하는 시사점" not in output
    assert "유지할 요약" in output
    assert "### STK-demo-C002" in output
    assert "### STK-demo-C001" not in output
    assert "### E-HW-001" in output
    assert "### E-SW-001" not in output
    assert "[STK-demo-C002](#stk-demo-c002)" in output
    assert "[E-HW-001](#e-hw-001)" in output
    assert section_names(output) == OUTPUT_SECTIONS


@pytest.mark.parametrize("filtered_summary", [False, True])
def test_summary_fallback_uses_only_first_surviving_observation_per_technology(input_md, filtered_summary):
    parsed = parse_input(input_md)
    observations = [
        claim(text="규칙검사에서거절된SW관찰"),
        claim(text="모델검토에서거절된HW관찰", tech_id="HW-01", evidence_id="E-HW-001"),
        claim(text="미확인SW관찰", kind="unknown", supports=[]),
        claim(text="미확인HW관찰", tech_id="HW-01", kind="unknown", supports=[]),
        claim(text="검증된SW첫관찰"),
        claim(text="검증된SW추가관찰"),
        claim(text="검증된HW첫관찰", tech_id="HW-01", evidence_id="E-HW-001"),
        claim(text="검증된HW추가관찰", tech_id="HW-01", evidence_id="E-HW-001"),
    ]
    summaries = ([Insight(text="거절주장과섞인요약", claim_indices=[0, 4]),
                  Insight(text="리뷰거절주장요약", claim_indices=[1]),
                  Insight(text="미확인주장의요약", claim_indices=[2, 3])] if filtered_summary else [])
    draft = assessment(observations, summary=summaries)
    output = render_output({"parsed": parsed, "evidence": parsed.evidence, "draft": draft,
                            "rejected": [0], "status": "partial",
                            "review": Review(rejected_claim_indices=[1], issues=[], queries=[])})
    summary = output.split("## SUMMARY 기여\n", 1)[1].split("## 평가 기준 및 방법", 1)[0]
    bullets = [line for line in summary.splitlines() if line.startswith("- ")]
    assert len(bullets) == 2
    assert "RDKV — 분석적 추론 · 해당 기술 직접: 검증된SW첫관찰" in bullets[0]
    assert "Photonic-CXL — 분석적 추론 · 해당 기술 직접: 검증된HW첫관찰" in bullets[1].replace("\\", "")
    assert "[STK-demo-C005](#stk-demo-c005)" in bullets[0]
    assert "[STK-demo-C007](#stk-demo-c007)" in bullets[1]
    for item in [*observations[:4], observations[5], observations[7]]:
        assert item.text not in summary
    assert all(item.text not in summary for item in summaries)


def test_summary_fallback_cannot_revive_rejected_or_unknown_claims_without_valid_ones(input_md):
    parsed = parse_input(input_md)
    draft = assessment([claim(text="거절된유일한SW관찰"),
                        claim(text="미확인인유일한HW관찰", tech_id="HW-01", kind="unknown", supports=[])])
    output = render_output({"parsed": parsed, "draft": draft, "rejected": [0], "status": "partial"})
    summary = output.split("## SUMMARY 기여\n", 1)[1].split("## 평가 기준 및 방법", 1)[0]
    assert "검증을 통과한 요약 근거가 부족합니다" in summary
    assert "거절된유일한SW관찰" not in summary
    assert "미확인인유일한HW관찰" not in summary
    assert "STK-demo-C" not in summary


def test_uncited_and_broken_source_claims_and_insights_are_omitted(input_md):
    parsed = parse_input(input_md)
    draft = assessment([claim(supports=[]), claim(evidence_id="DOES-NOT-EXIST")],
                       summary=[Insight(text="근거 없는 요약", claim_indices=[0]),
                                Insight(text="연결 없는 요약", claim_indices=[])])
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert "근거 없는 요약" not in output
    assert "연결 없는 요약" not in output
    assert "DOES-NOT-EXIST" not in output
    assert "### E-SW-001" not in output


def test_unselected_groups_are_not_invented_and_remaining_budgets_are_in_execution_appendix(input_md):
    parsed = parse_input(input_md)
    budget = Budget({"search": 6, "fetch": 10, "llm": 5})
    budget.take("search")
    budget.take("llm")
    output = render_output({"parsed": parsed, "budget": budget, "status": "partial", "mode": "fixture"})
    assert "선정된 역할군이 없습니다" in output
    assert "편익: 미확인" not in output
    assert "부담·위험: 미확인" not in output
    assert "도입 조건: 미확인" not in output
    assert "실제 반응: 미확인" not in output
    assert "| 남은 검색 요청 한도 | 5 |" in output
    assert "| 남은 원문 조회 한도 | 10 |" in output
    assert "| 남은 LLM 시도 한도 | 4 |" in output
    assert "| schema_version | 0.1 |" in output
    assert "| domain | cloud_datacenter |" in output
    assert "DEMO" in output
    assert "### 실행 기록" in output
    assert "남은 검색 요청 한도" not in output.split("## SUMMARY 기여", 1)[0]


def test_generated_markdown_cannot_inject_headings_links_html_or_extra_table_cells(input_md):
    parsed = parse_input(input_md)
    dangerous = "x | y\n\n## HACKED\n[click](javascript:alert(1)) <script>evil()</script>"
    draft = assessment([claim(text=dangerous, condition=dangerous, kind="statement", actor=dangerous)],
                       summary=[Insight(text=dangerous, claim_indices=[0])])
    draft.limitations = [dangerous]
    parsed.evidence["E-SW-001"].title = dangerous
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "<script>" not in output
    assert "[click](javascript:" not in output
    assert r"x \| y" in output
    table_tokens = MarkdownIt("commonmark").enable("table").parse(output)
    comparison_cells = []
    active_row = None
    for token in table_tokens:
        if token.type == "tr_open":
            active_row = 0
        elif token.type in {"td_open", "th_open"}:
            active_row += 1
        elif token.type == "tr_close":
            comparison_cells.append(active_row)
    assert comparison_cells[-2:] == [6, 6]


def web_evidence(identifier="STK-demo-E003", **kwargs):
    fields = {
        "id": identifier, "tech_ids": ["SW-01"], "title": "공급자 기술 발표", "url": "https://vendor.example/post",
        "location": "Overview", "excerpt": "Our device improves memory capacity in these simulated workloads.",
        "source_type": "web", "publisher": "Example Vendor", "author": "Example Author",
        "published_at": "2026-09-01", "retrieved_at": "2026-09-21",
        "metadata_provenance": {"author": "JSON-LD author.name", "publisher": "og:site_name"},
        "search_queries": ["RDKV operator deployment"],
        "audit": {"decision": "limited", "document_type": "supplier_publication",
                  "perspective": "interested_party", "relevance": "family",
                  "evidence_basis": "attributed_statement", "reasons": ["공급자가 자신의 기술을 설명함"],
                  "limitations": ["고객의 독립 운영 결과가 아님"], "verified_quotes": ["Our device improves memory capacity"],
                  "checks": {"날짜": "기준일 이전 자료"}},
    }
    fields.update(kwargs)
    return Evidence(**fields)


def test_all_web_sources_get_audit_cards_but_only_cited_sources_enter_reference(input_md):
    parsed = parse_input(input_md)
    used = web_evidence(content_sha256="a" * 64)
    unused = web_evidence("STK-demo-E004", url="https://report.example/article", audit={"decision": "exclude"})
    sources = {**parsed.evidence, used.id: used, unused.id: unused}
    draft = assessment([claim(evidence_id=used.id)])
    output = render_output({"parsed": parsed, "evidence": sources, "draft": draft, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "### 웹 출처 검토" in output
    assert "#### audit-STK-demo-E003" in output
    assert "#### audit-STK-demo-E004" in output
    assert "미사용 — REFERENCE에 포함하지 않음" in output
    assert "분석 근거에서 제외" in output
    assert "당사자 주장으로만 사용" in output
    assert "[검토 상세](#audit-stk-demo-e003)" in output
    assert "명시된 주체의 발언 범위" in output
    assert "JSON-LD author.name" in output
    assert r"og:site\_name" in output
    assert "RDKV operator deployment" in output
    assert "vendor.example" in output
    assert "Example Author" in output
    assert "a" * 64 in output
    references = output.split("## REFERENCE\n", 1)[1]
    assert "### STK-demo-E003" in references
    assert "### STK-demo-E004" not in references
    assert "[판정·허용 범위·수집 경로](#audit-stk-demo-e003)" in references


def test_unaudited_web_source_is_explicitly_on_hold_without_invented_checks(input_md):
    parsed = parse_input(input_md)
    source = web_evidence(audit={}, metadata_provenance={}, author="미표기", search_queries=[])
    output = render_output({"parsed": parsed, "evidence": {**parsed.evidence, source.id: source}, "status": "partial"})
    assert "평가 미완료·사용 보류" in output
    assert "미표기 — 필드 추출 경로를 확인할 수 없음" in output
    assert "확인 가능한 구절 없음" in output
    assert "자료 유형 미확인" in output
    assert "작성 관점 미확인" in output
    assert "독립 작성자 표시는 독립 교차검증 완료를 뜻하지 않으며" in output
    assert "여러 기사도 같은 원자료를 재전달할 수 있습니다" in output
    assert "신뢰도" not in output


def test_upstream_papers_are_never_given_web_source_audits(input_md):
    parsed = parse_input(input_md)
    parsed.evidence["E-SW-001"].audit = {"decision": "exclude", "reasons": ["논문에대한검토처럼표시하면안됨"]}
    output = render_output({"parsed": parsed, "draft": assessment([claim()]), "status": "partial"})
    assert "### 웹 출처 검토" not in output
    assert "audit-E-SW-001" not in output
    assert "논문에대한검토처럼표시하면안됨" not in output
    assert "### E-SW-001" in output


def test_web_snippet_prefers_verified_support_and_is_short_printed_once(input_md):
    parsed = parse_input(input_md)
    support_quote = " ".join(f"word{i:02d}" for i in range(45))
    source = web_evidence(excerpt="AUDIT QUOTE. " + support_quote)
    source.audit["verified_quotes"] = ["AUDIT QUOTE"]
    draft = assessment([claim(evidence_id=source.id, supports=[Support(evidence_id=source.id, quote=support_quote)])])
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "draft": draft, "status": "partial"})
    snippet_lines = [line for line in output.splitlines() if line.startswith("- 원문에서 확인한 검토 구절: ")]
    assert len(snippet_lines) == 1
    snippet = snippet_lines[0].split(": ", 1)[1]
    assert len(snippet) <= 140
    assert len(snippet.split()) <= 25
    assert snippet.startswith("word00 word01")
    assert snippet in source.excerpt
    assert "AUDIT QUOTE" not in output
    assert output.count(snippet) == 1


def test_unverified_quote_is_not_printed_and_verified_audit_quote_can_fallback(input_md):
    parsed = parse_input(input_md)
    source = web_evidence()
    draft = assessment([claim(evidence_id=source.id, supports=[Support(evidence_id=source.id, quote="Invented quote")])])
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "draft": draft, "status": "partial"})
    assert "Invented quote" not in output
    assert output.count("Our device improves memory capacity") == 1
    source.audit["verified_quotes"] = ["Another invented quote"]
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "draft": draft, "status": "partial"})
    assert "Another invented quote" not in output
    assert "확인 가능한 구절 없음" in output


def test_navigation_quote_falls_through_to_substantive_verified_audit_basis(input_md):
    parsed = parse_input(input_md)
    navigation = "[IR](https://vendor.example/" + "long-path/" * 40 + ")"
    basis = "The vendor reports results from simulation and provides no customer deployment measurements."
    source = web_evidence(excerpt=navigation + "\n" + basis)
    source.audit["verified_quotes"] = [navigation, basis]
    draft = assessment([claim(evidence_id=source.id, supports=[Support(evidence_id=source.id, quote=navigation)])])
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "draft": draft, "status": "partial"})
    snippets = [line.split(": ", 1)[1] for line in output.splitlines()
                if line.startswith("- 원문에서 확인한 검토 구절: ")]
    assert snippets == [basis]
    assert len(snippets[0]) <= 140
    assert len(snippets[0].split()) <= 25
    assert output.count(basis) == 1
    assert "long-path" not in output


def test_verified_markdown_quote_displays_words_without_link_destinations(input_md):
    parsed = parse_input(input_md)
    raw = "The vendor describes [simulation results](https://vendor.example/" + "long/" * 50 + ") for memory appliances."
    visible = "The vendor describes simulation results for memory appliances."
    source = web_evidence(excerpt=raw)
    source.audit["verified_quotes"] = [raw]
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "status": "partial"})
    assert output.count(visible) == 1
    assert "long/long/" not in output


def test_navigation_only_quote_leaves_explicit_missing_excerpt(input_md):
    parsed = parse_input(input_md)
    raw = "[IR](https://vendor.example/investor-relations/very-long-navigation-address)"
    source = web_evidence(excerpt=raw)
    source.audit["verified_quotes"] = [raw]
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "status": "partial"})
    assert "- 원문에서 확인한 검토 구절: 확인 가능한 구절 없음" in output
    assert "- 원문에서 확인한 검토 구절: IR" not in output


def test_duplicate_url_does_not_repeat_the_literal_excerpt(input_md):
    parsed = parse_input(input_md)
    first, second = web_evidence(), web_evidence("STK-demo-E004")
    output = render_output({"parsed": parsed, "evidence": {first.id: first, second.id: second}, "status": "partial"})
    assert output.count("Our device improves memory capacity") == 1
    assert "동일 원문의 검토 구절은 앞선 카드에 한 번만 표시" in output


def test_audit_metadata_cannot_inject_markdown_or_html(input_md):
    parsed = parse_input(input_md)
    attack = "x | y\n\n## ATTACK\n[click](javascript:evil()) <script>evil</script>"
    source = web_evidence(title=attack, author=attack, publisher=attack, metadata_provenance={attack: attack},
                          search_queries=[attack])
    source.audit.update(reasons=[attack], limitations=[attack], checks={attack: attack})
    output = render_output({"parsed": parsed, "evidence": {source.id: source}, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "<script>" not in output
    assert "[click](javascript:" not in output
    assert r"x \| y" in output


CONTEXT_V2 = """## 분석 요청

### 요청 맥락

- 최초 사용자 요청: SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘.
- 분석 목적: 환경별 도입 편익과 부담을 출처와 함께 설명한다.
- 제약 조건: 미지정

### 대상 도메인

| 도메인 ID | 도메인 | 사용 상황 |
| --- | --- | --- |
| D-CLOUD | 클라우드 데이터센터 | 장문맥 LLM 서비스 운영 |
| D-EDGE | 온디바이스 | 네트워크 없이 로컬 추론 |

"""


def v2_input(input_md, context=CONTEXT_V2):
    return (input_md.replace("| schema_version | 0.1 |", "| schema_version | 0.2 |")
            .replace("| domain | cloud_datacenter |\n", "")
            .replace("## 기술 목록", context + "## 기술 목록"))


def test_v2_parses_original_request_objective_constraints_and_multiple_domains(input_md):
    parsed = parse_input(v2_input(input_md))
    context = parsed.analysis_context
    assert parsed.metadata["schema_version"] == "0.2"
    assert context.origin == "upstream"
    assert context.original_request == "SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘."
    assert context.objective == "환경별 도입 편익과 부담을 출처와 함께 설명한다."
    assert context.constraints == "미지정"
    assert [(domain.id, domain.name, domain.scenario) for domain in context.domains] == [
        ("D-CLOUD", "클라우드 데이터센터", "장문맥 LLM 서비스 운영"),
        ("D-EDGE", "온디바이스", "네트워크 없이 로컬 추론"),
    ]


def test_v2_domain_table_is_authoritative_over_legacy_domain_metadata(input_md):
    text = v2_input(input_md).replace("| 조사 기준일", "| domain | obsolete_domain |\n| 조사 기준일")
    parsed = parse_input(text)
    output = render_output({"parsed": parsed, "status": "partial"})
    assert "| domain | D-CLOUD, D-EDGE |" in output
    assert "obsolete_domain" not in output


def test_v1_legacy_context_preserved_and_explicitly_identified(input_md):
    parsed = parse_input(input_md)
    assert parsed.analysis_context.origin == "legacy_default"
    assert parsed.analysis_context.original_request == ""
    assert parsed.analysis_context.domains[0].name == "클라우드 데이터센터"
    output = render_output({"parsed": parsed, "status": "partial"})
    assert "| schema_version | 0.1 |" in output
    assert "미전달 — 기존 0.1 입력" in output
    assert r"legacy\_default" in output


@pytest.mark.parametrize("old,new", [
    ("## 분석 요청", "## 다른 이름"),
    ("### 요청 맥락", "### 다른 요청"),
    ("### 대상 도메인", "### 다른 도메인"),
    ("- 최초 사용자 요청: SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘.\n", ""),
    ("- 분석 목적: 환경별 도입 편익과 부담을 출처와 함께 설명한다.\n", ""),
    ("- 제약 조건: 미지정\n", ""),
    ("- 최초 사용자 요청: SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘.", "- 최초 사용자 요청:"),
    ("- 분석 목적: 환경별 도입 편익과 부담을 출처와 함께 설명한다.", "- 분석 목적:"),
])
def test_v2_missing_or_empty_required_context_is_rejected(input_md, old, new):
    with pytest.raises(InputError):
        parse_input(v2_input(input_md, CONTEXT_V2.replace(old, new)))


@pytest.mark.parametrize("bad_id", ["D/EDGE", "D_EDGE", "도메인", "[bad](x)", "d-cloud"])
def test_v2_domain_ids_are_safe_unique_and_case_insensitive(input_md, bad_id):
    with pytest.raises(InputError, match="도메인 ID"):
        parse_input(v2_input(input_md, CONTEXT_V2.replace("| D-EDGE |", f"| {bad_id} |")))


def test_v2_needs_at_least_one_named_domain_and_preserves_unspecified_scenario(input_md):
    header_only = CONTEXT_V2.split("| D-CLOUD |", 1)[0]
    with pytest.raises(InputError, match="최소 한 개"):
        parse_input(v2_input(input_md, header_only))
    with pytest.raises(InputError, match="도메인 이름"):
        parse_input(v2_input(input_md, CONTEXT_V2.replace("| D-CLOUD | 클라우드 데이터센터 |", "| D-CLOUD | |")))
    parsed = parse_input(v2_input(input_md, CONTEXT_V2.replace("장문맥 LLM 서비스 운영", "미지정")))
    assert parsed.analysis_context.domains[0].scenario == "미지정"


def test_v2_output_separates_domain_claims_and_labels_insights_and_provenance(input_md):
    parsed = parse_input(v2_input(input_md))
    draft = assessment([
        claim(domain_id="D-CLOUD", text="클라우드만의 검증 조건"),
        claim(domain_id="D-EDGE", text="온디바이스만의 검증 조건"),
        claim(domain_id="", text="범위가없는내용"),
        claim(domain_id="D-MISSING", text="등록안된도메인내용"),
    ], summary=[Insight(text="두 환경의 영향은 다르다.", claim_indices=[0, 1])],
        implications=[Insight(text="온디바이스의 조건을 추가 확인한다.", claim_indices=[1])])
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "| schema_version | 0.2 |" in output
    assert "| 분석 맥락 출처 | upstream |" in output
    assert parsed.analysis_context.original_request in output
    assert parsed.analysis_context.objective in output
    assert "D-CLOUD 클라우드 데이터센터: 장문맥 LLM 서비스 운영" in output
    assert "D-EDGE 온디바이스: 네트워크 없이 로컬 추론" in output
    comparison = output.split("## 이해관계자별 SW/HW 비교\n", 1)[1].split("## 이해 상충", 1)[0]
    cloud = comparison.split("### D-CLOUD · 클라우드 데이터센터", 1)[1].split("### D-EDGE", 1)[0]
    edge = comparison.split("### D-EDGE · 온디바이스", 1)[1]
    assert "클라우드만의 검증 조건" in cloud and "온디바이스만의 검증 조건" not in cloud
    assert "온디바이스만의 검증 조건" in edge and "클라우드만의 검증 조건" not in edge
    assert "범위가없는내용" not in output and "등록안된도메인내용" not in output
    summary = output.split("## SUMMARY 기여", 1)[1].split("## 평가 기준", 1)[0].replace("\\", "")
    assert "범위: D-CLOUD (클라우드 데이터센터), D-EDGE (온디바이스)" in summary
    implication = output.split("## 이해 상충 및 관점 간 연결", 1)[1].split("## 한계", 1)[0].replace("\\", "")
    assert "범위: D-EDGE (온디바이스)" in implication
    assert "D-CLOUD" not in implication
    assert r"- 도메인: D-CLOUD \(클라우드 데이터센터\)" in output
    assert r"- 도메인: D-EDGE \(온디바이스\)" in output


def test_v2_fallback_summary_has_one_observation_per_domain_and_technology(input_md):
    parsed = parse_input(v2_input(input_md))
    draft = assessment([
        claim(domain_id="D-CLOUD", text="CLOUD_SW_FIRST"),
        claim(domain_id="D-CLOUD", text="CLOUD_SW_SECOND"),
        claim(domain_id="D-CLOUD", tech_id="HW-01", evidence_id="E-HW-001", text="CLOUD_HW_FIRST"),
        claim(domain_id="D-EDGE", text="EDGE_SW_FIRST"),
        claim(domain_id="D-EDGE", tech_id="HW-01", evidence_id="E-HW-001", text="EDGE_HW_FIRST"),
    ])
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    summary = output.split("## SUMMARY 기여", 1)[1].split("## 평가 기준", 1)[0].replace("\\", "")
    assert len([line for line in summary.splitlines() if line.startswith("- ")]) == 4
    assert "CLOUD_SW_SECOND" not in summary
    for text in ["CLOUD_SW_FIRST", "CLOUD_HW_FIRST", "EDGE_SW_FIRST", "EDGE_HW_FIRST"]:
        assert text in summary
    assert summary.count("범위: D-CLOUD") == 2
    assert summary.count("범위: D-EDGE") == 2


def test_v2_empty_domain_id_does_not_gain_legacy_fallback_even_with_one_domain(input_md):
    context = CONTEXT_V2.replace("| D-EDGE | 온디바이스 | 네트워크 없이 로컬 추론 |\n", "")
    parsed = parse_input(v2_input(input_md, context))
    draft = assessment([claim(text="누락도메인주장")])
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert "누락도메인주장" not in output


def test_v2_context_domain_labels_and_scenarios_cannot_inject_markdown(input_md):
    parsed = parse_input(v2_input(input_md))
    attack = "x | y\n\n## ATTACK\n[click](javascript:evil()) <script>evil</script>"
    parsed.analysis_context.original_request = attack
    parsed.analysis_context.objective = attack
    parsed.analysis_context.constraints = attack
    parsed.analysis_context.domains[0].name = attack
    parsed.analysis_context.domains[0].scenario = attack
    draft = assessment([claim(domain_id="D-CLOUD")], summary=[Insight(text="조건 검토", claim_indices=[0])])
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "<script>" not in output
    assert "[click](javascript:" not in output
    assert r"x \| y" in output


def test_model_context_limitations_are_preserved_as_separate_unverified_review_notes(input_md):
    parsed = parse_input(v2_input(input_md))
    draft = assessment([claim(domain_id="D-CLOUD")])
    notes = ["원문 요청의 온디바이스 조건과 일부 추가 요청의 클라우드 한정 문구가 충돌할 수 있어 확인이 필요하다.",
             "대상 환경의 구체적인 운영 규모와 품질 허용 조건이 입력되지 않았다."]
    draft.limitations = [*notes, notes[0]]
    source = web_evidence()
    output = render_output({"parsed": parsed, "draft": draft,
                            "evidence": {**parsed.evidence, source.id: source}, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    heading = "### 추가 확인할 분석 한계(모델 제안)"
    assert output.index(heading) < output.index("### 웹 출처 검토")
    review_notes = output.split(heading, 1)[1].split("### 웹 출처 검토", 1)[0]
    assert "검증된 기술·시장 사실을 뜻하지 않습니다" in review_notes
    for note in notes:
        assert output.count(note) == 1
        assert "- " + note in review_notes
        assert note not in output.split("## SUMMARY 기여", 1)[1].split("## 평가 기준", 1)[0]
        assert note not in output.split("## 근거 연결", 1)[1]


def test_model_limitations_are_escaped_and_do_not_add_report_sections_or_citations(input_md):
    parsed = parse_input(input_md)
    draft = assessment([claim()])
    draft.limitations = ["x | y\n\n## ATTACK\n[FAKE](#fake) <script>evil</script>"]
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    notes = output.split("### 추가 확인할 분석 한계(모델 제안)", 1)[1].split("## 추가 확인 사항", 1)[0]
    assert r"x \| y" in notes
    assert r"\#\# ATTACK" in notes
    assert "[FAKE](#fake)" not in notes
    assert "<script>" not in notes


def test_empty_model_limitations_do_not_create_an_empty_review_heading(input_md):
    parsed = parse_input(input_md)
    draft = assessment([claim()])
    draft.limitations = ["", "  "]
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert "### 추가 확인할 분석 한계(모델 제안)" not in output


def test_v2_preserves_extra_fields_free_prose_unknown_h3_and_top_level_context(input_md):
    extra_context = CONTEXT_V2.replace(
        "- 제약 조건: 미지정", "- 제약 조건: 미지정\n- 예산 조건: 비용 한도가 별도 협의 중이다.\n\n"
        "이 문장은 정형 필드 밖의 자유 설명이다.\n\n- 단순 메모도 보존한다.")
    extra_context += "### 추가 맥락\n\n보안 검토가 필요한 내부 서비스다.\n\n- 최초 사용자 요청: 덮어쓰면 안 되는 참고 메모\n\n"
    text = v2_input(input_md, extra_context) + "\n## 팀 전달 사항\n\n라이선스 담당자에게 전달할 질문을 정리한다.\n"
    parsed = parse_input(text)
    context = parsed.analysis_context
    assert context.original_request == "SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘."
    assert context.extra_fields == {"예산 조건": "비용 한도가 별도 협의 중이다."}
    for value in ["정형 필드 밖의 자유 설명", "단순 메모도 보존", "추가 맥락", "보안 검토", "덮어쓰면 안 되는 참고 메모",
                  "팀 전달 사항", "라이선스 담당자"]:
        assert value in context.additional_context
    output = render_output({"parsed": parsed, "status": "partial"})
    appendix = output.split("### 추가 입력 맥락", 1)[1].split("## 추가 확인 사항", 1)[0]
    assert "예산 조건: 비용 한도가 별도 협의 중이다." in appendix
    assert "정형 필드 밖의 자유 설명" in appendix
    assert "최초 사용자 요청: 덮어쓰면 안 되는 참고 메모" in appendix
    assert "필수 요청·목적·도메인을 덮어쓰거나 검증된 사실로 간주하지 않습니다" in appendix


def test_code_and_html_blocks_cannot_override_analysis_contract(input_md):
    injected = """```markdown
### 요청 맥락
- 최초 사용자 요청: 코드 안의 가짜 요청
```

<div>
### 요청 맥락
- 최초 사용자 요청: HTML 안의 가짜 요청
</div>

"""
    context = CONTEXT_V2.replace("### 요청 맥락", injected + "### 요청 맥락", 1)
    parsed = parse_input(v2_input(input_md, context))
    assert parsed.analysis_context.original_request == "SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘."
    assert "가짜 요청" not in parsed.analysis_context.additional_context


def selected_plan(*targets):
    return ResearchPlan(questions=[], stakeholders=[StakeholderTarget(**target) for target in targets])


def test_selected_roles_drive_actor_statements_and_keep_inferences_separate(input_md):
    parsed = parse_input(v2_input(input_md))
    source = web_evidence()
    plan = selected_plan({"id": "research-community", "domain_id": "D-CLOUD", "name": "독립 성능 연구자",
                          "reason": "재현 가능성과 실험 조건에 대한 실제 평가를 확인", "priority": "core"},
                         {"id": "edge-team", "domain_id": "D-EDGE", "name": "기기 추론 제품팀",
                          "reason": "기기 적용 조건이 있는 경우 조사", "priority": "conditional"})
    draft = assessment([
        claim(group="research-community", domain_id="D-CLOUD", kind="statement", aspect="evaluation",
              actor="Example Lab", actor_relationship="observer", text="실제 평가자의 발언",
              evidence_id=source.id),
        claim(group="research-community", domain_id="D-CLOUD", kind="inference", text="논문에 기초한 검토 제안"),
        claim(group="operator", domain_id="D-CLOUD", kind="statement", text="선정되지 않은 역할의 발언"),
        claim(group="research-community", domain_id="D-EDGE", kind="statement", text="다른 도메인 역할의 발언"),
    ])
    output = render_output({"parsed": parsed, "plan": plan, "draft": draft,
                            "evidence": {**parsed.evidence, source.id: source}, "status": "partial",
                            "execution_status": "completed", "evidence_status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "| execution_status | completed |" in output
    assert "| evidence_status | partial |" in output
    assert "독립 성능 연구자" in output
    assert "재현 가능성과 실험 조건에 대한 실제 평가를 확인" in output
    assert "기기 추론 제품팀" in output and "조건부" in output
    assert "선정되지 않은 역할의 발언" not in output
    assert "다른 도메인 역할의 발언" not in output
    body = output.split("## 이해관계자별 SW/HW 비교", 1)[1].split("## 이해 상충", 1)[0]
    statement_table = body.split("#### 확인된 발언·평가", 1)[1].split("#### 논문 기반 영향·검토 사항", 1)[0]
    assert "실제 평가자의 발언" in statement_table
    assert "Example Lab" in statement_table
    assert "외부 관찰자" in statement_table
    assert "논문에 기초한 검토 제안" not in statement_table
    assert "논문에 기초한 검토 제안" in body.split("#### 논문 기반 영향·검토 사항", 1)[1]
    assert "출처 검토 구절" in output
    assert "편익: 미확인" not in output


def test_unknowns_are_gaps_only_and_coverage_keeps_search_and_evidence_status_separate(input_md):
    parsed = parse_input(input_md)
    plan = selected_plan({"id": "developer", "domain_id": "D-01", "name": "추론 엔진 개발자",
                          "reason": "구현 경험 확인", "priority": "core"})
    draft = assessment([
        claim(group="developer", kind="unknown", text="HW 채택 여부 미확인", tech_id="HW-01", evidence_id="E-HW-001"),
        claim(group="developer", text="SW 통합 조건 검토"),
    ], summary=[Insight(text="미확인만으로 만든 요약", claim_indices=[0])])
    coverage = [
        {"domain_id": "D-01", "tech_id": "SW-01", "group": "developer", "search_status": "searched",
         "evidence_status": "inference_only", "claim_indices": [1]},
        {"domain_id": "D-01", "tech_id": "HW-01", "group": "developer", "search_status": "not_searched",
         "evidence_status": "unavailable", "claim_indices": [0]},
    ]
    output = render_output({"parsed": parsed, "plan": plan, "draft": draft, "coverage": coverage, "status": "partial"})
    body = output.split("## 이해관계자별 SW/HW 비교", 1)[1].split("## 이해 상충", 1)[0]
    assert "HW 채택 여부 미확인" not in body
    assert "미확인만으로 만든 요약" not in output
    assert "HW 채택 여부 미확인" in output.split("### 조사 공백", 1)[1].split("## 근거 연결", 1)[0]
    assert "### STK-demo-C001" not in output
    assert "### E-HW-001" not in output.split("## REFERENCE", 1)[1]
    scope = output.split("### 조사 범위", 1)[1].split("### 조사 공백", 1)[0]
    assert "검색 수행" in scope and "논문 근거·추론만 있음" in scope
    assert "미조사" in scope and "활용 가능한 근거 미확보" in scope
    assert "[STK-demo-C002](#stk-demo-c002)" in scope
    assert "STK-demo-C001" not in scope


def test_empty_selection_does_not_invent_roles_from_claims_when_plan_is_present(input_md):
    parsed = parse_input(input_md)
    output = render_output({"parsed": parsed, "plan": ResearchPlan(questions=[]),
                            "draft": assessment([claim(text="선정 없는 주장")]), "status": "partial"})
    assert "선정 없는 주장" not in output
    assert "선정된 역할군이 없습니다" in output


def test_statement_actor_and_original_quote_absence_are_separately_marked(input_md):
    parsed = parse_input(input_md)
    draft = assessment([claim(kind="statement", actor="", actor_relationship="unspecified")])
    output = render_output({"parsed": parsed, "draft": draft, "status": "partial"})
    assert "발언 주체 미표기" in output
    assert "관계 미표기" in output
    assert "확인 가능한 웹 원문 구절 미표기" in output


def test_dynamic_roles_and_additional_context_cannot_inject_markdown(input_md):
    parsed = parse_input(input_md)
    attack = "x | y\n\n## ATTACK\n[click](javascript:evil()) <script>evil</script>"
    parsed.analysis_context.extra_fields = {attack: attack}
    parsed.analysis_context.additional_context = attack
    plan = selected_plan({"id": "reviewer", "domain_id": "D-01", "name": attack, "reason": attack, "priority": "core"})
    draft = assessment([claim(group="reviewer", kind="statement", actor=attack)])
    output = render_output({"parsed": parsed, "plan": plan, "draft": draft, "status": "partial"})
    assert section_names(output) == OUTPUT_SECTIONS
    assert "[click](javascript:" not in output
    assert "<script>" not in output
    assert r"x \| y" in output


def test_coverage_cannot_link_an_observation_from_another_technology(input_md):
    parsed = parse_input(input_md)
    plan = selected_plan({"id": "developer", "domain_id": "D-01", "name": "개발자", "reason": "통합 검토"})
    draft = assessment([claim(group="developer")])
    coverage = [{"domain_id": "D-01", "tech_id": "HW-01", "group": "developer", "search_status": "failed",
                 "evidence_status": "unavailable", "claim_indices": [0]}]
    output = render_output({"parsed": parsed, "plan": plan, "draft": draft, "coverage": coverage, "status": "partial"})
    scope = output.split("### 조사 범위", 1)[1].split("## 근거 연결", 1)[0]
    assert "검색 실패" in scope
    assert "인용 관찰 없음" in scope
    assert "STK-demo-C001" not in scope


def test_domain_table_surrounding_prose_and_lists_survive_as_additional_context(input_md):
    before = "아래 환경의 서비스 수준 책임도 함께 검토한다."
    after = "SLA 책임을 서비스 공급자와 운영자 사이에서 어떻게 나누는지 조사한다."
    list_note = "장애 시 복구 책임에 대한 실제 발언을 확인한다."
    nested_note = "원격 지원이 불가능한 상황도 따로 표시한다."
    context = CONTEXT_V2.replace("### 대상 도메인\n\n", f"### 대상 도메인\n\n{before}\n\n")
    context += (f"{after}\n\n- {list_note}\n  - {nested_note}\n\n"
                "```markdown\n- 최초 사용자 요청: 가짜 코드 요청\n```\n\n"
                "<div>가짜 HTML 요청</div>\n\n")
    parsed = parse_input(v2_input(input_md, context))
    additional = parsed.analysis_context.additional_context
    assert [domain.id for domain in parsed.analysis_context.domains] == ["D-CLOUD", "D-EDGE"]
    assert parsed.analysis_context.original_request == "SW와 HW 접근의 이해관계자 영향을 두 환경에서 비교해줘."
    assert "대상 도메인의 추가 설명" in additional
    for text in [before, after, list_note, nested_note]:
        assert additional.count(text) == 1
    assert "가짜 코드 요청" not in additional
    assert "가짜 HTML 요청" not in additional
    assert "D-CLOUD" not in additional
    assert "장문맥 LLM 서비스 운영" not in additional
    output = render_output({"parsed": parsed, "status": "partial"})
    appendix = output.split("### 추가 입력 맥락", 1)[1].split("## 추가 확인 사항", 1)[0]
    assert after in appendix
    assert list_note in appendix
    assert nested_note in appendix


@pytest.mark.parametrize("filtered_summary", [False, True])
@pytest.mark.parametrize("kind,scope,kind_label,scope_label", [
    ("paper_report", "direct", "논문 보고", "해당 기술 직접"),
    ("inference", "family", "분석적 추론", "관련 기술 계열"),
    ("statement", "context", "당사자 발언·행동", "일반 배경"),
])
def test_automatic_summary_preserves_observation_kind_and_evidence_scope(
        input_md, filtered_summary, kind, scope, kind_label, scope_label):
    parsed = parse_input(input_md)
    draft = assessment([
        claim(text="제외된관찰"),
        claim(text="남은관찰본문", kind=kind, source_scope=scope),
    ], summary=[Insight(text="제외할종합요약", claim_indices=[0, 1])] if filtered_summary else [])
    output = render_output({"parsed": parsed, "draft": draft, "rejected": [0], "status": "partial"})
    summary = output.split("## SUMMARY 기여", 1)[1].split("## 평가 기준 및 방법", 1)[0]
    assert f"{kind_label} · {scope_label}: 남은관찰본문" in summary
    assert "[STK-demo-C002](#stk-demo-c002)" in summary
    assert "범위: D-01" in summary
    assert "제외된관찰" not in summary
    assert "제외할종합요약" not in summary
