"""Enrich a reference view only from identity-bound literal source metadata."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
import re
from typing import Any

from .references import _url_key


_FIELDS = {'title', 'authors_or_organization', 'publication_date', 'year'}
_DESCRIPTORS = {'metadata_source', 'metadata_basis'}
_MISSING = {'', 'unknown', 'none', 'null', 'n/a', '미표기', '미확인', '없음', '작성자 미상', '제목 미확인'}
_MONTHS = {name: index for index, name in enumerate((
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'), 1)}


def _text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ', '.join(_text(part) for part in value)
    return ' '.join(str(value if value is not None else '').split())


def _missing(value: Any) -> bool:
    return _text(value).casefold() in _MISSING


def _year(value: Any) -> int | None:
    if _missing(value):
        return None
    match = re.match(r'^(\d{4})(?:$|[-/.])', _text(value))
    if match:
        return int(match[1])
    match = re.fullmatch(r'([A-Z][a-z]+) \d{1,2}, (\d{4})', _text(value))
    return int(match[2]) if match and match[1] in _MONTHS else None


def legacy_reference_metadata(registry: dict) -> dict:
    """Existing caller-supplied records retain their behavior, without applying proofs early."""
    if not isinstance(registry, dict) or any(not isinstance(record, dict) for record in registry.values()):
        raise ValueError('reference_metadata_registry_requires_object_records')
    return deepcopy({url: record for url, record in registry.items()
                     if 'source_proof' not in record})


def _literal_value(field: str, value: Any, proof: dict, excerpt: str) -> None:
    spans = proof.get('spans')
    if not isinstance(spans, list) or len(spans) != 1 or not isinstance(spans[0], dict):
        raise ValueError('field_requires_one_contiguous_original_span')
    span = spans[0]
    start, end, quote = span.get('start'), span.get('end'), span.get('quote')
    if (type(start) is not int or type(end) is not int or not isinstance(quote, str)
            or not 0 <= start < end <= len(excerpt) or excerpt[start:end] != quote):
        raise ValueError('field_span_or_literal_quote_mismatch')
    transform = proof.get('transform')
    if field in {'title', 'authors_or_organization'} and transform == 'whitespace':
        if not isinstance(value, str) or not value or value != _text(quote):
            raise ValueError('field_whitespace_value_mismatch')
    elif field == 'authors_or_organization' and transform == 'author_list':
        if (not isinstance(value, list) or not value or any(not isinstance(v, str)
                or not v or v != _text(v) for v in value) or ', '.join(value) != _text(quote)):
            raise ValueError('field_author_list_literal_mismatch')
    elif field == 'year' and transform == 'year':
        if type(value) is not int or not re.fullmatch(r'\d{4}', quote) or str(value) != quote:
            raise ValueError('field_year_literal_mismatch')
    elif field == 'publication_date' and transform == 'year_date':
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}', quote) or value != quote:
            raise ValueError('field_year_date_literal_mismatch')
    elif field == 'publication_date' and transform == 'date':
        match = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', quote)
        if match:
            canonical = date(*map(int, match.groups())).isoformat()
        else:
            match = re.fullmatch(r'([A-Z][a-z]+) (\d{1,2}), (\d{4})', quote)
            if not match or match[1] not in _MONTHS:
                raise ValueError('field_date_literal_format_unsupported')
            canonical = date(int(match[3]), _MONTHS[match[1]], int(match[2])).isoformat()
        if not isinstance(value, str) or value != canonical:
            raise ValueError('field_date_literal_value_mismatch')
    else:
        raise ValueError('field_transform_unsupported')


def verify_reference_metadata(registry: dict, parsed, *, source_reports: list | tuple) -> tuple[dict, list[dict]]:
    """Return safe overrides plus an audit; another input may simply lack a proof's source.

    source_reports are the unchanged original USABLE_SOURCE_REPORTS, not the
    excerpt-free collected inventory. Both identities must agree. Original sources
    and registered metadata are never mutated. A populated conflict
    is retained, except an exact substring title may be expanded to its proven full title.
    """
    overrides, audit = legacy_reference_metadata(registry), []
    url_counts, invalid_urls = {}, set()
    for url in registry:
        try:
            normalized = _url_key(url)
        except ValueError:
            invalid_urls.add(url)
            continue
        url_counts[normalized] = url_counts.get(normalized, 0) + 1
    for url, record in registry.items():
        if not isinstance(record, dict) or 'source_proof' not in record:
            continue
        proof = record['source_proof']
        entry = {'url': url, 'source_id': proof.get('source_id') if isinstance(proof, dict) else None,
                 'status': 'skipped', 'proof_verified': False, 'fields': []}
        audit.append(entry)
        try:
            if url in invalid_urls:
                raise ValueError('registry_url_invalid')
            if url_counts.get(_url_key(url)) != 1:
                raise ValueError('registry_url_identity_not_unique')
            if not isinstance(proof, dict) or not isinstance(proof.get('source_id'), str):
                raise ValueError('source_proof_identity_missing')
            sources = [source for source in source_reports
                       if source.get('source_id') == proof['source_id']]
            if not sources:
                entry['reason'] = 'source_not_present'
                continue
            if len(sources) != 1:
                raise ValueError('source_identity_not_unique')
            source = sources[0]
            inventory = [item for item in parsed.collected_sources if item.get('source_id') == proof['source_id']]
            if len(inventory) != 1:
                raise ValueError('registered_source_identity_not_unique')
            citation = parsed.reference_to_citation.get(proof['source_id'])
            current = parsed.reference_records.get(citation, {})
            if (not _url_key(url) or _url_key(source.get('url')) != _url_key(url)
                    or _url_key(inventory[0].get('url')) != _url_key(url)
                    or _url_key(current.get('url')) != _url_key(url)):
                raise ValueError('source_or_registered_reference_url_mismatch')
            excerpt = source.get('excerpt')
            if (not isinstance(excerpt, str) or sha256(excerpt.encode()).hexdigest()
                    != proof.get('excerpt_sha256')):
                raise ValueError('source_excerpt_sha256_mismatch')
            fields = proof.get('fields')
            supplied = set(record) - _DESCRIPTORS - {'source_proof'}
            if not isinstance(fields, dict) or not fields or set(fields) != supplied or not supplied <= _FIELDS:
                raise ValueError('unverified_field_or_citation_identity')
            for field in fields:
                if not isinstance(fields[field], dict):
                    raise ValueError('field_proof_invalid')
                _literal_value(field, record[field], fields[field], excerpt)
            entry.update(proof_verified=True, citation_key=citation, excerpt_sha256=proof['excerpt_sha256'])
            candidate_years = {_year(record[field]) for field in fields if field in {'year', 'publication_date'}} - {None}
            existing_years = {_year(current.get(field)) for field in ('year', 'publication_date')} - {None}
            unknown_existing_date = any(not _missing(current.get(field)) and _year(current.get(field)) is None
                                        for field in ('year', 'publication_date'))
            date_conflict = (len(candidate_years) > 1 or bool(candidate_years) and (
                unknown_existing_date or any(year not in candidate_years for year in existing_years)))
            accepted = {}
            for field in fields:
                old, new = current.get(field), record[field]
                reason = None
                if field in {'year', 'publication_date'} and date_conflict:
                    status, reason = 'conflict', 'publication_year_date_conflict'
                elif _text(old) == _text(new):
                    status = 'unchanged'
                elif _missing(old) or field == 'title' and _text(old) in new:
                    accepted[field], status = deepcopy(new), 'applied'
                else:
                    status = 'conflict'
                entry['fields'].append({'field': field, 'old_value': deepcopy(old), 'candidate_value': deepcopy(new),
                    'status': status, 'reason': reason, 'proof': deepcopy(fields[field])})
            conflicts = any(field['status'] == 'conflict' for field in entry['fields'])
            entry['status'] = ('partial' if conflicts else 'applied') if accepted else (
                'conflict' if conflicts else 'unchanged')
            if accepted:
                overrides[url] = {**accepted, 'metadata_source': source['url'],
                    'metadata_basis': 'Literal saved original spans verified against source identity and excerpt SHA256.'}
        except (ValueError, TypeError, KeyError) as exc:
            entry['reason'] = str(exc)
    return overrides, audit
