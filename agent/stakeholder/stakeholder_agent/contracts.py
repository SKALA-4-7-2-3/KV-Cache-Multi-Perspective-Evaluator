"""Parse the versioned Markdown boundary and render a citation-safe report.

Document text is data: headings inside fenced/indented code, HTML, and quoted
blocks cannot define the input contract. Free-form upstream prose is retained
for the analysis step, while contract fields are parsed deterministically.
"""

import html
import re
from datetime import date
from urllib.parse import quote, urlsplit
from uuid import uuid4

from markdown_it import MarkdownIt

from .evidence import substantive_quote, visible_quote
from .models import (
    ASPECT_LABELS,
    GROUPS,
    KIND_LABELS,
    AgentState,
    AnalysisContext,
    Domain,
    Evidence,
    ParsedInput,
    Technology,
)

INPUT_SECTIONS = (
    "실행 정보", "기술 목록", "논문 기반 기술 요약", "근거 목록", "추가 요청 및 정보 공백",
)
LIMIT_FIELDS = {
    "남은 검색 요청 한도": "search",
    "남은 원문 조회 한도": "fetch",
    "남은 LLM 시도 한도": "llm",
}
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,95}\Z", re.ASCII)
_URL = re.compile(r"https?://[^\s<>\"\[\]]+")
_SCOPE_LABELS = {"direct": "해당 기술 직접", "family": "관련 기술 계열", "context": "일반 배경",
                 "unclassified": "검색 후보 자료 — 주장별 근거 범위 확인"}


class InputError(ValueError):
    """The caller supplied an ambiguous or invalid input contract."""


def _sections(tokens, tag):
    starts = [i for i, token in enumerate(tokens)
              if token.type == "heading_open" and token.tag == tag and token.level == 0]
    result = {}
    for index, start in enumerate(starts):
        name = tokens[start + 1].content.strip()
        if name in result:
            raise InputError(f"중복된 {tag} 제목: {name}")
        end = starts[index + 1] if index + 1 < len(starts) else len(tokens)
        result[name] = tokens[start + 3:end]
    return result


def _table_rows(tokens):
    rows = []
    row = None
    table_depth = 0
    for token in tokens:
        if token.type == "table_open" and token.level == 0:
            table_depth += 1
        elif token.type == "table_close" and token.level == 0:
            table_depth -= 1
        elif table_depth and token.type == "tr_open":
            row = []
        elif table_depth and token.type == "inline" and row is not None:
            row.append(token.content.strip())
        elif table_depth and token.type == "tr_close" and row is not None:
            rows.append(row)
            row = None
    return rows


def _field_table(tokens):
    rows = _table_rows(tokens)
    if not rows or rows[0] != ["항목", "값"]:
        raise InputError("실행 정보에는 '항목 | 값' 표가 필요합니다.")
    result = {}
    for row in rows[1:]:
        if len(row) != 2 or not row[0]:
            raise InputError("실행 정보 표의 항목·값 형식이 잘못되었습니다.")
        if row[0] in result:
            raise InputError(f"실행 정보 항목 중복: {row[0]}")
        result[row[0]] = row[1]
    return result


def _fields(tokens):
    result = {}
    for token in tokens:
        # A top-level list item's inline text has level 3. Quoted lists and
        # nested items have greater levels and cannot override contract fields.
        if token.type != "inline" or token.level != 3:
            continue
        name, separator, value = token.content.partition(":")
        if not separator:
            continue
        name = name.strip()
        if name in result:
            raise InputError(f"근거 필드 중복: {name}")
        result[name] = value.strip()
    return result


def _prose(tokens):
    return "\n".join(token.content for token in tokens if token.type == "inline")


def _identifier(value, label):
    if not _SAFE_ID.fullmatch(value):
        raise InputError(f"{label}에는 1~96자의 영문·숫자·하이픈만 사용할 수 있습니다.")
    return value


def _http_url(text):
    match = _URL.search(text)
    if match is None:
        return ""
    value = match.group(0).rstrip(".,;")
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or any(ord(char) < 32 for char in value) or "\\" in value):
            return ""
        # Accessing port also rejects malformed values rather than failing
        # later in a provider.
        _ = parsed.port
    except ValueError:
        return ""
    return value


def _analysis_context(sections, schema_version):
    if schema_version == "0.1":
        return AnalysisContext()
    if "분석 요청" not in sections:
        raise InputError("schema_version 0.2에는 '분석 요청' H2가 필요합니다.")
    context_sections = _sections(sections["분석 요청"], "h3")
    if "요청 맥락" not in context_sections or "대상 도메인" not in context_sections:
        raise InputError("분석 요청에는 '요청 맥락'과 '대상 도메인' H3가 필요합니다.")
    fields = _fields(context_sections["요청 맥락"])
    required = ["최초 사용자 요청", "분석 목적", "제약 조건"]
    missing = [name for name in required if name not in fields]
    if missing:
        raise InputError("요청 맥락 필드 누락: " + ", ".join(missing))
    if not fields["최초 사용자 요청"] or not fields["분석 목적"]:
        raise InputError("최초 사용자 요청과 분석 목적은 비어 있을 수 없습니다.")
    rows = _table_rows(context_sections["대상 도메인"])
    if not rows or rows[0] != ["도메인 ID", "도메인", "사용 상황"]:
        raise InputError("대상 도메인 표에는 도메인 ID, 도메인, 사용 상황 열이 필요합니다.")
    domains = []
    seen = set()
    for row in rows[1:]:
        if len(row) != 3:
            raise InputError("대상 도메인 표에는 세 개의 열이 필요합니다.")
        domain_id, name, scenario = row
        _identifier(domain_id, "도메인 ID")
        if domain_id.casefold() in seen:
            raise InputError(f"중복된 도메인 ID: {domain_id}")
        seen.add(domain_id.casefold())
        if not name:
            raise InputError(f"{domain_id}: 도메인 이름이 필요합니다.")
        domains.append(Domain(domain_id, name, scenario or "미지정"))
    if not domains:
        raise InputError("대상 도메인은 최소 한 개가 필요합니다.")
    additional = []
    free_context = []
    for token in context_sections["요청 맥락"]:
        if token.type != "inline":
            continue
        key, separator, _ = token.content.partition(":")
        if token.level == 3 and separator and key.strip() in fields:
            continue
        free_context.append(token.content)
    if free_context:
        additional.append("요청 맥락의 추가 설명:\n" + "\n".join(free_context))
    domain_prose = []
    table_depth = 0
    for token in context_sections["대상 도메인"]:
        if token.type == "table_open":
            table_depth += 1
        elif token.type == "table_close":
            table_depth -= 1
        elif token.type == "inline" and not table_depth:
            domain_prose.append(token.content)
    if domain_prose:
        additional.append("대상 도메인의 추가 설명:\n" + "\n".join(domain_prose))
    intro_tokens = []
    for token in sections["분석 요청"]:
        if token.type == "heading_open" and token.tag == "h3" and token.level == 0:
            break
        intro_tokens.append(token)
    if _prose(intro_tokens).strip():
        additional.append("분석 요청의 추가 설명:\n" + _prose(intro_tokens))
    for name, block in context_sections.items():
        if name not in {"요청 맥락", "대상 도메인"}:
            additional.append(f"분석 요청 / {name}:\n{_prose(block)}")
    for name, block in sections.items():
        if name not in {*INPUT_SECTIONS, "분석 요청"}:
            additional.append(f"추가 입력 항목 / {name}:\n{_prose(block)}")
    return AnalysisContext(original_request=fields["최초 사용자 요청"], objective=fields["분석 목적"],
                           constraints=fields["제약 조건"] or "미지정", domains=domains, origin="upstream",
                           extra_fields={key: value for key, value in fields.items() if key not in required},
                           additional_context="\n\n".join(additional))


def parse_input(input_md: str) -> ParsedInput:
    """Read schemas 0.1/0.2. Missing evidence is a gap; invalid identity is an error."""
    if not isinstance(input_md, str) or not input_md.strip():
        raise InputError("입력은 비어 있지 않은 Markdown 문자열이어야 합니다.")
    # HTML blocks, like fenced code, are opaque data and cannot define fields.
    tokens = MarkdownIt("commonmark", {"html": True}).enable("table").parse(input_md)
    sections = _sections(tokens, "h2")
    missing = [name for name in INPUT_SECTIONS if name not in sections]
    if missing:
        raise InputError("필수 H2 제목 누락: " + ", ".join(missing))
    metadata = _field_table(sections["실행 정보"])
    schema_version = metadata.get("schema_version")
    if schema_version not in {"0.1", "0.2"}:
        raise InputError("지원하는 schema_version은 0.1 또는 0.2입니다.")
    if schema_version == "0.1" and metadata.get("domain") != "cloud_datacenter":
        raise InputError("domain은 cloud_datacenter여야 합니다.")
    analysis_context = _analysis_context(sections, schema_version)
    as_of = metadata.get("조사 기준일", "")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of, re.ASCII):
            raise ValueError
        date.fromisoformat(as_of)
    except ValueError:
        raise InputError("조사 기준일은 유효한 YYYY-MM-DD 날짜여야 합니다.") from None
    run_id = metadata.get("run_id", "")
    if not run_id:
        run_id = "auto-" + uuid4().hex[:16]
        metadata["run_id"] = run_id
        metadata["run_id 생성 방식"] = "입력 누락으로 자동 생성"
    _identifier(run_id, "run_id")

    limits = {}
    for name, key in LIMIT_FIELDS.items():
        if name in metadata:
            if not re.fullmatch(r"[0-9]+", metadata[name], re.ASCII):
                raise InputError(f"{name}는 0 이상의 정수여야 합니다.")
            try:
                limits[key] = int(metadata[name])
            except ValueError:
                raise InputError(f"{name}의 정수가 너무 큽니다.") from None

    rows = _table_rows(sections["기술 목록"])
    if not rows or rows[0] != ["기술 ID", "이름", "구분", "논문·버전·URL"]:
        raise InputError("기술 목록 표는 기술 ID, 이름, 구분, 논문·버전·URL 열이 필요합니다.")
    technologies = []
    seen_ids = set()
    for row in rows[1:]:
        if len(row) != 4:
            raise InputError("기술 목록에는 네 개의 열이 필요합니다.")
        tech_id, name, kind, paper = row
        _identifier(tech_id, "기술 ID")
        if tech_id.casefold() in seen_ids:
            raise InputError(f"중복된 기술 ID: {tech_id}")
        seen_ids.add(tech_id.casefold())
        url = _http_url(paper)
        if not name or kind not in {"SW", "HW"} or not url:
            raise InputError(f"{tech_id}: 이름, SW/HW 구분, HTTP(S) 논문 URL을 확인하세요.")
        technologies.append(Technology(tech_id, name, kind, paper, url))
    if len(technologies) != 2 or {tech.kind for tech in technologies} != {"SW", "HW"}:
        raise InputError("기술 목록은 SW 한 개와 HW 한 개여야 합니다.")

    by_tech = {tech.id: tech for tech in technologies}
    evidence = {}
    seen_evidence_ids = set()
    gaps = []
    for evidence_id, block in _sections(sections["근거 목록"], "h3").items():
        _identifier(evidence_id, "근거 ID")
        if evidence_id.casefold() in seen_evidence_ids:
            raise InputError(f"앵커가 충돌하는 근거 ID: {evidence_id}")
        if re.fullmatch(rf"STK-{re.escape(run_id)}-C[0-9]+", evidence_id, re.IGNORECASE):
            raise InputError(f"출력 주장 ID와 충돌하는 근거 ID: {evidence_id}")
        seen_evidence_ids.add(evidence_id.casefold())
        fields = _fields(block)
        document_id = fields.get("문서 ID", "")
        if not document_id:
            gaps.append(f"{evidence_id}: 문서 ID가 없어 근거 등록을 보류했습니다.")
            continue
        if document_id not in by_tech:
            raise InputError(f"{evidence_id}: 문서 ID {document_id}가 기술 목록에 없습니다.")
        tech = by_tech[document_id]
        url = _http_url(fields.get("원문", ""))
        location = fields.get("위치", "") or fields.get("페이지·절", "")
        excerpt = fields.get("근거 요지(요약)", "") or fields.get("발췌", "")
        missing_fields = [label for label, value in (("원문 URL", url), ("원문 위치", location),
                                                     ("근거 요지 또는 발췌", excerpt)) if not value]
        if missing_fields:
            gaps.append(f"{evidence_id}: {', '.join(missing_fields)}가 없어 근거 등록을 보류했습니다.")
            continue
        evidence[evidence_id] = Evidence(
            id=evidence_id, tech_ids=[document_id],
            title=fields.get("제목") or tech.paper.replace(tech.url, "").strip(" ,"),
            url=url, location=location, excerpt=excerpt,
            publisher=fields.get("저자") or fields.get("기관") or "미표기",
            published_at=fields.get("발행일·버전") or fields.get("발행일") or "미표기",
            retrieved_at=fields.get("조회일") or "미표기", source_type="paper", scope="direct",
        )
    for tech in technologies:
        if not any(tech.id in item.tech_ids for item in evidence.values()):
            gaps.append(f"{tech.id}: 인용 가능한 입력 논문 근거가 없습니다.")
    summary = _prose(sections["논문 기반 기술 요약"])
    if not summary.strip():
        gaps.append("논문 기반 기술 요약이 비어 있습니다.")
    # Do not treat every request as an unresolved gap (e.g. the domain limit).
    # Keep the block as supplied context for the planning step.
    metadata["추가 요청 및 정보 공백"] = _prose(sections["추가 요청 및 정보 공백"])
    return ParsedInput(run_id, as_of, technologies, evidence, summary, gaps, metadata, limits, analysis_context)


def _escape(value):
    """Untrusted text stays one Markdown text fragment, including table cells."""
    value = " / ".join(str(value).splitlines())
    value = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+!|~>])", r"\\\1", value)


def _citation(identifier):
    return f"[{identifier}](#{identifier.lower()})"


def _url_link(url):
    # Percent-encode Markdown delimiters without stripping query strings or
    # arXiv version suffixes. A bad URL is rendered as text, never as a link.
    if _http_url(url) != url:
        return _escape(url)
    destination = quote(url, safe=":/?#[]@!$&'*+,;=%~_-")
    return f"[원문](<{destination}>)"


def _unique(items):
    return list(dict.fromkeys(str(item) for item in items if str(item).strip()))


def _audit_decision(source):
    audit = source.audit
    decision = audit.get("decision", "hold")
    if decision == "limited":
        if (audit.get("document_type") == "supplier_publication"
                or audit.get("perspective") == "interested_party"):
            return "당사자 주장으로만 사용"
        return "명시된 제한 범위에서 사용"
    return {"use": "명시된 근거 범위에서 사용 가능", "exclude": "분석 근거에서 제외",
            "hold": "평가 미완료·사용 보류"}.get(decision, "평가 미완료·사용 보류")


def _audit_scope(source):
    audit = source.audit
    relevance = {"direct": "해당 기술 직접", "family": "관련 기술 계열",
                 "background": "일반 배경", "unrelated": "대상과 무관", "unknown": "관련성 미확인"}
    basis = {"methods_and_results": "방법·결과 보고 범위", "attributed_statement": "명시된 주체의 발언 범위",
             "opinion": "의견·해석 범위", "unknown": "근거 방식 미확인"}
    return (relevance.get(audit.get("relevance"), "관련성 미확인") + " / "
            + basis.get(audit.get("evidence_basis"), "근거 방식 미확인"))


def _verified_snippet(source, supports):
    """One literal snippet per web source; never print an unverified model quote."""
    body = " ".join(source.excerpt.split())
    candidates = [support.quote for support in supports]
    candidates.extend(source.audit.get("verified_quotes", []))
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        normalized = " ".join(candidate.split())
        if not normalized or normalized not in body:
            continue
        visible = visible_quote(normalized)
        snippet = " ".join(visible.split()[:25])
        if len(snippet) > 140:
            snippet = snippet[:140]
            # Preserve complete words when the source is space-delimited.
            if " " in snippet and len(visible) > 140 and visible[140] != " ":
                snippet = snippet.rsplit(" ", 1)[0]
        snippet = snippet.rstrip()
        if substantive_quote(snippet):
            return snippet
    return ""


def _web_audit_lines(sources, used_sources, claims):
    web_sources = [source for source in sources.values() if source.source_type == "web"]
    if not web_sources:
        return []
    lines = ["", "### 웹 출처 검토", "",
             ("수집한 웹 자료를 모두 표시합니다. 사용 가능 판정·공식 출처·직접 관련성은 내용의 진실을 보장하지 않습니다. "
              "독립 작성자 표시는 독립 교차검증 완료를 뜻하지 않으며, 여러 기사도 같은 원자료를 재전달할 수 있습니다."), ""]
    document_labels = {"supplier_publication": "공급자·당사자 발행물", "research": "연구 자료",
                       "standard": "표준 문서", "reporting": "취재·보도", "commentary": "논평·분석",
                       "republication": "재전달·재게시", "unknown": "자료 유형 미확인"}
    perspective_labels = {"interested_party": "이해관계가 있는 당사자",
                          "independent_author": "독립 작성자 — 독립 교차검증 완료를 뜻하지 않음",
                          "unknown": "작성 관점 미확인"}
    quoted_urls = set()
    for source in web_sources:
        audit = source.audit
        supports = [support for claim in claims.values() for support in claim.supports
                    if support.evidence_id == source.id]
        snippet = _verified_snippet(source, supports)
        try:
            host = urlsplit(source.url).hostname or "미확인"
        except ValueError:
            host = "미확인"
        rows = [
            ("출력 인용 여부", "인용됨" if source.id in used_sources else "미사용 — REFERENCE에 포함하지 않음"),
            ("제목", source.title), ("작성자", source.author), ("발행기관", source.publisher),
            ("발행일", source.published_at), ("조회일", source.retrieved_at),
            ("원문 수집 호스트", host), ("원문 위치", source.location),
            ("자료 유형", document_labels.get(audit.get("document_type"), "자료 유형 미확인")),
            ("작성 관점", perspective_labels.get(audit.get("perspective"), "작성 관점 미확인")),
            ("사용 결정", _audit_decision(source)), ("허용·관련 범위", _audit_scope(source)),
            ("판정 사유", " / ".join(audit.get("reasons", [])) or "검토 사유 미표기"),
            ("한계", " / ".join(audit.get("limitations", [])) or "개별 한계 미표기 — 검증 완료를 의미하지 않음"),
            ("검색어", " / ".join(source.search_queries) or "검색 경로 미표기"),
        ]
        for key, value in source.metadata_provenance.items():
            rows.append((f"메타데이터 출처 — {key}", value))
        if not source.metadata_provenance:
            rows.append(("메타데이터 출처", "미표기 — 필드 추출 경로를 확인할 수 없음"))
        for key, value in audit.get("checks", {}).items():
            rows.append((f"확인 항목 — {key}", value))
        if source.content_sha256:
            rows.append(("수집 본문 SHA-256", source.content_sha256))
        lines.extend([f"#### audit-{source.id}", "", f"원문: {_url_link(source.url)}", ""])
        if source.requested_url and source.requested_url != source.url:
            lines.extend([f"조회 요청 URL: {_url_link(source.requested_url)}", ""])
        lines.extend(["| 검토 항목 | 확인 내용 |", "| --- | --- |"])
        lines.extend(f"| {_escape(key)} | {_escape(value)} |" for key, value in rows)
        # The same excerpt is never repeated in claims or REFERENCE.
        if source.url in quoted_urls:
            quote_display = "동일 원문의 검토 구절은 앞선 카드에 한 번만 표시"
        elif snippet:
            quoted_urls.add(source.url)
            quote_display = _escape(snippet)
        else:
            quote_display = "확인 가능한 구절 없음"
        lines.extend(["", "- 원문에서 확인한 검토 구절: " + quote_display, ""])
    return lines


def render_output(state: AgentState) -> str:
    """Render all nine report sections, including failed/partial executions."""
    parsed = state.get("parsed")
    draft = state.get("draft")
    sources = state.get("evidence", parsed.evidence if parsed else {})
    run_id = parsed.run_id if parsed else "unavailable"
    errors = state.get("errors", [])
    gaps = _unique((parsed.gaps if parsed else []) + state.get("gaps", []) + errors)
    rejected = set(state.get("rejected", []))
    if state.get("review"):
        rejected.update(state["review"].rejected_claim_indices)
    known_techs = {tech.id for tech in parsed.technologies} if parsed else set()
    context = parsed.analysis_context if parsed else None
    domains = {domain.id: domain for domain in context.domains} if context else {}
    schema_version = parsed.metadata.get("schema_version", "0.1") if parsed else "0.2"

    def claim_domain(claim):
        if claim.domain_id:
            return claim.domain_id if claim.domain_id in domains else ""
        if schema_version == "0.1" and len(domains) == 1:
            return next(iter(domains))
        return ""

    def scope_label(domain_ids):
        return "범위: " + ", ".join(f"{identifier} ({domains[identifier].name})"
                                    for identifier in dict.fromkeys(domain_ids))

    plan = state.get("plan")
    roles = {}
    if plan is not None:
        for target in plan.stakeholders:
            if target.domain_id in domains and _SAFE_ID.fullmatch(target.id):
                roles[(target.domain_id, target.id)] = (target.name, target.reason, target.priority)
    elif draft:
        # Direct-render compatibility uses observed roles only; never invent
        # the old five-group matrix when an execution supplied no selection.
        for claim in draft.claims:
            domain_id = claim_domain(claim)
            if domain_id and _SAFE_ID.fullmatch(claim.group):
                roles.setdefault((domain_id, claim.group),
                                 (GROUPS.get(claim.group, claim.group), "직접 렌더 입력에서 확인된 역할; 선정 사유 미전달", "미표기"))

    def role_name(claim):
        return roles[(claim_domain(claim), claim.group)][0]

    relationships = {"provider": "공급자", "competitor": "경쟁사", "adopter": "도입 주체",
                     "developer": "개발자", "customer": "고객·이용자", "observer": "외부 관찰자",
                     "unspecified": "관계 미표기"}

    def actor_label(claim):
        return f"{claim.actor or '발언 주체 미표기'} ({relationships[claim.actor_relationship]})"

    claims = {}
    unknown_claims = []
    if draft:
        for index, claim in enumerate(draft.claims):
            if (index in rejected or claim.tech_id not in known_techs
                    or (claim_domain(claim), claim.group) not in roles):
                continue
            if claim.kind == "unknown":
                unknown_claims.append(claim)
                continue
            if any(support.evidence_id not in sources for support in claim.supports):
                continue
            if not claim.supports:
                continue
            claims[index] = claim
    claim_ids = {index: f"STK-{run_id}-C{index + 1:03d}" for index in claims}
    used_sources = _unique(support.evidence_id for claim in claims.values() for support in claim.supports)

    def insight_lines(insights):
        result = []
        for insight in insights:
            if not insight.claim_indices or not all(index in claims and claims[index].kind != "unknown"
                                                   for index in insight.claim_indices):
                continue
            links = " ".join(_citation(claim_ids[index]) for index in dict.fromkeys(insight.claim_indices))
            scope = scope_label(claim_domain(claims[index]) for index in insight.claim_indices)
            result.append(f"- {_escape(insight.text)} — {_escape(scope)} {links}")
        return result

    lines = ["# 이해관계자 분석 결과", ""]
    if state.get("mode") == "fixture":
        lines.extend(["> DEMO: 고정 fixture로 실행한 예시입니다. 실제 외부 검색·LLM 조사 결과가 아닙니다.", ""])
    lines.extend(["## 분석 정보", "", "| 항목 | 값 |", "| --- | --- |"])
    metadata = {
        "schema_version": schema_version, "run_id": run_id,
        "domain": ("cloud_datacenter" if schema_version == "0.1" else ", ".join(domains))
                  if parsed else "입력 오류로 확인 불가",
        "조사 기준일": parsed.as_of if parsed else "입력 오류로 확인 불가",
        "status": state.get("status", "failed"), "실행 모드": state.get("mode", "미표기"),
        "execution_status": state.get("execution_status", "미표기"),
        "evidence_status": state.get("evidence_status", "미표기"),
        "대상": " / ".join(f"{tech.id} {tech.name} ({tech.kind}) — {tech.paper}"
                         for tech in parsed.technologies) if parsed else "입력 오류로 확인 불가",
        "사용 근거 수": str(len(used_sources)),
        "사용 근거 범위": "출력 주장에 연결된 근거만 REFERENCE에 포함",
    }
    if context:
        metadata.update({
            "최초 사용자 요청": context.original_request or "미전달 — 기존 0.1 입력",
            "분석 목적": context.objective,
            "제약 조건": context.constraints,
            "분석 맥락 출처": context.origin,
            "대상 도메인·사용 상황": " / ".join(f"{domain.id} {domain.name}: {domain.scenario}"
                                           for domain in context.domains),
            "추가 입력 맥락": ("있음 — 한계 및 편향 검토의 추가 입력 맥락에 보존"
                           if context.extra_fields or context.additional_context else "추가 전달 없음"),
        })
    if parsed and "run_id 생성 방식" in parsed.metadata:
        metadata["run_id 생성 방식"] = parsed.metadata["run_id 생성 방식"]
    operations = {}
    budget = state.get("budget")
    if budget:
        for label, key in LIMIT_FIELDS.items():
            operations[label.replace("남은", "사용한", 1)] = str(budget.used[key])
            operations[label] = str(budget.remaining(key))
    if state.get("trace"):
        operations["실행 흐름"] = " → ".join(state["trace"])
    if state.get("selection_origin"):
        operations["역할 선정 경로"] = state["selection_origin"]
    for name, value in metadata.items():
        # Contract keys and validated machine-readable values stay literal so
        # an outer orchestrator can copy remaining budgets and identifiers.
        rendered = str(value) if name in {"schema_version", "run_id", "domain", "조사 기준일"} else _escape(value)
        lines.append(f"| {name} | {rendered} |")

    lines.extend(["", "## SUMMARY 기여", ""])
    summaries = insight_lines(draft.summary) if draft else []
    if not summaries and parsed:
        # A failed synthesis must not hide individually verified observations.
        # Repeat at most one existing claim per domain and technology.
        for domain in context.domains:
            for tech in parsed.technologies:
                candidates = [(i, claim) for i, claim in claims.items()
                              if claim.tech_id == tech.id and claim.kind != "unknown"
                              and claim_domain(claim) == domain.id]
                if candidates:
                    index, claim = candidates[0]
                    summaries.append(f"- {_escape(tech.name)} — {KIND_LABELS[claim.kind]} · "
                                     f"{_escape(_SCOPE_LABELS[claim.source_scope])}: {_escape(claim.text)} — "
                                     f"{_escape(scope_label([domain.id]))} {_citation(claim_ids[index])}")
    lines.extend(summaries or ["검증을 통과한 요약 근거가 부족합니다. 아래 미확인 항목과 한계를 확인하세요."])
    lines.extend([
        "", "## 평가 기준 및 방법", "",
        "입력의 도메인·사용 상황과 조사 목적에 맞춰 역할군을 선정하고, 실제 확인한 발언·평가와 분석자의 검토 사항을 구분합니다.", "",
        ("논문 보고, 당사자 발언·행동, 분석적 추론, 미확인을 구분합니다. 기술적 편익을 특정 기업의 "
         "지지·채택으로 대신하지 않으며, 관련 기술 계열의 자료를 해당 논문의 직접 증거로 일반화하지 않습니다."), "",
        "주장별 적용 조건과 근거 범위는 근거 연결에 표시합니다. 자료 미확보는 공개 자료의 부재나 반대를 뜻하지 않습니다.", "",
    ])
    if roles:
        lines.extend(["| 도메인 | 선정 역할군 | 선정 이유 | 우선순위 |", "| --- | --- | --- | --- |"])
        for (domain_id, _), (name, reason, priority) in roles.items():
            priority_label = {"core": "핵심", "conditional": "조건부"}.get(priority, priority)
            lines.append(f"| {_escape(domains[domain_id].name)} | {_escape(name)} | {_escape(reason)} | {_escape(priority_label)} |")
    else:
        lines.append("선정된 역할군이 없습니다. 역할 선정을 완료한 뒤 조사 범위를 확인해야 합니다.")
    lines.extend(["", "## 이해관계자별 SW/HW 비교", ""])
    if parsed:
        technologies = {tech.id: f"{tech.kind}: {tech.name}" for tech in parsed.technologies}
        for domain in context.domains:
            lines.extend([
                f"### {_escape(domain.id)} · {_escape(domain.name)}", "",
                f"사용 상황: {_escape(domain.scenario)}", "",
                "#### 확인된 발언·평가", "",
            ])
            statements = [(i, claim) for i, claim in claims.items()
                          if claim_domain(claim) == domain.id and claim.kind == "statement"]
            if statements:
                lines.extend(["| 역할군 | 발언 주체·관계 | 기술 | 확인한 발언·평가 | 근거 범위 | 출처 |",
                              "| --- | --- | --- | --- | --- | --- |"])
                for index, claim in statements:
                    refs = " ".join(_citation(eid) for eid in dict.fromkeys(s.evidence_id for s in claim.supports))
                    lines.append(f"| {_escape(role_name(claim))} | {_escape(actor_label(claim))} | "
                                 f"{_escape(technologies[claim.tech_id])} | {_escape(claim.text)} {_citation(claim_ids[index])} | "
                                 f"{_escape(_SCOPE_LABELS[claim.source_scope])} | {refs} |")
            else:
                lines.append("이번 조사에서 출력 가능한 당사자 발언·평가를 확보하지 못했습니다. 미조사·실패·근거 범위는 아래 조사 범위를 확인하세요.")
            lines.extend(["", "#### 논문 기반 영향·검토 사항", "",
                          "아래 내용은 논문 보고 또는 자료에서 도출한 검토 사항이며, 해당 주체의 실제 반응을 대신하지 않습니다.", ""])
            analytical = [(i, claim) for i, claim in claims.items()
                          if claim_domain(claim) == domain.id and claim.kind in {"paper_report", "inference"}]
            for index, claim in analytical:
                lines.append(f"- {_escape(role_name(claim))} / {_escape(technologies[claim.tech_id])} / {KIND_LABELS[claim.kind]}: "
                             f"{_escape(claim.text)} {_citation(claim_ids[index])}")
            if not analytical:
                lines.append("출력 가능한 논문 보고·분석적 검토 사항이 없습니다.")
            lines.append("")
    else:
        lines.append("기술 식별에 필요한 입력이 없어 비교를 수행하지 못했습니다.")

    lines.extend(["", "## 이해 상충 및 관점 간 연결", ""])
    implications = insight_lines(draft.implications) if draft else []
    lines.extend(implications or ["검증된 주장에 연결되는 시사점이 부족하여 판단을 보류합니다."])
    lines.extend(["", "## 한계 및 편향 검토", ""])
    limitations = _unique([
        "논문 근거는 앞단에서 전달된 요약·발췌 범위입니다. 이 에이전트가 논문 전체를 재검증한 것은 아닙니다.",
        "외부 자료는 실제 조회된 원문 범위에 한정됩니다. 공급자 발표와 독립 검증, 특정 구현과 기술 계열을 구분합니다.",
        "근거 ID·원문 구절 검사 및 모델 검토는 독립적인 실증이나 사실의 완전한 검증을 보장하지 않습니다.",
    ] + gaps)
    if unknown_claims:
        limitations.append("조사 공백의 미확인 항목은 해당 정보의 부재나 이해관계자의 반대를 뜻하지 않습니다.")
    if rejected:
        limitations.append(f"검증에서 제외된 주장 {len(rejected)}개와 그 주장에 의존한 요약·시사점은 출력하지 않았습니다.")
    for item in limitations or ["분석은 입력과 실제 조회 범위에 한정됩니다. 보고된 결과가 모든 운영 환경을 보장하지 않습니다."]:
        lines.append("- " + _escape(item))
    proposed_limitations = _unique(draft.limitations if draft else [])
    if proposed_limitations:
        lines.extend(["", "### 추가 확인할 분석 한계(모델 제안)", "",
                      ("분석 중 제기한 확인 사항이며, 검증된 기술·시장 사실을 뜻하지 않습니다. "
                       "적용 범위와 표현의 타당성을 추가 확인해야 합니다."), ""])
        lines.extend("- " + _escape(item) for item in proposed_limitations)
    if context and (context.extra_fields or context.additional_context):
        lines.extend(["", "### 추가 입력 맥락", "",
                      "상위 입력에서 전달된 추가 자료를 보존합니다. 필수 요청·목적·도메인을 덮어쓰거나 검증된 사실로 간주하지 않습니다.", ""])
        for key, value in context.extra_fields.items():
            lines.append(f"- {_escape(key)}: {_escape(value)}")
        if context.additional_context:
            lines.extend(["", _escape(context.additional_context), ""])
    if operations:
        lines.extend(["", "### 실행 기록", "", "| 항목 | 값 |", "| --- | --- |"])
        lines.extend(f"| {_escape(key)} | {_escape(value)} |" for key, value in operations.items())
    lines.extend(_web_audit_lines(sources, used_sources, claims))
    lines.extend(["", "## 추가 확인 사항", ""])
    coverage = [row for row in state.get("coverage", [])
                if (row.get("domain_id"), row.get("group")) in roles and row.get("tech_id") in known_techs]
    if coverage:
        lines.extend(["### 조사 범위", "",
                      "검색 실행 상태와 확보한 근거의 범위는 별개입니다. 미조사는 근거 부재를 뜻하지 않습니다.", "",
                      "| 도메인 | 역할군 | 기술 | 검색 상태 | 근거 상태 | 연결된 관찰 |",
                      "| --- | --- | --- | --- | --- | --- |"])
        search_labels = {"not_searched": "미조사", "searched": "검색 수행", "failed": "검색 실패"}
        evidence_labels = {"direct": "직접 관련 근거", "family": "관련 기술 계열 근거",
                           "inference_only": "논문 근거·추론만 있음", "unavailable": "활용 가능한 근거 미확보"}
        for row in coverage:
            indices = [index for index in row.get("claim_indices", []) if isinstance(index, int) and index in claims
                       and claim_domain(claims[index]) == row["domain_id"]
                       and claims[index].group == row["group"] and claims[index].tech_id == row["tech_id"]]
            refs = " ".join(_citation(claim_ids[index]) for index in dict.fromkeys(indices)) or "인용 관찰 없음"
            domain_id, group = row["domain_id"], row["group"]
            lines.append(f"| {_escape(domains[domain_id].name)} | {_escape(roles[(domain_id, group)][0])} | "
                         f"{_escape(technologies[row['tech_id']])} | "
                         f"{_escape(search_labels.get(row.get('search_status'), '미표기'))} | "
                         f"{_escape(evidence_labels.get(row.get('evidence_status'), '미표기'))} | {refs} |")
        lines.append("")
    if unknown_claims:
        lines.extend(["### 조사 공백", "", "미확인 사항은 사실 주장이나 참고문헌의 근거로 사용하지 않습니다.", "",
                      "| 도메인 | 역할군 | 기술 | 미확인 사항 |", "| --- | --- | --- | --- |"])
        for claim in unknown_claims:
            lines.append(f"| {_escape(domains[claim_domain(claim)].name)} | {_escape(role_name(claim))} | "
                         f"{_escape(technologies[claim.tech_id])} | {_escape(claim.text)} |")
        lines.append("")
    follow_up = _unique((draft.follow_up if draft else []) + errors)
    lines.extend(["- " + _escape(item) for item in follow_up] or ["미확인 항목의 당사자 자료와 실제 운영 조건을 추가 확인해야 합니다."])

    lines.extend(["", "## 근거 연결", ""])
    for index, claim in claims.items():
        lines.extend([
            f"### {claim_ids[index]}", "",
            f"- 내용: {_escape(claim.text)}",
            f"- 성격: {KIND_LABELS[claim.kind]}",
            f"- 대상: {_escape(claim.tech_id)} / {_escape(role_name(claim))} / {ASPECT_LABELS[claim.aspect]}",
            f"- 도메인: {_escape(scope_label([claim_domain(claim)]).removeprefix('범위: '))}",
            f"- 적용 조건: {_escape(claim.condition or '미표기')}",
            f"- 근거 범위: {_SCOPE_LABELS[claim.source_scope]}",
            "- 근거: " + (", ".join(_citation(identifier) for identifier in
                                  dict.fromkeys(s.evidence_id for s in claim.supports)) or "미확인 — 인용 근거 없음"),
            "",
        ])
        if claim.kind == "statement":
            web_supports = [sources[support.evidence_id] for support in claim.supports
                            if sources[support.evidence_id].source_type == "web"]
            quoted = [source for source in web_supports if _verified_snippet(
                source, [support for support in claim.supports if support.evidence_id == source.id])]
            quote_location = (" ".join(f"[출처 검토 구절](#audit-{source.id.lower()})" for source in quoted)
                              or "확인 가능한 웹 원문 구절 미표기")
            lines.extend([f"- 발언 주체·관계: {_escape(actor_label(claim))}",
                          f"- 원문 구절 확인: {quote_location}", ""])
        for identifier in dict.fromkeys(s.evidence_id for s in claim.supports):
            source = sources[identifier]
            if source.source_type == "web":
                lines.extend([(f"- 웹 출처 판정: {_citation(identifier)} — {_escape(_audit_decision(source))}; "
                               f"{_escape(_audit_scope(source))}. [검토 상세](#audit-{identifier.lower()})"), ""])
    if not claims:
        lines.extend(["출력 가능한 검증된 주장이 없습니다.", ""])
    lines.extend(["## REFERENCE", ""])
    for evidence_id in used_sources:
        source = sources[evidence_id]
        lines.extend([
            f"### {evidence_id}", "",
            f"- 제목: {_escape(source.title)}",
            f"- 작성자·기관: {_escape(source.publisher)}",
            f"- 발행일·버전: {_escape(source.published_at)}",
            f"- 원문: {_url_link(source.url)}",
            f"- 사용 위치: {_escape(source.location)}",
            f"- 조회일: {_escape(source.retrieved_at)}",
            f"- 유형·범위: {_escape(source.source_type)} / {_escape(_SCOPE_LABELS.get(source.scope, source.scope))}",
            "",
        ])
        if source.source_type == "web":
            lines.extend([f"- 작성자: {_escape(source.author)}",
                          f"- 웹 출처 검토: [판정·허용 범위·수집 경로](#audit-{evidence_id.lower()})", ""])
    if not used_sources:
        lines.append("실제 출력 주장에 인용된 근거가 없습니다.")
    return "\n".join(lines).rstrip() + "\n"
