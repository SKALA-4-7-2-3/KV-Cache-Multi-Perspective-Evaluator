"""Conservative normalization of model-returned technical evidence references.

The model receives canonical evidence IDs, but may occasionally omit the
``@sha12`` separator or repeat an ID prefix.  Normalization is intentionally
limited to references that resolve to exactly one item in the supplied
registry.  Anything ambiguous or unknown is preserved so the ordinary
contract validator can reject it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from paper_review_agent.technical_schemas import TechnicalEvidence


ModelT = TypeVar("ModelT", bound=BaseModel)

_PAGE_TOKEN = re.compile(r"(?:^|:)p(?P<page>\d{4})(?=:)")
_NUMBER_TOKEN = re.compile(
    r"(?<![A-Za-z0-9.\-])[-+]?\d[\d,]*(?:\.\d+)?(?:\s*[×xX%])?"
)
_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_LEXICAL_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.+/-]{2,}")


@dataclass(frozen=True)
class _EvidenceLocatorKey:
    evidence_id: str
    source_kind: str
    page: int
    element_id: str
    suffix: str

    @property
    def page_element_suffix(self) -> str:
        return f"p{self.page:04d}:{self.element_id}:{self.suffix}"

    @property
    def element_suffix(self) -> str:
        return f"{self.element_id}:{self.suffix}"


class EvidenceIdNormalizer:
    """Resolve only exact or uniquely identifiable locator-tail references."""

    def __init__(self, evidence: list[TechnicalEvidence]):
        self._exact = {item.evidence_id: item.evidence_id for item in evidence}
        self._source_kind = {
            item.evidence_id: item.source_kind for item in evidence
        }
        self._keys = tuple(_locator_key(item) for item in evidence)

    def resolve(self, reference: str) -> str:
        """Return a canonical ID, or the original reference when not provable."""

        exact = self._exact.get(reference)
        if exact is not None:
            return exact

        source_hint = _source_kind_hint(reference)
        candidates = [
            key
            for key in self._keys
            if source_hint is None or key.source_kind == source_hint
        ]

        # This handles both a missing ``@sha12`` separator and a duplicated
        # prefix, because in each case the canonical page/element/suffix tuple
        # remains the final locator tail returned by the model.
        resolved = _only(
            key.evidence_id
            for key in candidates
            if reference.endswith(key.page_element_suffix)
        )
        if resolved is not None:
            return resolved

        # Some structured outputs retain only the element locator and suffix.
        # Accept that form only when it is unique.  If the model supplied page
        # tokens, require the candidate to agree with one of them rather than
        # silently discarding a conflicting page.
        page_hints = {
            int(match.group("page")) for match in _PAGE_TOKEN.finditer(reference)
        }
        resolved = _only(
            key.evidence_id
            for key in candidates
            if reference.endswith(key.element_suffix)
            and (not page_hints or key.page in page_hints)
        )
        return resolved if resolved is not None else reference

    def source_kind(self, reference: str) -> str | None:
        return self._source_kind.get(self.resolve(reference))


def normalize_evidence_references(
    model: ModelT, evidence: list[TechnicalEvidence]
) -> ModelT:
    """Normalize every evidence reference list in a validated Pydantic model.

    Matching field names rather than a fixed list of schema paths makes this
    cover ``PaperAnalysis`` claims, ``TechnicalClaim``, ``CriticalClaimItem``,
    ``ExperimentObservation`` and top-level ``TechnicalDossier.evidence_ids``
    while retaining validation by the model's concrete class.
    """

    normalizer = EvidenceIdNormalizer(evidence)

    def visit(value: object, field_name: str | None = None) -> object:
        if isinstance(value, dict):
            normalized_dict = {
                key: visit(child, key) for key, child in value.items()
            }
            if "evidence_ids" in normalized_dict and "context_evidence_ids" in normalized_dict:
                primary = list(normalized_dict.get("evidence_ids") or [])
                context = list(normalized_dict.get("context_evidence_ids") or [])
                unresolved_primary = [
                    item for item in primary if normalizer.source_kind(item) is None
                ]
                unresolved_context = [
                    item for item in context if normalizer.source_kind(item) is None
                ]
                paper_references = [
                    item
                    for item in [*primary, *context]
                    if normalizer.source_kind(item) == "paper"
                ]
                common_references = [
                    item
                    for item in [*primary, *context]
                    if normalizer.source_kind(item) == "common"
                ]
                normalized_dict["evidence_ids"] = list(
                    dict.fromkeys(
                        (
                            paper_references
                            if paper_references
                            else [
                                item
                                for item in primary
                                if normalizer.source_kind(item) == "common"
                            ]
                        )
                        + unresolved_primary
                    )
                )
                normalized_dict["context_evidence_ids"] = list(
                    dict.fromkeys(
                        common_references
                        + unresolved_context
                    )
                )
            return normalized_dict
        if isinstance(value, list):
            if field_name in {"evidence_ids", "context_evidence_ids"}:
                normalized = [
                    normalizer.resolve(item) if isinstance(item, str) else item
                    for item in value
                ]
                return list(dict.fromkeys(normalized))
            return [visit(item) for item in value]
        return value

    payload = visit(model.model_dump(mode="python"))
    return type(model).model_validate(payload)


def augment_precise_numeric_references(
    model: ModelT, evidence: list[TechnicalEvidence]
) -> ModelT:
    """Attach a unique exact cell/span when a claim cited only its parent object."""

    evidence_by_id = {item.evidence_id: item for item in evidence}

    def visit(value: object) -> object:
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        updated = {key: visit(child) for key, child in value.items()}
        references = updated.get("evidence_ids")
        if not isinstance(references, list) or not references:
            return updated
        numeric_text = updated.get("text")
        if not isinstance(numeric_text, str) and isinstance(
            updated.get("observation_id"), str
        ):
            # Observation conditions are part of the assertion, not optional
            # prose. Include them while attaching precise row/header evidence
            # so model, platform, context and concurrency numbers remain just
            # as traceable as the measured value.
            numeric_text = " ".join(
                str(updated.get(field) or "")
                for field in (
                    "metric",
                    "value",
                    "value_min",
                    "value_max",
                    "unit",
                    "baseline",
                    "model",
                    "hardware",
                    "context_length",
                    "concurrency",
                    "dataset",
                    "workload",
                )
            )
        if not isinstance(numeric_text, str):
            numeric_text = updated.get("value")
        if not isinstance(numeric_text, str):
            return updated
        numbers = list(dict.fromkeys(_normalized_numbers(numeric_text)))
        if not numbers:
            return updated
        cited = [
            evidence_by_id[item]
            for item in references
            if isinstance(item, str) and item in evidence_by_id
        ]
        additions: list[str] = _matching_table_row_companions(
            numeric_text,
            cited,
            evidence,
            excluded_ids=set(references),
        )
        for number in numbers:
            matching_cited = [
                item
                for item in cited
                if number in _normalized_numbers(item.snippet)
            ]
            if matching_cited and any(
                _precise_for_number(item, number) for item in matching_cited
            ):
                continue
            candidates = [
                item
                for item in evidence
                if item.evidence_id not in references
                and number in _normalized_numbers(item.snippet)
                and _precise_for_number(item, number)
                and matching_cited
                and any(_same_visual_object(item, parent) for parent in matching_cited)
            ]
            candidate_ids = list(dict.fromkeys(item.evidence_id for item in candidates))
            if len(candidate_ids) != 1:
                # A model can cite a nearby aggregate whose text contains a
                # different value (for example, 256K for a claim about five
                # models).  Search the same cited paper for an exact number
                # token and require a unique lexical best match rather than
                # accepting substring coincidence.
                document_ids = {item.document_id for item in cited}
                broad = [
                    item
                    for item in evidence
                    if item.evidence_id not in references
                    and item.document_id in document_ids
                    and number in _normalized_numbers(item.snippet)
                    and _precise_for_number(item, number)
                ]
                claim_words = _lexical_words(numeric_text)
                scored = [
                    (
                        len(claim_words.intersection(_lexical_words(item.snippet))),
                        _page_affinity(item, cited),
                        item,
                    )
                    for item in broad
                ]
                best_score = max(
                    ((lexical, affinity) for lexical, affinity, _ in scored),
                    default=(0, (-1, -10_000)),
                )
                best = [
                    item
                    for lexical, affinity, item in scored
                    if (lexical, affinity) == best_score and lexical >= 2
                ]
                candidate_ids = list(
                    dict.fromkeys(item.evidence_id for item in best)
                )
            if len(candidate_ids) == 1:
                additions.extend(candidate_ids)
        updated["evidence_ids"] = list(dict.fromkeys([*references, *additions]))
        return updated

    return type(model).model_validate(visit(model.model_dump(mode="python")))


_EVALUATION_MODE_PATTERNS = {
    "emulated": re.compile(r"\bemulat(?:e|ed|es|ing|ion|ions)\b", re.IGNORECASE),
    "simulated": re.compile(r"\bsimulat(?:e|ed|es|ing|ion|ions)\b", re.IGNORECASE),
    "measured": re.compile(r"\bmeasur(?:e|ed|es|ing|ement|ements)\b", re.IGNORECASE),
    "analytical": re.compile(r"\banalyt(?:ic|ical|ically|ics)\b", re.IGNORECASE),
}


def augment_observation_evaluation_modes(
    model: ModelT, evidence: list[TechnicalEvidence]
) -> ModelT:
    """Resolve ``not_stated`` only from a uniquely matching explicit mode passage.

    Exact numeric spans often sit in the results paragraph while the preceding
    setup/contribution passage states that those parameters were emulated or
    simulated.  This helper joins both citations only when one evaluation mode
    is explicitly named by same-paper evidence with strong lexical overlap.
    Ambiguous or weak matches remain ``not_stated`` for the auditor to reject.
    """

    evidence_by_id = {item.evidence_id: item for item in evidence}

    def visit(value: object) -> object:
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        updated = {key: visit(child) for key, child in value.items()}
        if (
            updated.get("evaluation_mode") != "not_stated"
            or not isinstance(updated.get("observation_id"), str)
            or not isinstance(updated.get("evidence_ids"), list)
        ):
            return updated
        references = [
            item for item in updated["evidence_ids"] if isinstance(item, str)
        ]
        cited = [evidence_by_id[item] for item in references if item in evidence_by_id]
        document_ids = {item.document_id for item in cited}
        if not document_ids:
            return updated
        description = " ".join(
            str(updated.get(field) or "")
            for field in (
                "metric",
                "value",
                "unit",
                "baseline",
                "model",
                "hardware",
                "context_length",
                "concurrency",
                "dataset",
                "workload",
            )
        )
        words = _lexical_words(description)
        scored: list[tuple[int, tuple[int, int], str, TechnicalEvidence]] = []
        for item in evidence:
            if item.document_id not in document_ids:
                continue
            modes = [
                mode
                for mode, pattern in _EVALUATION_MODE_PATTERNS.items()
                if pattern.search(item.snippet)
            ]
            if len(modes) != 1:
                continue
            overlap = len(words.intersection(_lexical_words(item.snippet)))
            if overlap < 3:
                continue
            scored.append((overlap, _page_affinity(item, cited), modes[0], item))
        if not scored:
            return updated
        scored.sort(key=lambda item: (item[0], item[1], item[3].evidence_id), reverse=True)
        best_score = (scored[0][0], scored[0][1])
        best = [item for item in scored if (item[0], item[1]) == best_score]
        best_modes = {item[2] for item in best}
        if len(best_modes) != 1:
            return updated
        mode = next(iter(best_modes))
        # A different mode with equal lexical overlap remains ambiguous even
        # when its page happens to be nearer to an existing citation.
        competing_modes = {
            item[2] for item in scored if item[0] == scored[0][0]
        }
        if len(competing_modes) != 1:
            return updated
        supporting = min(
            (item[3] for item in best if item[2] == mode),
            key=lambda item: item.evidence_id,
        )
        updated["evaluation_mode"] = mode
        updated["evidence_ids"] = list(
            dict.fromkeys([*references, supporting.evidence_id])
        )
        return updated

    return type(model).model_validate(visit(model.model_dump(mode="python")))


def _matching_table_row_companions(
    claim_text: str,
    cited: list[TechnicalEvidence],
    evidence: list[TechnicalEvidence],
    *,
    excluded_ids: set[str],
) -> list[str]:
    """Attach exact cells for row conditions named by a table-value claim.

    A result cell such as ``1.9×-11.8×`` does not itself repeat the adjacent
    ``LLaMA-8B`` and ``1×H100`` cells.  When the claim names those conditions,
    cite their individual cells too.  Matching is restricted to the same table
    element and row and requires the complete cell text to occur in the claim,
    so it cannot jump to another configuration with a coincidentally equal
    number.
    """

    normalized_claim = _literal_normalize(claim_text)
    row_keys = {
        (
            item.document_id,
            item.locator.physical_page,
            item.locator.element_id,
            cell.row_index,
        )
        for item in cited
        if item.content_kind == "table"
        for cell in item.locator.table_cells
    }
    if not row_keys:
        return []
    additions: list[str] = []
    for item in evidence:
        if item.evidence_id in excluded_ids or item.content_kind != "table":
            continue
        for cell in item.locator.table_cells:
            key = (
                item.document_id,
                item.locator.physical_page,
                item.locator.element_id,
                cell.row_index,
            )
            raw = _literal_normalize(cell.raw_text)
            if key in row_keys and len(raw) >= 2 and raw in normalized_claim:
                additions.append(item.evidence_id)
                break
    return list(dict.fromkeys(additions))


def _literal_normalize(value: str) -> str:
    return (
        value.casefold()
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("x", "×")
        .replace(" ", "")
    )


def _locator_key(evidence: TechnicalEvidence) -> _EvidenceLocatorKey:
    suffix = evidence.evidence_id.rsplit(":", 1)[-1]
    return _EvidenceLocatorKey(
        evidence_id=evidence.evidence_id,
        source_kind=evidence.source_kind,
        page=evidence.locator.physical_page or 0,
        element_id=evidence.locator.element_id,
        suffix=suffix,
    )


def _source_kind_hint(reference: str) -> str | None:
    for source_kind in ("paper", "common"):
        if reference.startswith(source_kind + ":"):
            return source_kind
    return None


def _only(values: Iterable[str]) -> str | None:
    unique = set(values)
    if len(unique) != 1:
        return None
    return next(iter(unique))


def _normalized_numbers(value: str) -> list[str]:
    values = []
    for match in _NUMBER_TOKEN.finditer(value):
        raw = match.group(0)
        before = value[: match.start()].rstrip()
        after = value[match.end() :].lstrip()
        numeric_part = raw.rstrip("×xX% ")
        brace_list = before.endswith("{") and after.startswith("}")
        valid_thousands = bool(
            re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", numeric_part)
        )
        parts = (
            numeric_part.split(",")
            if "," in numeric_part and (brace_list or not valid_thousands)
            else [numeric_part]
        )
        suffix = raw[len(numeric_part) :]
        for index, part in enumerate(parts):
            if part:
                token = part + (suffix if index == len(parts) - 1 else "")
                values.append(
                    re.sub(r"[\s,]", "", token).lower().replace("x", "×")
                )
    lowered = value.casefold()
    values.extend(
        number
        for word, number in _NUMBER_WORDS.items()
        if re.search(rf"\b{word}\b", lowered)
    )
    return list(dict.fromkeys(values))


def _page_affinity(
    candidate: TechnicalEvidence, cited: list[TechnicalEvidence]
) -> tuple[int, int]:
    """Prefer an equally lexical locator on, then nearest to, cited pages."""

    page = candidate.locator.physical_page
    cited_pages = [
        item.locator.physical_page
        for item in cited
        if item.document_id == candidate.document_id
        and item.locator.physical_page is not None
    ]
    if page is None or not cited_pages:
        return (-1, -10_000)
    distance = min(abs(page - cited_page) for cited_page in cited_pages)
    return (1 if distance == 0 else 0, -distance)


def _lexical_words(value: str) -> set[str]:
    words = {
        match.group(0).casefold().strip("._+-/")
        for match in _LEXICAL_TOKEN.finditer(value)
    }
    return {
        word
        for word in words
        if word
        and word
        not in {"the", "and", "with", "from", "that", "this", "result", "results"}
    }


def _precise_for_number(evidence: TechnicalEvidence, number: str) -> bool:
    if evidence.content_kind == "table":
        return any(
            any(
                number in _normalized_numbers(value or "")
                for value in (cell.raw_text, cell.row_header, cell.column_header)
            )
            for cell in evidence.locator.table_cells
        )
    if evidence.extraction_method == "vision":
        return bool(evidence.locator.crop_sha256 or evidence.locator.visual_artifact_id)
    return evidence.locator.text_span is not None


def _same_visual_object(
    candidate: TechnicalEvidence, parent: TechnicalEvidence
) -> bool:
    if candidate.document_id != parent.document_id:
        return False
    if candidate.locator.physical_page != parent.locator.physical_page:
        return False
    candidate_ids = {
        candidate.locator.element_id,
        candidate.locator.parent_element_id,
    }
    parent_ids = {parent.locator.element_id, parent.locator.parent_element_id}
    return bool({item for item in candidate_ids if item} & {item for item in parent_ids if item})
