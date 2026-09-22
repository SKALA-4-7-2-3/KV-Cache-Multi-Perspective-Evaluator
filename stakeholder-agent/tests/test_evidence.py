"""Exact source spans and source-local quotation references."""

from dataclasses import replace

import pytest

from stakeholder_agent.evidence import quote_options, resolve_support_quotes, substantive_quote, visible_quote
from stakeholder_agent.models import Assessment, Claim, Evidence, Support


def source(text, identifier="E-ONE"):
    return Evidence(id=identifier, tech_ids=["HW-01"], title="Research source",
                    url="https://example.org/research", location="본문", excerpt=text)


def draft_with(supports):
    claim = Claim(tech_id="HW-01", group="supplier", aspect="benefit", kind="statement",
                  text="공급자가 기술을 설명했다", condition="제공된 자료에 한정", source_scope="direct",
                  supports=supports)
    return Assessment(claims=[claim], summary=[], implications=[], limitations=[], follow_up=[])


def test_catalog_preserves_exact_sentences_and_internal_whitespace():
    first = "The supplier  describes\tshared memory."
    second = "원문에 있는 한글 문장은 번역하거나 다시 작성하지 않습니다."
    third = "A second paragraph supplies independent context."
    evidence = source(f"  {first}  {second}\n\n{third}\n")
    assert quote_options(evidence) == {"Q001": first, "Q002": second, "Q003": third}
    assert all(quote in evidence.excerpt for quote in quote_options(evidence).values())


@pytest.mark.parametrize("path_length", [40, 600])
def test_web_catalog_does_not_treat_a_long_navigation_destination_as_visible_evidence(path_length):
    raw_link = "[IR](https://example.org/" + "x" * path_length + ")"
    evidence = replace(source(raw_link), source_type="web")
    assert visible_quote(raw_link) == "IR"
    assert not substantive_quote(raw_link)
    assert quote_options(evidence) == {}


def test_meaningful_link_label_and_sentence_keep_the_exact_original_source_span():
    raw = "[공급자의 메모리 공유 기술](https://example.org/memory)에서 실제 구현의 범위를 설명한다."
    evidence = replace(source(raw), source_type="web")
    assert visible_quote(raw) == "공급자의 메모리 공유 기술에서 실제 구현의 범위를 설명한다."
    assert substantive_quote(raw)
    assert quote_options(evidence) == {"Q001": raw}
    draft = draft_with([Support(evidence_id=evidence.id, quote="Q001")])
    resolve_support_quotes(draft, {evidence.id: evidence})
    assert draft.claims[0].supports[0].quote == raw
    assert draft.claims[0].supports[0].quote in evidence.excerpt


def test_web_visible_text_filter_does_not_change_upstream_paper_catalog():
    raw_link = "[IR](https://example.org/investor-relations)"
    paper = source(raw_link)
    assert paper.source_type == "paper"
    assert not substantive_quote(raw_link)
    assert quote_options(paper) == {"Q001": raw_link}


def test_long_english_sentence_respects_word_and_character_limits_without_rewriting():
    text = " ".join(f"word{index:03}" for index in range(95)) + "."
    quotes = list(quote_options(source(text)).values())
    assert len(quotes) == 4
    assert " ".join(quotes) == text
    assert all(12 <= len(quote) <= 220 for quote in quotes)
    assert all(len(quote.split()) <= 25 for quote in quotes)
    assert all(quote in text for quote in quotes)


def test_unbroken_multilingual_text_is_still_an_exact_bounded_span():
    text = "메모리확장과추론의관계" * 75
    quotes = list(quote_options(source(text)).values())
    assert quotes
    assert all(12 <= len(quote) <= 220 and quote in text for quote in quotes)


@pytest.mark.parametrize("text", ["", " \t\n ", "Too short.", "12345678901"])
def test_empty_or_short_fragments_offer_no_quote(text):
    assert quote_options(source(text)) == {}


def test_twelve_character_source_is_accepted():
    assert quote_options(source("abcdefghijkl")) == {"Q001": "abcdefghijkl"}


def test_catalog_is_deterministic_deduplicated_and_limited_to_eighty():
    paragraphs = [f"Evidence sentence {index:03} describes a distinct observation." for index in range(100)]
    evidence = source("\n".join([paragraphs[0], *paragraphs]))
    options = quote_options(evidence)
    assert options == quote_options(evidence)
    assert list(options) == [f"Q{index:03}" for index in range(1, 81)]
    assert list(options.values()) == paragraphs[:80]
    assert len(set(options.values())) == len(options)


def test_resolver_uses_the_cited_sources_catalog_and_preserves_literal_quotes():
    one = source("First supplier describes a research implementation.", "E-ONE")
    two = source("Second supplier describes an unrelated memory system.", "E-TWO")
    literal = "The model wrote this literal quote itself."
    draft = draft_with([Support(evidence_id="E-ONE", quote="Q001"),
                        Support(evidence_id="E-TWO", quote="Q001"),
                        Support(evidence_id="E-ONE", quote=literal),
                        Support(evidence_id="E-MISSING", quote="Q001"),
                        Support(evidence_id="E-ONE", quote="Q999")])
    original_claim = draft.claims[0].model_dump(exclude={"supports"})
    assert resolve_support_quotes(draft, {one.id: one, two.id: two}) is None
    assert [support.quote for support in draft.claims[0].supports] == [
        one.excerpt, two.excerpt, literal, "Q001", "Q999",
    ]
    assert [support.evidence_id for support in draft.claims[0].supports] == [
        "E-ONE", "E-TWO", "E-ONE", "E-MISSING", "E-ONE",
    ]
    assert draft.claims[0].model_dump(exclude={"supports"}) == original_claim


@pytest.mark.parametrize("quote", [" Q001", "Q001 ", "q001", "Q1", '"Q001"', "[Q001]",
                                   "Q001: translated claim", "번역해 쓴 원문에 없는 주장"])
def test_resolver_does_not_fuzzily_match_keys_or_rewrite_free_text(quote):
    evidence = source("The source supplies a sufficiently long literal sentence.")
    draft = draft_with([Support(evidence_id=evidence.id, quote=quote)])
    resolve_support_quotes(draft, {evidence.id: evidence})
    assert draft.claims[0].supports[0].quote == quote


def test_missing_choice_in_an_empty_catalog_remains_for_validation():
    evidence = source("short")
    draft = draft_with([Support(evidence_id=evidence.id, quote="Q001")])
    resolve_support_quotes(draft, {evidence.id: evidence})
    assert draft.claims[0].supports[0].quote == "Q001"
