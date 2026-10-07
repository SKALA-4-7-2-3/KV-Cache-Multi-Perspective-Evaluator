"""Offline contracts for complete long-source reading and model-only writing projection."""
from hashlib import sha256
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from pipeline.reporting import (source_analysis, source_windows, validate_windowed_source_reading,
                                writing_source_projection, project_writing_prompt)


def block(markdown, name):
    match = re.search(r'<!-- ' + name + r'_JSON\n([\s\S]*?)\nEND_' + name + '_JSON -->', markdown)
    return json.loads(match.group(1))


def markdown_for(sources):
    return '<!-- USABLE_SOURCE_REPORTS_JSON\n' + json.dumps(sources) + '\nEND_USABLE_SOURCE_REPORTS_JSON -->'


def install_reader(monkeypatch, calls, *, fail_window=None, fail_reduce=False, unrelated=False):
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        @property
        def responses(self): return self
        def parse(self, **kwargs):
            calls.append(kwargs)
            data = json.loads(re.search(r'---[^\n]+---\n([\s\S]*?)\n---END_', kwargs['input']).group(1))
            if 'window_readings' in data:
                choices = data['observation_spans'][-2:]
                value = {'use_in_report': bool(choices), 'observations': [
                    {'source_report': 'Representative source statement.', 'supporting_quote_id': s['id']}
                    for s in choices], 'omission_reason': '' if choices else 'All windows are unrelated.'}
                if fail_reduce:
                    value = {'use_in_report': True, 'observations': [{'source_report': 'Bad reduction',
                                                                     'supporting_quote_id': 'unregistered'}]}
            else:
                source = data.get('source', data)
                index = source.get('coverage_window', {}).get('index')
                if fail_window is not None and index == fail_window:
                    value = {'use_in_report': True, 'observations': [{'source_report': 'Bad',
                        'supporting_quote_id': 'unregistered'}] if 'excerpt_spans' in data else [
                        {'source_report': 'Bad', 'supporting_quote': 'Invented quote'}]}
                else:
                    excerpt = source.get('excerpt', '')
                    value = {'use_in_report': True, 'observations': [{'source_report': 'Source statement.',
                        'supporting_quote': excerpt[:20]}], 'operating_organization_interpretation': 'Conditional.',
                        'market_interpretation': 'Conditional market background.', 'limitations': ['Only this source.'],
                        'omission_reason': '', 'source_id': 'model-reassigned', 'citation_key': 'WRONG'}
                    if unrelated:
                        value.update(use_in_report=False, observations=[], omission_reason='No relevant facts in this window.')
            return SimpleNamespace(output_text=json.dumps(value),
                output_parsed=SimpleNamespace(model_dump=lambda: value))
    monkeypatch.setattr('pipeline.governance.openai_client', lambda **kwargs: Client())


def test_windows_cover_every_character_without_truncating_tail():
    excerpt = 'α' * 60000 + 'β' * 60000 + 'TAIL specific condition.'
    windows = source_windows({'excerpt': excerpt})
    assert ''.join(w['excerpt'] for w in windows) == excerpt
    assert windows[0]['start'] == 0 and windows[-1]['end'] == len(excerpt)
    assert all(0 < len(w['excerpt']) <= 60000 for w in windows)
    assert all(a['end'] == b['start'] for a, b in zip(windows, windows[1:]))
    assert all(w['sha256'] == sha256(w['excerpt'].encode()).hexdigest() for w in windows)


def test_long_source_reads_all_windows_then_reduces_exact_registered_quotes(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls)
    source = {'source_id': 'long', 'citation_key': 'WEB_long', 'title': 'Original title',
              'excerpt': 'A' * 60000 + 'B' * 60000 + 'TAIL specific condition.'}
    result = source_analysis(markdown_for([source]), tmp_path, 'offline-model')
    reading = block(result, 'REPORT_SOURCE_ANALYSIS')[0]
    assert len(calls) == 4 and reading['coverage']['completed'] is True
    assert len(reading['window_readings']) == 3 and len(reading['observations']) <= 2
    assert reading['source_id'] == 'long' and reading['citation_key'] == 'WEB_long'
    assert reading['window_readings'][-1]['reading']['observations'][0]['supporting_quote'].startswith('TAIL')
    assert all(o['supporting_quote'] in source['excerpt'] for o in reading['observations'])
    validate_windowed_source_reading(source, reading)
    source_analysis(markdown_for([source]), tmp_path, 'offline-model')
    assert len(calls) == 4
    assert all('base64' in call['instructions'] for call in calls)
    reading['window_readings'].pop()
    with pytest.raises(ValueError, match='coverage'):
        validate_windowed_source_reading(source, reading)


def test_all_unrelated_windows_are_read_with_explicit_omission_reasons(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls, unrelated=True)
    source = {'source_id': 'menus', 'excerpt': 'x' * 120001}
    reading = block(source_analysis(markdown_for([source]), tmp_path, 'offline-model'), 'REPORT_SOURCE_ANALYSIS')[0]
    assert len(calls) == 4 and reading['use_in_report'] is False and reading['omission_reason']
    assert reading['coverage']['completed'] is True
    assert all(w['reading']['omission_reason'] for w in reading['window_readings'])


def test_bad_reducer_is_repaired_once_and_resume_reuses_all_completed_windows(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls, fail_reduce=True)
    source = {'source_id': 'long', 'excerpt': 'x' * 120001}
    with pytest.raises(ValueError, match='reduction contract failed after two attempts'):
        source_analysis(markdown_for([source]), tmp_path, 'offline-model')
    assert len(calls) == 5 and not (tmp_path / 'report.source-analysis.json').exists()
    install_reader(monkeypatch, calls)
    reading = block(source_analysis(markdown_for([source]), tmp_path, 'offline-model'), 'REPORT_SOURCE_ANALYSIS')[0]
    assert len(calls) == 6 and reading['coverage']['completed'] is True


def test_corrupted_reducer_offset_or_window_hash_cannot_reuse_completed_reading(tmp_path, monkeypatch):
    from copy import deepcopy
    calls = []
    install_reader(monkeypatch, calls)
    source = {'source_id': 'long', 'excerpt': 'x' * 120001}
    reading = block(source_analysis(markdown_for([source]), tmp_path, 'offline-model'), 'REPORT_SOURCE_ANALYSIS')[0]
    changed = deepcopy(reading)
    changed['observations'][0]['supporting_quote_span']['start'] += 1
    with pytest.raises(ValueError, match='registered original window'):
        validate_windowed_source_reading(source, changed)
    changed = deepcopy(reading)
    changed['window_readings'][1]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='coverage'):
        validate_windowed_source_reading(source, changed)


def test_failed_middle_window_never_creates_completed_source_aggregate(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls, fail_window=2)
    source = {'source_id': 'long', 'excerpt': 'A' * 60000 + 'B' * 60000 + 'TAIL'}
    with pytest.raises(ValueError, match='two attempts'):
        source_analysis(markdown_for([source]), tmp_path, 'offline-model')
    assert not (tmp_path / 'report.source-analysis.json').exists()
    assert len(calls) == 3  # First window; second window's original attempt and ID repair.


def test_short_source_success_cache_survives_adding_long_source(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls)
    short = {'source_id': 'short', 'excerpt': 'A short original statement.'}
    source_analysis(markdown_for([short]), tmp_path, 'offline-model')
    source_analysis(markdown_for([short, {'source_id': 'long', 'excerpt': 'x' * 60001}]),
                    tmp_path, 'offline-model')
    assert len(calls) == 4  # Short once; long two windows and one reduce.


def test_projection_preserves_source_reduction_and_original_validator_input(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls)
    source = {'source_id': 'long', 'citation_key': 'WEB_long', 'excerpt': 'x' * 120001}
    original = source_analysis(markdown_for([source]), tmp_path, 'offline-model') + '\nFINAL TRL CONTRACT'
    projection = writing_source_projection(original)
    manifest = block(projection, 'USABLE_SOURCE_REPORTS')[0]
    assert 'excerpt' not in manifest and manifest['excerpt_sha256'] == sha256(source['excerpt'].encode()).hexdigest()
    assert manifest['excerpt_characters'] == 120001 and manifest['source_id'] == 'long'
    projected_reading = block(projection, 'REPORT_SOURCE_ANALYSIS')[0]
    original_reading = block(original, 'REPORT_SOURCE_ANALYSIS')[0]
    assert {k: v for k, v in projected_reading.items() if k != 'window_readings_manifest'} == {
        k: v for k, v in original_reading.items() if k != 'window_readings'}
    assert len(original_reading['window_readings']) == projected_reading['window_readings_manifest']['window_count']
    assert 'FINAL TRL CONTRACT' in projection and source['excerpt'] in original
    prompt = 'PREFIX\n' + original + '\nJSON: ' + json.dumps(original) + '\nEND'
    sent = project_writing_prompt(prompt, original, projection)
    assert source['excerpt'] not in sent and projection in sent
    assert block(original, 'USABLE_SOURCE_REPORTS')[0]['excerpt'] == source['excerpt']


def test_short_source_projection_does_not_change_legacy_prompts():
    original = markdown_for([{'excerpt': 'Short original.'}])
    assert writing_source_projection(original) == original


def test_sibling_revision_reuses_exact_validated_source_caches(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls)
    sources = [{'source_id': 'short-original', 'citation_key': 'WEB_short', 'excerpt': 'Short original statement.'},
               {'source_id': 'long-original', 'citation_key': 'WEB_long', 'excerpt': 'A' * 60000 + 'Actual tail.'}]
    original = markdown_for(sources)
    first_dir, second_dir = tmp_path / 'revision-1', tmp_path / 'revision-2'
    first_dir.mkdir(); second_dir.mkdir()
    first = source_analysis(original, first_dir, 'same-model')
    calls.clear()
    second = source_analysis(original, second_dir, 'same-model')
    assert calls == []
    assert block(first, 'REPORT_SOURCE_ANALYSIS') == block(second, 'REPORT_SOURCE_ANALYSIS')
    assert block(second, 'USABLE_SOURCE_REPORTS') == sources
    assert list((second_dir / 'source-readings').glob('*.json'))


@pytest.mark.parametrize('change', ['model', 'source', 'window_instructions'])
def test_sibling_cache_misses_when_its_exact_contract_changes(tmp_path, monkeypatch, change):
    import pipeline.reporting as reporting
    calls = []
    install_reader(monkeypatch, calls)
    source = {'source_id': 'long-original', 'citation_key': 'WEB_long', 'excerpt': 'A' * 60000 + 'Original tail.'}
    first_dir, second_dir = tmp_path / 'revision-1', tmp_path / 'revision-2'
    first_dir.mkdir(); second_dir.mkdir()
    source_analysis(markdown_for([source]), first_dir, 'same-model')
    calls.clear()
    if change == 'source':
        source = {**source, 'excerpt': 'B' * 60000 + 'Changed tail.'}
    if change == 'window_instructions':
        monkeypatch.setattr(reporting, 'SOURCE_WINDOW_INSTRUCTIONS', reporting.SOURCE_WINDOW_INSTRUCTIONS + 'Changed contract.')
    source_analysis(markdown_for([source]), second_dir, 'new-model' if change == 'model' else 'same-model')
    assert calls


def test_tampered_sibling_cache_fails_closed_without_new_model_calls(tmp_path, monkeypatch):
    calls = []
    install_reader(monkeypatch, calls)
    source = {'source_id': 'long-original', 'citation_key': 'WEB_long', 'excerpt': 'A' * 60000 + 'Original tail.'}
    first_dir, second_dir = tmp_path / 'revision-1', tmp_path / 'revision-2'
    first_dir.mkdir(); second_dir.mkdir()
    source_analysis(markdown_for([source]), first_dir, 'same-model')
    for path in (first_dir / 'source-readings').glob('*.json'):
        value = json.loads(path.read_text())
        if 'window_readings' in value:
            value['window_readings'][0]['sha256'] = 'Wrong original hash'
            path.write_text(json.dumps(value))
            break
    calls.clear()
    with pytest.raises(ValueError, match='coverage'):
        source_analysis(markdown_for([source]), second_dir, 'same-model')
    assert calls == []


def test_generation_sends_projection_but_keeps_original_parser_and_files(tmp_path, monkeypatch):
    from pipeline.reporting import generate_report
    from report_agent import compiler, generator, validator
    fixtures = Path(__file__).resolve().parents[2] / 'report/tests/fixtures'
    calls, sent, validated = [], [], []
    install_reader(monkeypatch, calls)
    source = {'source_id': 'long', 'excerpt': 'FULL ORIGINAL SOURCE\n' + 'x' * 120000}
    original = (fixtures / 'trl-runtime.input.md').read_text() + '\n' + markdown_for([source])
    original = source_analysis(original, tmp_path, 'offline-model')
    candidate = (fixtures / 'trl-runtime.tex').read_text()
    original_validate = validator.validate_latex
    def validate(tex, parsed):
        validated.append(parsed.raw_markdown)
        return original_validate(tex, parsed)
    def respond(self, instructions, prompt):
        sent.append(prompt)
        return candidate
    monkeypatch.setattr(compiler, 'find_latex_compiler', lambda name: 'offline-compiler')
    monkeypatch.setattr(compiler, 'compile_latex', lambda tex, pdf: pdf.write_bytes(b'offline fixture only'))
    monkeypatch.setattr(generator.ReportAgent, '_openai_response', respond)
    monkeypatch.setattr(generator, 'validate_latex', validate)
    monkeypatch.setattr(validator, 'validate_latex', validate)
    result = generate_report(original, tmp_path, model='offline-model', attribution_first=False,
                             source_coverage_repair=False)
    assert sent and 'x' * 120000 not in sent[0] and len(sent[0]) < 100000
    assert validated and all(block(body, 'USABLE_SOURCE_REPORTS')[0]['excerpt'] == source['excerpt']
                             for body in validated)
    assert block((tmp_path / 'report.input.md').read_text(), 'USABLE_SOURCE_REPORTS')[0]['excerpt'] == source['excerpt']
    assert block((tmp_path / 'review.output.md').read_text(), 'USABLE_SOURCE_REPORTS')[0]['excerpt'] == source['excerpt']
    assert 'x' * 120000 not in (tmp_path / 'report.model-input.md').read_text()
    assert result['trl'] == {'SW-01': 4, 'HW-01': None}
