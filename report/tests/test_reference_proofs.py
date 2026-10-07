"""Only literal source metadata may enrich the report's reference view."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from report_agent.reference_proofs import legacy_reference_metadata, verify_reference_metadata


def fixture():
    excerpt = 'Full exact title\nAda Lovelace, Grace Hopper\nAugust 05, 2026\n2026'
    source = {'source_id': 'source-one', 'citation_key': 'WEB_one',
              'url': 'https://example.test/article', 'excerpt': excerpt}
    values = {'title': 'Full exact title', 'authors_or_organization': ['Ada Lovelace', 'Grace Hopper'],
              'publication_date': '2026-08-05', 'year': 2026}
    transforms = {'title': 'whitespace', 'authors_or_organization': 'author_list',
                  'publication_date': 'date', 'year': 'year'}
    quotes = {'title': 'Full exact title', 'authors_or_organization': 'Ada Lovelace, Grace Hopper',
              'publication_date': 'August 05, 2026', 'year': '2026'}
    fields = {name: {'transform': transforms[name], 'spans': [{
        'start': excerpt.index(quote), 'end': excerpt.index(quote) + len(quote), 'quote': quote}]}
        for name, quote in quotes.items()}
    registry = {source['url']: {**values, 'source_proof': {
        'source_id': source['source_id'], 'excerpt_sha256': sha256(excerpt.encode()).hexdigest(),
        'fields': fields}}}
    parsed = SimpleNamespace(collected_sources=(source,),
        reference_records={'WEB_one': {'url': source['url'], 'title': 'exact title',
            'authors_or_organization': '미표기', 'publication_date': 'unknown', 'year': None}},
        reference_to_citation={'source-one': 'WEB_one'})
    return registry, parsed


def test_verified_fields_extend_title_and_fill_missing_values_without_mutating_originals():
    registry, parsed = fixture()
    originals = deepcopy((registry, parsed.collected_sources, parsed.reference_records))
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    result = metadata['https://example.test/article']
    assert result['title'] == 'Full exact title'
    assert result['authors_or_organization'] == ['Ada Lovelace', 'Grace Hopper']
    assert result['publication_date'] == '2026-08-05' and result['year'] == 2026
    assert 'source_proof' not in result
    assert audit[0]['status'] == 'applied' and audit[0]['proof_verified'] is True
    assert (registry, parsed.collected_sources, parsed.reference_records) == originals


@pytest.mark.parametrize('change', ['hash', 'offset', 'quote', 'author', 'date', 'year', 'url', 'identity'])
def test_changed_proof_or_value_is_never_merged(change):
    registry, parsed = fixture()
    record = next(iter(registry.values()))
    proof = record['source_proof']
    if change == 'hash': proof['excerpt_sha256'] = '0' * 64
    elif change == 'offset': proof['fields']['title']['spans'][0]['start'] += 1
    elif change == 'quote': proof['fields']['title']['spans'][0]['quote'] = 'Invented title'
    elif change == 'author': record['authors_or_organization'][0] = 'Ada LoveIace'
    elif change == 'date': record['publication_date'] = '2026-08-06'
    elif change == 'year': record['year'] = 2025
    elif change == 'url': parsed.collected_sources[0]['url'] = 'https://example.test/different'
    else: parsed.reference_records['WEB_one']['url'] = 'https://example.test/different'
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata == {} and audit[0]['status'] == 'skipped'
    assert audit[0]['proof_verified'] is False


def test_nonmissing_conflicts_are_skipped_and_audited_not_overwritten():
    registry, parsed = fixture()
    parsed.reference_records['WEB_one'].update(title='Different registered title',
        authors_or_organization='Existing Author', publication_date='2026-01-01')
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata['https://example.test/article'] == {
        'year': 2026, 'metadata_source': 'https://example.test/article',
        'metadata_basis': 'Literal saved original spans verified against source identity and excerpt SHA256.'}
    assert audit[0]['status'] == 'partial'
    assert {field['field'] for field in audit[0]['fields'] if field['status'] == 'conflict'} == {
        'title', 'authors_or_organization', 'publication_date'}
    assert parsed.reference_records['WEB_one']['title'] == 'Different registered title'


@pytest.mark.parametrize('existing', [{'publication_date': '2024-01-01'}, {'year': 2024},
                                     {'publication_date': 'unresolved date'},
                                     {'year': 2026, 'publication_date': '2024-01-01'}])
def test_year_and_publication_date_cannot_conflict_across_fields(existing):
    registry, parsed = fixture()
    parsed.reference_records['WEB_one'].update(existing)
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert 'year' not in metadata['https://example.test/article']
    assert 'publication_date' not in metadata['https://example.test/article']
    time = [field for field in audit[0]['fields'] if field['field'] in {'year', 'publication_date'}]
    assert all(field['status'] == 'conflict' and field['reason'] == 'publication_year_date_conflict' for field in time)
    assert all(parsed.reference_records['WEB_one'][field] == value for field, value in existing.items())


def test_contradictory_literal_years_within_one_source_are_not_resolved_by_guessing():
    registry, parsed = fixture()
    record = next(iter(registry.values()))
    source = parsed.collected_sources[0]
    source['excerpt'] += '\n2025'
    proof = record['source_proof']
    proof['excerpt_sha256'] = sha256(source['excerpt'].encode()).hexdigest()
    record['year'] = 2025
    start = source['excerpt'].rfind('2025')
    proof['fields']['year']['spans'] = [{'start': start, 'end': start + 4, 'quote': '2025'}]
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert 'year' not in metadata['https://example.test/article']
    assert 'publication_date' not in metadata['https://example.test/article']
    assert audit[0]['status'] == 'partial'


def test_year_only_publication_date_preserves_verified_precision_in_canonical_reference():
    from report_agent.references import normalize_reference, format_reference
    registry, parsed = fixture()
    record = next(iter(registry.values()))
    record['publication_date'] = '2026'
    record['source_proof']['fields']['publication_date'] = {
        'transform': 'year_date', 'spans': record['source_proof']['fields']['year']['spans']}
    parsed.reference_records['WEB_one']['publication_date'] = '미표기'
    metadata, _ = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    reference = normalize_reference({**parsed.reference_records['WEB_one'], 'kind': 'paper'}, metadata)
    assert reference['publication_date'] == '2026'
    assert '(2026)' in format_reference(reference) and '2026-08' not in format_reference(reference)


def test_run_specific_proof_absent_elsewhere_is_skipped_but_legacy_behavior_is_preserved():
    registry, parsed = fixture()
    registry['https://example.test/legacy'] = {'title': 'Supplied legacy title', 'metadata_basis': 'Legacy basis'}
    parsed.collected_sources = ()
    legacy = legacy_reference_metadata(registry)
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata == legacy == {'https://example.test/legacy': registry['https://example.test/legacy']}
    assert audit[0]['reason'] == 'source_not_present' and audit[0]['status'] == 'skipped'


def test_proof_cannot_reassign_citation_identity_or_supply_unverified_facts():
    registry, parsed = fixture()
    record = next(iter(registry.values()))
    record['citation_key'] = 'OTHER'
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata == {} and audit[0]['status'] == 'skipped'
    del record['citation_key']
    record['venue_or_site'] = 'Invented conference'
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata == {} and audit[0]['status'] == 'skipped'


def test_duplicate_source_identity_is_not_resolved_by_first_match():
    registry, parsed = fixture()
    parsed.collected_sources = (*parsed.collected_sources, deepcopy(parsed.collected_sources[0]))
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata == {} and audit[0]['reason'] == 'source_identity_not_unique'


def test_actual_inventory_without_excerpt_binds_to_separate_unchanged_original():
    registry, parsed = fixture()
    original = deepcopy(parsed.collected_sources[0])
    parsed.collected_sources = ({k: v for k, v in original.items() if k != 'excerpt'},)
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=[original])
    assert audit[0]['status'] == 'applied' and metadata[original['url']]['title'] == 'Full exact title'
    assert 'excerpt' not in parsed.collected_sources[0]
    parsed.collected_sources[0]['url'] = 'https://example.test/unregistered'
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=[original])
    assert metadata == {} and audit[0]['proof_verified'] is False


def test_malformed_proof_url_is_audited_without_blocking_other_valid_sources():
    registry, parsed = fixture()
    registry['https://[broken'] = deepcopy(next(iter(registry.values())))
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert 'https://example.test/article' in metadata
    assert audit[-1]['status'] == 'skipped' and audit[-1]['reason'] == 'registry_url_invalid'


def test_normal_candidate_preparation_uses_proven_reference_values_not_model_inventions():
    from report_agent.generator import prepare_candidate
    from report_agent.references import normalize_reference
    registry, parsed = fixture()
    metadata, _ = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    parsed.reference_records = {key: normalize_reference(value, metadata) for key, value in parsed.reference_records.items()}
    parsed.metadata = {'render_mode': 'annotated_draft'}
    candidate = r'\begin{document}Body.\cite{WEB_one}\section{REFERENCE}\begin{thebibliography}{9}\bibitem{WEB_one} Invented author, title and date.\end{thebibliography}\end{document}'
    result = prepare_candidate(candidate, parsed)
    assert 'Full exact title' in result and 'Ada Lovelace, Grace Hopper(2026-08-05)' in result
    assert 'Invented author' not in result and r'\cite{WEB_one}' in result


def test_normalized_duplicate_registry_url_cannot_report_applied_then_render_legacy_value():
    from report_agent.references import normalize_reference
    registry, parsed = fixture()
    legacy_url = 'https://example.test/article/'
    registry = {legacy_url: {'title': 'Legacy registered title'}, **registry}
    metadata, audit = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    assert metadata == {legacy_url: registry[legacy_url]}
    assert audit[0]['status'] == 'skipped' and audit[0]['reason'] == 'registry_url_identity_not_unique'
    assert normalize_reference(parsed.reference_records['WEB_one'], metadata)['title'] == 'Legacy registered title'


@pytest.mark.parametrize('registry', [[], {'https://example.test/source': 'invalid record'}])
def test_invalid_legacy_registry_is_rejected_before_any_metadata_is_dropped(registry):
    with pytest.raises(ValueError, match='requires_object_records'):
        legacy_reference_metadata(registry)


def test_metadata_view_changes_reuse_the_original_source_reading_cache(tmp_path, monkeypatch):
    from pipeline.reporting import source_analysis
    from pipeline.tests.test_reporting_source_windows import block, install_reader, markdown_for
    registry, parsed = fixture()
    source = parsed.collected_sources[0]
    calls = []
    install_reader(monkeypatch, calls)
    first = source_analysis(markdown_for([source]), tmp_path, 'same-reader-model')
    cached_bytes = (tmp_path / 'report.source-analysis.json').read_bytes()
    keys_before = {p.name: p.read_bytes() for p in (tmp_path / 'source-readings').glob('*.json')}
    metadata, _ = verify_reference_metadata(registry, parsed, source_reports=parsed.collected_sources)
    second_input = markdown_for([source]) + '\n<!-- REFERENCE_METADATA_JSON\n' + json.dumps(metadata) + '\nEND_REFERENCE_METADATA_JSON -->'
    calls.clear()
    second = source_analysis(second_input, tmp_path, 'same-reader-model')
    assert calls == []
    assert block(first, 'REPORT_SOURCE_ANALYSIS') == block(second, 'REPORT_SOURCE_ANALYSIS')
    assert block(second, 'USABLE_SOURCE_REPORTS') == [source]
    assert (tmp_path / 'report.source-analysis.json').read_bytes() == cached_bytes
    assert {p.name: p.read_bytes() for p in (tmp_path / 'source-readings').glob('*.json')} == keys_before


def test_reference_proof_source_invalidates_only_report_and_quality(tmp_path):
    from pipeline.artifacts import stage_fingerprint
    path = tmp_path / 'report/src/report_agent/reference_proofs.py'
    path.parent.mkdir(parents=True)
    path.write_text('original\n')
    before = {stage: stage_fingerprint(tmp_path, stage) for stage in ('trl', 'review', 'report-1', 'quality-1')}
    path.write_text('changed\n')
    changed = {stage for stage in before if before[stage] != stage_fingerprint(tmp_path, stage)}
    assert changed == {'report-1', 'quality-1'}
