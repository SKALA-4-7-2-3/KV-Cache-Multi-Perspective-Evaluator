"""Bounded, auditable use decisions for newly collected web sources only.

These decisions constrain how a document may be cited; they do not certify its
truth. A vendor's own announcement can support an attributed statement while
remaining insufficient evidence of independent validation or customer adoption.
"""

import hashlib
import json
import re
from dataclasses import asdict, replace
from urllib.parse import urlsplit

from .evidence import quote_options, source_quote_has_text, visible_quote
from .models import Claim, Evidence, Technology, WebSourceReview
from .retrieval import family_matches

_NAME_SEPARATOR = r"[\s\-‐‑‒–—―−]*"
_ARXIV_ID = re.compile(r"(?<![\w.])(\d{4}\.\d{4,5})(?:v\d+)?(?!\w|\.\d)", re.IGNORECASE)


def _present(value: str) -> bool:
    return bool(value and value.strip() not in {"미표기", "미확인", "unknown"})


def _named_in(name: str, text: str) -> bool:
    parts = [part for part in re.split(r"[\s\-‐‑‒–—―−]+", name.strip()) if part]
    if not parts:
        return False
    pattern = r"(?<!\w)" + _NAME_SEPARATOR.join(re.escape(part) for part in parts) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _direct_technology_ids(source: Evidence, technologies: list[Technology]) -> list[str]:
    """A literal identity is necessary, never sufficient, for direct relevance.

    Search queries, requested URLs and query-associated tech_ids are not source
    content. Mentions in references can still pass this minimum identity check;
    source review and claim review must establish the actual relevance.
    """
    text = source.title + "\n" + source.excerpt
    normalized_text = " ".join(re.findall(r"[^\W_]+", text.casefold()))
    source_arxiv_ids = set(_ARXIV_ID.findall(text))
    found = []
    for technology in technologies:
        paper = re.sub(r"https?://\S+", "", technology.paper)
        paper = re.sub(r"\barxiv\s*:?\s*\d{4}\.\d{4,5}(?:v\d+)?", "", paper, flags=re.IGNORECASE)
        paper = _ARXIV_ID.sub("", paper).strip(" ,;:.()[]")
        title_words = re.findall(r"[^\W_]+", paper.casefold())
        title = " ".join(title_words)
        title_present = (len(title_words) >= 4
                         and f" {title} " in f" {normalized_text} ")
        paper_ids = set(_ARXIV_ID.findall(technology.url + " " + technology.paper))
        if (technology.id not in found
                and (_named_in(technology.name, text) or title_present or paper_ids & source_arxiv_ids)):
            found.append(technology.id)
    return found


def _check_direct_identity(source: Evidence, audit: dict, technologies: list[Technology]) -> dict:
    identifiers = _direct_technology_ids(source, technologies)
    audit["direct_tech_ids"] = identifiers
    audit["checks"]["직접 기술 식별"] = (
        ("수집 제목·본문에서 식별: " + ", ".join(identifiers)) if identifiers
        else "수집 제목·본문에서 대상 기술명·논문 제목·arXiv ID를 확인하지 못함")
    audit["checks"]["직접 관련성 최소 조건"] = (
        "기술 식별자 등장은 직접 근거의 최소 조건일 뿐 충분조건이 아님. "
        "언급·참고문헌만으로 해당 구현의 평가·채택을 인정하지 않음")
    if audit.get("relevance") == "direct" and not identifiers:
        reason = "대상 기술 식별이 없어 모델의 직접 관련 판정을 관련성 미확인으로 제한함"
        audit["relevance"] = "unknown"
        if audit.get("decision") in {"use", "limited"}:
            audit["decision"] = "limited"
        audit["reasons"] = list(dict.fromkeys([*audit["reasons"], reason]))
        audit["limitations"] = list(dict.fromkeys([*audit["limitations"], reason,
            "공통 계열 용어(CXL 등)만으로 특정 논문·구현의 직접 근거로 사용할 수 없음"]))
    return audit


def _audit(source: Evidence, reviews: list[WebSourceReview], as_of: str) -> dict:
    audit = {"decision": "hold", "document_type": "unknown", "perspective": "unknown",
             "relevance": "unknown", "evidence_basis": "unknown", "reasons": [],
             "limitations": [], "verified_quotes": [], "checks": {
                 "조회 호스트": urlsplit(source.url).hostname or "미확인",
                 "원문 확보": "수집 본문 있음" if source.excerpt.strip() else "수집 본문 없음",
                 "발행 주체": "기록 있음 — 수집 근거 참조" if _present(source.publisher) else "미확인",
                 "발행일": source.published_at if _present(source.published_at) else "미확인",
                 "교차검증": "미확인 — URL 개수나 출처 분류만으로 독립 검증을 인정하지 않음",
                 "검토 방식": "수집 정보·원문 대조 규칙과 모델 분류. 진실성 인증이나 신뢰도 점수가 아님",
             }}
    publication = re.search(r"\d{4}-\d{2}-\d{2}", source.published_at)
    if not source.excerpt.strip():
        audit.update(decision="exclude", reasons=["읽을 수 있는 원문이 없어 사실 근거로 사용하지 않음"])
        return audit
    if publication and publication.group() > as_of:
        audit.update(decision="exclude", reasons=["입력의 조사 기준일 이후에 발행된 자료"])
        return audit
    if len(reviews) != 1:
        audit["reasons"] = ["출처 평가 누락" if not reviews else "동일 출처에 상충할 수 있는 중복 평가가 있음"]
        return audit
    review = reviews[0]
    options = quote_options(source)
    quotes = [options.get(quote, quote) for quote in review.basis_quotes]
    valid = [quote for quote in quotes if source_quote_has_text(source.excerpt, quote)]
    if not quotes or len(valid) != len(quotes):
        audit["reasons"] = ["출처 분류를 뒷받침하는 원문 구절이 없거나 원문과 일치하지 않음"]
        return audit
    audit.update(review.model_dump(exclude={"evidence_id", "basis_quotes"}))
    audit["verified_quotes"] = list(dict.fromkeys(valid))
    audit["checks"]["검토 구절"] = "수집 원문 안의 연속 구절과 일치"
    if review.document_type == "supplier_publication":
        audit["perspective"] = "interested_party"
    if review.decision == "exclude" or review.relevance in {"background", "unrelated"}:
        audit["decision"] = "exclude"
        audit["reasons"].append("대상 기술의 주장 근거로 사용하지 않음")
        return audit
    limits = list(audit["limitations"])
    if not _present(source.publisher):
        limits.append("발행 주체를 수집 메타정보에서 확인하지 못함")
    if not publication:
        limits.append("발행일 미확인 — 조사 기준일과의 선후 관계를 확인하지 못함")
    if "..." in source.title or "…" in source.title:
        limits.append("제목 일부가 생략됐을 수 있음")
    if review.document_type in {"commentary", "republication", "unknown"}:
        limits.append("논평·재전재·미분류 자료는 원출처와 사실 확인이 추가로 필요함")
    if audit["perspective"] != "independent_author":
        limits.append("이해관계가 있거나 독립성 미확인 — 독립 검증으로 취급하지 않음")
    if review.relevance != "direct":
        limits.append("기술 계열 또는 관련성 미확인 — 해당 논문 구현의 성능·도입으로 일반화할 수 없음")
    if review.evidence_basis != "methods_and_results":
        limits.append("재현 가능한 방법·결과 확인 부족 — 기술 효과의 실증으로 취급하지 않음")
    audit["limitations"] = list(dict.fromkeys(limits))
    if limits or review.decision == "limited":
        audit["decision"] = "limited"
        audit["reasons"].append("발언 주체에 귀속시킨 진술만 허용하며 효과·도입 사실의 독립 증거로 사용하지 않음")
    else:
        audit["decision"] = "use"
        audit["reasons"].append("검토한 원문과 조건의 범위에서 사용 가능. 사실성이나 독립 재현을 보증하지 않음")
    return audit


def _context_fingerprint(source: Evidence, as_of: str,
                         technologies: list[Technology] | None) -> str:
    """Bind reusable decisions to the exact collected material and review context."""
    material = asdict(source)
    material.pop("audit")
    context = {"version": "source-audit-v1", "source": material, "as_of": as_of,
               "technologies": None if technologies is None else [asdict(item) for item in technologies]}
    encoded = json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def assess_web_sources(evidence: dict[str, Evidence], reviews: list[WebSourceReview],
                       as_of: str, technologies: list[Technology] | None = None,
                       *, preserve_existing: bool = False) -> dict[str, Evidence]:
    """Keep paper objects untouched; optional identities constrain direct web use.

    A later analysis may omit an already reviewed source. Opt-in preservation
    retains its completed audit only when the locally recorded context still
    matches. New and duplicate reviews always go through the normal checks.
    Omitting technologies preserves the legacy direct-identity contract.
    """
    result = dict(evidence)
    for identifier, source in evidence.items():
        if source.source_type != "web":
            continue
        own = [review for review in reviews if review.evidence_id == identifier]
        fingerprint = _context_fingerprint(source, as_of, technologies)
        if (preserve_existing and not own
                and source.audit.get("decision") in {"use", "limited", "exclude"}
                and source.audit.get("context_fingerprint") == fingerprint):
            continue
        audit = _audit(source, own, as_of)
        if technologies is not None:
            audit = _check_direct_identity(source, audit, technologies)
        audit["context_fingerprint"] = fingerprint
        result[identifier] = replace(source, audit=audit)
    return result


def pending_web_source_ids(evidence: dict[str, Evidence]) -> list[str]:
    """Return sources requiring review, excluding completed exclusion decisions."""
    return [identifier for identifier, source in evidence.items()
            if source.source_type == "web"
            and source.audit.get("decision") not in {"use", "limited", "exclude"}]


def assess_operator_sources(evidence: dict[str, Evidence], as_of: str,
                            technologies: list[Technology]) -> dict[str, Evidence]:
    """Use relevant family prose for attributed statements without a paper-name gate.

    This is a transparent topic/metadata screen, not an LLM credibility verdict.
    Source identity and factual support are checked again for each actual claim.
    """
    result = dict(evidence)
    for identifier, source in evidence.items():
        if source.source_type != "web":
            continue
        audit = _audit(source, [], as_of)
        if audit["decision"] == "exclude":  # empty body or future publication
            result[identifier] = replace(source, audit=audit)
            continue
        options = quote_options(source)
        # Strip link destinations before matching, and ignore headings or short
        # navigation labels. A URL slug is not prose about the technology.
        prose = {quote: visible_quote(quote) for quote in options.values()
                 if not quote.lstrip().startswith("#")}
        prose = {quote: text for quote, text in prose.items()
                 if len(text.split()) >= 6}
        related = [t for t in technologies if t.id in source.tech_ids and
                   family_matches(t.kind, " ".join(prose.values()))]
        topic_quotes = [quote for quote, text in prose.items()
                        if re.search(r"\b(?:kv|cxl|quanti\w*|compress\w*|offload\w*|pool\w*)\b"
                                     r"|양자화|압축|오프로딩|풀링", text, re.IGNORECASE)]
        if not related or not topic_quotes:
            audit.update(decision="exclude", relevance="unrelated",
                         reasons=["수집한 본문 구절에서 KV 압축 또는 CXL 메모리 운영 관련 내용을 확보하지 못함"],
                         limitations=["메뉴, 제목 또는 검색어의 주제 일치만으로는 근거로 사용하지 않음"])
        else:
            audit.update(
                decision="limited", relevance="family", document_type="unknown", perspective="unknown",
                evidence_basis="attributed_statement", verified_quotes=topic_quotes[:3],
                reasons=["수집한 본문 구절에 운영 조직의 KV 압축 또는 CXL 메모리 검토와 관련된 내용이 있음",
                         "개별 논문명 언급을 자료 사용 조건으로 요구하지 않음"],
                limitations=["기술 계열 자료이며 RDKV 또는 Photonic-CXL 자체의 성과나 도입 증거가 아님",
                             "주제 관련성만 확인했으며 독립성이나 내용의 진실성을 인증하지 않음",
                             "실제 주장에는 발언 주체, 관계와 해당 주장을 지지하는 본문 인용이 필요함"])
            if not _present(source.publisher):
                audit["limitations"].append("발행 주체는 수집 메타정보에서 미확인")
            if not re.search(r"\d{4}-\d{2}-\d{2}", source.published_at):
                audit["limitations"].append("발행일 미확인")
        audit["review_method"] = "topic_scoped_attribution"
        audit["checks"]["검토 방식"] = "코드의 본문 주제 확인. 실제 주장과 인용의 관계는 별도 검토"
        audit = _check_direct_identity(source, audit, technologies)
        result[identifier] = replace(source, scope="family" if related else "unclassified", audit=audit)
    return result


def web_source_issue(source: Evidence, claim: Claim) -> str:
    if source.source_type != "web":
        return ""
    decision = source.audit.get("decision", "hold")
    if decision in {"hold", "exclude"}:
        return "웹 출처 평가가 완료되지 않았거나 사용에서 제외된 자료"
    if (claim.source_scope == "direct" and "direct_tech_ids" in source.audit
            and claim.tech_id not in source.audit["direct_tech_ids"]):
        return "수집 제목·본문에서 해당 기술을 식별하지 못한 웹 자료를 직접 근거로 표시"
    if decision == "limited" and claim.kind != "statement":
        return "제한된 웹 출처를 당사자·작성자에게 귀속한 진술 이외의 근거로 사용"
    relevance = source.audit.get("relevance", "unknown")
    if relevance in {"family", "unknown"} and claim.source_scope == "direct":
        return "기술 계열·관련성 미확인 웹 자료를 해당 구현의 직접 근거로 표시"
    return ""
