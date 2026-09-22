"""Contract tests use synthetic papers; no machine paths or network are required."""

import copy
import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from stakeholder_agent.contracts import InputError
from stakeholder_agent.json_input import PROJECT_PAPERS, parse_json_input


def make_paper(tech_id):
    spec = PROJECT_PAPERS[tech_id]
    paper_id = f"paper-{tech_id}"
    evidence_id = f"ev-{tech_id}"
    return {
        "schema_version": "1.1.0", "status": "succeeded",
        "paper": {"paper_id": paper_id, "title": spec["title"].split(" Cache")[0],
                  "arxiv_id": spec["arxiv_id"] if tech_id == "SW-01" else None,
                  "authors": [], "page_count": 12, "source_hash": f"hash-{tech_id}",
                  "source_path": "/unavailable/upstream/paper.pdf", "abstract": None},
        "analysis": {
            "technical_overview": {
                "experimental_results": [{"text": "논문이 조건부 성능 결과를 보고했다.",
                                          "claim_type": "observed_result", "confidence": 0.91,
                                          "evidence_ids": [evidence_id], "context_evidence_ids": []}],
                "requirements": [], "not_reported": ["requirements"],
            },
            "scope": {"domains": [{"text": "논문은 의료 사례를 언급한다.",
                                   "claim_type": "author_claim", "confidence": 0.9,
                                   "evidence_ids": [evidence_id], "context_evidence_ids": []}]},
            "limitations": {"author_stated": [{"text": "서빙 결과는 시뮬레이션이다.",
                                                "claim_type": "author_claim", "confidence": 0.99,
                                                "evidence_ids": [evidence_id], "context_evidence_ids": []}]},
        },
        "evidence_registry": [{"evidence_id": evidence_id, "document_id": paper_id,
                               "chunk_id": f"chunk-{tech_id}", "content_hash": "full-chunk-hash",
                               "content_kind": "text", "source_kind": "paper", "page": 3,
                               "section": None, "snippet": "Serving results were simulated."}],
        "quality": {"audits": [{"claim_key": "technical_overview.experimental_results.0",
                                 "evidence_ids": [evidence_id], "verdict": "supported",
                                 "reason": "원문에서 보고된 수치다."}],
                    "warnings": [], "unsupported_claims": 0, "partial_claims": 0},
        "run": {"run_id": f"upstream-{tech_id}", "embedding_model": "upstream-model"},
        "diagnostics": [],
    }


@pytest.fixture
def papers():
    return [make_paper("SW-01"), make_paper("HW-01")]


@pytest.fixture
def request_context():
    return {"original_request": "두 논문의 클라우드 데이터센터 이해관계자를 조사해줘.",
            "domains": [{"id": "D-01", "name": "클라우드 데이터센터", "scenario": "LLM 추론 운영"}],
            "requirements": {"latency": "미지정", "constraints": ["근거와 추론 구분"]},
            "additional_context": {"interests": ["구매 담당자", "운영 부담"]},
            "extra_interests": ["서비스 안정성"]}


@pytest.fixture
def envelope(papers, request_context):
    return {"schema_version": "1.0", "role": "stakeholders", "run_id": "current-run",
            "paper_analyses": papers, "request": request_context,
            "config": {"as_of": "2026-09-22"}, "round": 0,
            "budget": {"llm": 5, "search": 6, "fetch": 10},
            "usage": {"llm": 1, "search": 2, "fetch": 0}}


def test_preserves_upstream_semantics_and_requested_domain(envelope):
    original = copy.deepcopy(envelope)
    normalized = parse_json_input(envelope)
    assert envelope == original
    assert normalized.schema_version == "1.0"
    assert normalized.papers == original["paper_analyses"]
    assert normalized.request["original_request"] == original["request"]["original_request"]
    assert normalized.parsed.run_id == "current-run"
    assert normalized.parsed.as_of == "2026-09-22"
    assert normalized.parsed.analysis_context.domains[0].name == "클라우드 데이터센터"
    summary = json.loads(normalized.parsed.summary)
    assert summary[0]["analysis"] == original["paper_analyses"][0]["analysis"]
    assert summary[0]["quality"] == original["paper_analyses"][0]["quality"]
    assert "시뮬레이션" in normalized.parsed.summary
    assert summary[0]["analysis"]["technical_overview"]["experimental_results"][0]["confidence"] == 0.91
    assert any("미보고 항목 technical_overview.requirements" in gap for gap in normalized.parsed.gaps)
    assert normalized.parsed.requested_limits == envelope["budget"]
    assert normalized.usage == envelope["usage"]


def test_list_and_json_string_inputs_are_equivalent(papers, request_context, envelope):
    direct = parse_json_input(papers, request=request_context, as_of="2026-09-22", run_id="current-run")
    serialized = parse_json_input(json.dumps(envelope, ensure_ascii=False))
    assert direct.parsed.summary == serialized.parsed.summary
    assert direct.parsed.evidence == serialized.parsed.evidence


def test_source_order_does_not_change_technology_identity(papers, request_context):
    normalized = parse_json_input(list(reversed(papers)), request=request_context)
    assert [tech.id for tech in normalized.parsed.technologies] == ["SW-01", "HW-01"]
    assert normalized.parsed.evidence["ev-HW-01"].tech_ids == ["HW-01"]
    assert normalized.papers[0]["paper"]["paper_id"] == "paper-HW-01"


def test_all_registry_entries_and_context_references_survive(envelope):
    sw = envelope["paper_analyses"][0]
    extra = copy.deepcopy(sw["evidence_registry"][0])
    extra["evidence_id"] = "ev-extra"
    sw["evidence_registry"].append(extra)
    sw["analysis"]["technical_overview"]["experimental_results"][0]["context_evidence_ids"] = ["ev-extra"]
    unused = copy.deepcopy(extra)
    unused["evidence_id"] = "ev-unused"
    sw["evidence_registry"].append(unused)
    normalized = parse_json_input(envelope)
    assert {"ev-extra", "ev-unused"} <= normalized.parsed.evidence.keys()
    claims = json.loads(normalized.parsed.summary)[0]["analysis"]["technical_overview"]["experimental_results"]
    assert claims[0]["context_evidence_ids"] == ["ev-extra"]


def test_metadata_and_truncated_snippets_are_not_silently_upgraded(envelope):
    snippet = "x" * 1200
    envelope["paper_analyses"][0]["evidence_registry"][0]["snippet"] = snippet
    normalized = parse_json_input(envelope)
    source = normalized.parsed.evidence["ev-SW-01"]
    assert source.excerpt == snippet
    assert source.content_sha256 == sha256(snippet.encode()).hexdigest()
    assert source.metadata_provenance["upstream_content_hash"] == "full-chunk-hash"
    assert source.metadata_provenance["url"] == "project_registry"
    assert source.published_at == source.retrieved_at == source.publisher == "미표기"
    assert source.url == "https://arxiv.org/abs/2605.08317"
    assert "v1" not in source.url
    assert normalized.provenance[0]["paper"]["source_path"] == "/unavailable/upstream/paper.pdf"
    assert normalized.provenance[0]["run"]["run_id"] == "upstream-SW-01"
    assert normalized.provenance[0]["schema_version"] == "1.1.0"
    assert normalized.provenance[0]["possibly_truncated_evidence_ids"] == ["ev-SW-01"]
    assert any("1,200자" in gap for gap in normalized.parsed.gaps)


def test_request_extensions_and_natural_language_are_retained(envelope):
    envelope["request"]["original_request"] += "\n추가: JSON 원문을 그대로 유지.\n"
    envelope["request"]["domains"][0]["extra_detail"] = {"owner": "platform"}
    normalized = parse_json_input(envelope)
    context = normalized.parsed.analysis_context
    assert context.original_request == envelope["request"]["original_request"]
    assert json.loads(context.constraints) == envelope["request"]["requirements"]
    assert json.loads(context.additional_context) == envelope["request"]["additional_context"]
    assert json.loads(context.extra_fields["extra_interests"]) == ["서비스 안정성"]
    assert json.loads(context.extra_fields["domain_extensions"])["D-01"]["extra_detail"] == {"owner": "platform"}
    assert normalized.request["domains"][0]["extra_detail"] == {"owner": "platform"}


def test_default_date_and_run_id_are_explicit(papers, request_context):
    normalized = parse_json_input(papers, request=request_context)
    assert normalized.parsed.as_of == datetime.now(UTC).astimezone().date().isoformat()
    assert normalized.parsed.run_id.startswith("auto-")
    assert normalized.provenance[-1]["as_of_source"] == "runtime_local_date_default"
    assert normalized.provenance[-1]["run_id_source"] == "generated"
    assert any("실행일" in gap for gap in normalized.parsed.gaps)


def test_usage_can_be_exhausted_without_being_reset(envelope):
    envelope["usage"] = {"search": 9, "llm": 5, "fetch": 10}
    normalized = parse_json_input(envelope)
    assert normalized.usage == {"search": 9, "llm": 5, "fetch": 10}
    assert normalized.budget["search"] == 6


def test_partial_upstream_and_audit_warnings_become_gaps(envelope):
    sw = envelope["paper_analyses"][0]
    sw["status"] = "partial"
    sw["quality"]["warnings"] = ["일부 원문 표를 읽지 못했다."]
    sw["quality"]["audits"][0]["verdict"] = "partial"
    sw["diagnostics"] = ["원문 일부 미확인"]
    gaps = parse_json_input(envelope).parsed.gaps
    assert any("partial 상태" in gap for gap in gaps)
    assert any("원문 표" in gap for gap in gaps)
    assert any("upstream audit" in gap for gap in gaps)
    assert any("diagnostics" in gap for gap in gaps)


@pytest.mark.parametrize("bad_request", [None, {}, {"original_request": "", "domains": []}])
def test_request_is_required_before_any_execution(papers, bad_request):
    with pytest.raises(InputError, match="request|요청"):
        parse_json_input(papers, request=bad_request)


@pytest.mark.parametrize("field", ["evidence_ids", "context_evidence_ids"])
def test_dangling_claim_references_fail(envelope, field):
    envelope["paper_analyses"][0]["analysis"]["technical_overview"]["experimental_results"][0][field] = ["bad-id"]
    with pytest.raises(InputError, match="연결되지 않은 근거"):
        parse_json_input(envelope)


def test_audit_references_and_paths_are_validated(envelope):
    audit = envelope["paper_analyses"][0]["quality"]["audits"][0]
    audit["evidence_ids"] = ["bad-id"]
    with pytest.raises(InputError, match="audit.*연결되지 않은"):
        parse_json_input(envelope)
    audit["evidence_ids"] = ["ev-SW-01"]
    audit["claim_key"] = "unknown.path.0"
    with pytest.raises(InputError, match="claim_key"):
        parse_json_input(envelope)


def test_conflicting_duplicate_evidence_is_rejected(envelope):
    source = envelope["paper_analyses"][0]["evidence_registry"][0]
    duplicate = copy.deepcopy(source)
    duplicate["snippet"] = "다른 원문"
    envelope["paper_analyses"][0]["evidence_registry"].append(duplicate)
    with pytest.raises(InputError, match="근거 ID 충돌"):
        parse_json_input(envelope)


def test_cross_paper_evidence_collision_is_rejected(envelope):
    hw = envelope["paper_analyses"][1]
    hw["evidence_registry"][0]["evidence_id"] = "ev-SW-01"
    for categories in hw["analysis"].values():
        for key, claims in categories.items():
            if key != "not_reported":
                for claim in claims:
                    claim["evidence_ids"] = ["ev-SW-01"]
    hw["quality"]["audits"][0]["evidence_ids"] = ["ev-SW-01"]
    with pytest.raises(InputError, match="근거 ID 충돌"):
        parse_json_input(envelope)


@pytest.mark.parametrize("value", [-1, True, 2.0, "2", None])
@pytest.mark.parametrize("field", ["budget", "usage"])
def test_counters_require_nonnegative_integers(envelope, field, value):
    envelope[field]["llm"] = value
    with pytest.raises(InputError, match="JSON 입력 규격"):
        parse_json_input(envelope)


@pytest.mark.parametrize("value", ["2026-02-30", "2026-9-22", "today", ""])
def test_invalid_dates_fail(envelope, value):
    envelope["config"]["as_of"] = value
    with pytest.raises(InputError, match="날짜"):
        parse_json_input(envelope)


@pytest.mark.parametrize("value", ["failed", "running", "unknown"])
def test_unusable_upstream_status_fails(envelope, value):
    envelope["paper_analyses"][0]["status"] = value
    with pytest.raises(InputError, match="upstream.*상태"):
        parse_json_input(envelope)


def test_duplicate_technology_and_conflicting_identity_fail(envelope):
    envelope["paper_analyses"][1] = copy.deepcopy(envelope["paper_analyses"][0])
    with pytest.raises(InputError, match="동일한 기술"):
        parse_json_input(envelope)
    envelope["paper_analyses"][0]["paper"]["arxiv_id"] = "2607.27187"
    with pytest.raises(InputError, match="식별.*충돌"):
        parse_json_input(envelope)


def test_duplicate_json_keys_and_non_json_numbers_fail():
    for data in ['{"request": {}, "request": {}}', '{"count": NaN}', '{"count": Infinity}']:
        with pytest.raises(InputError):
            parse_json_input(data)


def test_document_id_and_page_range_are_checked(envelope):
    evidence = envelope["paper_analyses"][0]["evidence_registry"][0]
    evidence["document_id"] = "other-paper"
    with pytest.raises(InputError, match="document_id"):
        parse_json_input(envelope)
    evidence["document_id"] = "paper-SW-01"
    evidence["page"] = 13
    with pytest.raises(InputError, match="쪽수 범위"):
        parse_json_input(envelope)


def test_conflicting_separate_parameters_fail(envelope):
    with pytest.raises(InputError, match="request.*서로 다릅니다"):
        parse_json_input(envelope, request={"original_request": "different"})
    with pytest.raises(InputError, match="기준일"):
        parse_json_input(envelope, as_of="2026-09-23")
    with pytest.raises(InputError, match="run_id"):
        parse_json_input(envelope, run_id="other-run")


@pytest.mark.parametrize("field, value", [("role", "market"), ("schema_version", "2.0"), ("round", True)])
def test_envelope_contract_version_and_role_are_checked(envelope, field, value):
    envelope[field] = value
    with pytest.raises(InputError):
        parse_json_input(envelope)


def test_source_path_is_never_opened(envelope, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("The adapter must not open upstream paths.")

    monkeypatch.setattr("builtins.open", refuse)
    assert parse_json_input(envelope).papers[0]["paper"]["source_path"].startswith("/unavailable/")


def test_only_safe_runtime_config_is_propagated(envelope):
    envelope["config"].update({"model": "test-model", "model_timeout": 30,
                                "tool_timeout": 10.0, "repair_limit": 1,
                                "api_key": "sensitive-test-value", "unknown_setting": {"value": 1}})
    normalized = parse_json_input(envelope)
    assert normalized.config == {"as_of": "2026-09-22", "model": "test-model", "model_timeout": 30.0,
                                  "tool_timeout": 10.0, "repair_limit": 1}
    assert "sensitive-test-value" not in repr(normalized)
    assert any("미지원 config 필드" in gap for gap in normalized.parsed.gaps)


@pytest.mark.parametrize("field,value", [("model_timeout", 0), ("tool_timeout", True),
                                          ("repair_limit", True), ("repair_limit", 2)])
def test_invalid_runtime_config_fails(envelope, field, value):
    envelope["config"][field] = value
    with pytest.raises(InputError):
        parse_json_input(envelope)


def test_request_extension_name_collision_does_not_drop_original(envelope):
    envelope["request"]["domain_extensions"] = "user-supplied-extra"
    envelope["request"]["domains"][0]["extra"] = "per-domain-extra"
    context = parse_json_input(envelope).parsed.analysis_context
    assert context.extra_fields["domain_extensions"] == "user-supplied-extra"
    assert json.loads(context.extra_fields["_domain_extensions"])["D-01"]["extra"] == "per-domain-extra"
