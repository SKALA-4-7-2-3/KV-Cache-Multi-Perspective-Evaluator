from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tools.trace_live_pipeline import PayloadFreeTracer, artifact_receipt, call_delta, live_run_name, main, verify_remote


def test_trace_writes_never_include_private_payload_or_runtime():
    writes = []
    run = SimpleNamespace(id=uuid4(), inputs={'private': 'PRIVATE_MARKER'},
        outputs={'private': 'PRIVATE_MARKER'}, extra={'runtime': 'PRIVATE_MARKER'},
        serialized={'private': 'PRIVATE_MARKER'}, events=['PRIVATE_MARKER'],
        error='PRIVATE_MARKER traceback', tags=['PRIVATE_MARKER'], ls_client=None)
    run.post = lambda: writes.append(deepcopy({k: v for k, v in vars(run).items()
                                              if k not in {'post', 'patch', 'ls_client'}}))
    run.patch = run.post
    tracer = PayloadFreeTracer(client=object(), project_name='test', tags=['safe'])
    tracer._persist_run_single(run)
    run.inputs = {'private': 'PRIVATE_MARKER'}
    run.outputs = {'private': 'PRIVATE_MARKER'}
    run.extra = {'metadata': 'PRIVATE_MARKER', 'runtime': 'PRIVATE_MARKER'}
    run.events = ['PRIVATE_MARKER']
    tracer._update_run_single(run)
    assert len(writes) == 2
    assert 'PRIVATE_MARKER' not in repr(writes)
    assert all(w['tags'] == ['safe'] for w in writes)
    assert tracer.sent_ids == {run.id}


def test_live_trace_name_matches_actual_model_provider():
    assert live_run_name('codex_cli_chatgpt') == 'LIVE Codex - KV-Cache Orchestrator-Workers'
    assert live_run_name('openai_api') == 'LIVE API - KV-Cache Orchestrator-Workers'


def test_call_delta_counts_only_new_actual_calls_and_preserves_unknown_tokens():
    before = {'calls': {'old': {'kind': 'llm', 'actual_tokens': 999}}}
    after = {'calls': {**before['calls'],
        'a': {'kind': 'llm', 'actual_tokens': 7, 'status': 'finished', 'task_id': 'plan'},
        'b': {'kind': 'llm', 'actual_tokens': None, 'reserved_tokens': 13,
              'status': 'failed', 'task_id': 'report'},
        'c': {'kind': 'search', 'actual_tokens': None, 'status': 'finished', 'task_id': 'market'}}}
    result = call_delta(before, after)
    assert result['counts'] == {'llm': 2, 'search': 1, 'extract': 0, 'fetch': 0}
    assert result['actual_tokens'] == 7 and result['unconfirmed_reserved_tokens'] == 13
    assert result['failed_calls'] == 1 and result['call_ids'] == ['a', 'b', 'c']


def test_remote_verification_checks_grandchildren_and_rejects_payload():
    grandchild = SimpleNamespace(id=uuid4(), inputs={'private': 'PRIVATE_MARKER'},
        outputs={}, extra={}, serialized=None, events=[], error=None,
        end_time='done', child_runs=[])
    child = SimpleNamespace(**{**vars(grandchild), 'id': uuid4(), 'inputs': {},
                               'child_runs': [grandchild]})
    root = SimpleNamespace(**{**vars(child), 'id': uuid4(), 'child_runs': [child]})
    client = SimpleNamespace(flush=lambda **kw: None,
        read_run=lambda *a, **kw: root, get_run_url=lambda **kw: 'safe-url')
    with pytest.raises(ValueError, match='payload'):
        verify_remote(client, root.id, {root.id, child.id, grandchild.id}, timeout=.2)


def test_remote_verification_requires_every_sent_id_without_waiting_forever():
    root = SimpleNamespace(id=uuid4(), inputs={}, outputs={}, extra={},
        serialized=None, events=[], error=None, end_time='done', child_runs=[])
    client = SimpleNamespace(flush=lambda **kw: None,
        read_run=lambda *a, **kw: root, get_run_url=lambda **kw: 'safe-url')
    with pytest.raises(TimeoutError):
        verify_remote(client, root.id, {root.id, uuid4()}, timeout=.02)


def test_remote_flush_waits_for_callback_ids_before_subset_check(monkeypatch):
    import tools.trace_live_pipeline as wrapper
    root = SimpleNamespace(id=uuid4(), inputs={}, outputs={}, extra={},
        serialized=None, events=[], error=None, end_time='done', child_runs=[])
    expected = {root.id}
    order = []
    def wait():
        order.append('callbacks')
        expected.add(uuid4())
    monkeypatch.setattr(wrapper, 'wait_for_all_tracers', wait)
    client = SimpleNamespace(flush=lambda **kw: order.append('flush'),
        read_run=lambda *a, **kw: root, get_run_url=lambda **kw: 'safe-url')
    with pytest.raises(TimeoutError):
        verify_remote(client, root.id, expected, timeout=.02)
    assert order == ['callbacks', 'flush']


def test_remote_verification_accepts_only_numeric_server_depth():
    root = SimpleNamespace(id=uuid4(), inputs={}, outputs={}, extra={'metadata': {'ls_run_depth': 0}},
        serialized=None, events=[], error=None, end_time='done', child_runs=[])
    client = SimpleNamespace(flush=lambda **kw: None,
        read_run=lambda *a, **kw: root, get_run_url=lambda **kw: 'safe-url')
    assert verify_remote(client, root.id, {root.id}, timeout=.2)['uploaded_run_count'] == 1
    root.extra['metadata']['ls_run_depth'] = 'PRIVATE_MARKER'
    with pytest.raises(ValueError, match='payload'):
        verify_remote(client, root.id, {root.id}, timeout=.2)


def test_ambient_disabled_still_allows_only_explicit_sanitized_callback(monkeypatch):
    from langsmith import tracing_context
    from langsmith.run_trees import RunTree
    from langsmith.utils import tracing_is_enabled
    from langchain_core.tracers.langchain import wait_for_all_tracers
    writes = []
    def send(run, *args, **kwargs):
        writes.append({k: deepcopy(getattr(run, k)) for k in
                       ('inputs', 'outputs', 'serialized', 'events', 'extra', 'error', 'tags')})
    monkeypatch.setattr(RunTree, 'post', send)
    monkeypatch.setattr(RunTree, 'patch', send)
    tracer = PayloadFreeTracer(client=object(), project_name='test', tags=['safe'])
    with tracing_context(enabled=True):
        with tracing_context(enabled=False, parent=False):
            assert not tracing_is_enabled()
            run_id = uuid4()
            tracer.on_chain_start({'secret': 'PRIVATE_MARKER'}, {'secret': 'PRIVATE_MARKER'},
                                  run_id=run_id, metadata={'secret': 'PRIVATE_MARKER'})
            tracer.on_chain_end({'secret': 'PRIVATE_MARKER'}, run_id=run_id)
            wait_for_all_tracers()
        assert tracing_is_enabled()
    assert len(writes) == 2 and tracer.sent_ids == {run_id}
    assert 'PRIVATE_MARKER' not in repr(writes)


@pytest.mark.parametrize('args,code,status', [(['--help'], 0, 'not_invoked'),
    (['--no-such-option'], 2, 'failed')])
def test_original_cli_help_and_error_codes_are_preserved(args, code, status, capsys, monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING_V2', 'true')
    assert main(args) == code
    receipt = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert receipt['status'] == status and receipt['pipeline_exit_code'] == code
    assert receipt['graph_invoked'] is False and receipt['real_report_quality_pass'] is False
    assert receipt['langsmith_trace_id'] is None
    import os
    assert os.environ['LANGSMITH_TRACING_V2'] == 'true'


def report_fixture(tmp_path):
    from pipeline.artifacts import ArtifactStore
    store = ArtifactStore(tmp_path)
    files = {}
    for kind in ('pdf', 'tex'):
        path = tmp_path / ('report.' + kind)
        path.write_bytes(b'local integrity fixture')
        files[kind + '_path'], files[kind + '_sha256'] = str(path), sha256(path.read_bytes()).hexdigest()
    report = store.put('artifacts/report-1-hash.json', files)
    base = store.put('artifacts/quality-1-hash.json', {})
    quality = store.put('quality/controller-1.json', {'controller': {'base_quality_ref': base},
        'route': 'passed', 'gates': {k: {'status': 'pass'} for k in
                                   ['H1','H2','H3','H4','H5','H6','H7','all_checks_completed']},
        'hashes': {k: files[k + '_sha256'] for k in ('pdf', 'tex')}})
    for name in ('report-1', 'quality-1'):
        store.event('stage', name=name, reused=False)
    return SimpleNamespace(store=store, output_dir=tmp_path), {
        'phase': 'content_quality_pass', 'report_ref': report, 'quality_ref': quality}


def test_cached_quality_or_only_planner_calls_never_claim_live_report_pass(tmp_path):
    context, state = report_fixture(tmp_path)
    result = artifact_receipt(context, state, {'successful_llm_by_task': {'plan': 1}})
    assert result['accepted_report_quality_pass'] is True
    assert result['live_report_quality_pass'] is False
    result = artifact_receipt(context, state, {'successful_llm_by_task': {'report-1': 1, 'quality-1': 2}})
    assert result['live_report_quality_pass'] is True
    context.store.event('stage', name='quality-1', reused=True)
    result = artifact_receipt(context, state, {'successful_llm_by_task': {'report-1': 1, 'quality-1': 2}})
    assert result['live_report_quality_pass'] is False


def test_receipt_rejects_changed_report_bytes_even_with_passed_quality(tmp_path):
    context, state = report_fixture(tmp_path)
    (tmp_path / 'report.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError, match='stored hash'):
        artifact_receipt(context, state, {})


def test_dotenv_cannot_reenable_ambient_before_real_prepare(tmp_path, monkeypatch, capsys):
    import os
    from pipeline import inputs
    from langsmith import tracing_context
    from langsmith.utils import tracing_is_enabled
    flags = ('LANGCHAIN_TRACING_V2', 'LANGSMITH_TRACING', 'LANGSMITH_TRACING_V2')
    env = tmp_path / '.env'
    env.write_text('\n'.join(key + '=true' for key in flags))
    original = inputs.load_inputs
    checked = []
    def load(*args, **kwargs):
        checked.append(True)
        assert not tracing_is_enabled()
        assert all(os.environ[key] == 'false' for key in flags)
        return original(*args, **kwargs)
    monkeypatch.setattr(inputs, 'load_inputs', load)
    with tracing_context(enabled=True):
        assert main(['--stop-after', 'prepare', '--env-file', str(env),
                     '--output', str(tmp_path / 'prepared')]) == 0
        assert tracing_is_enabled()
    assert checked == [True]
    receipt = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert receipt['graph_invoked'] is False and receipt['real_report_quality_pass'] is False


def test_receipt_references_final_codex_provenance_bytes_without_payload(tmp_path, capsys):
    provenance = tmp_path / 'codex.calls.jsonl'
    body = b'{"thread_id":"PRIVATE_MARKER"}\n'
    provenance.write_bytes(body)
    assert main(['--help', '--output', str(tmp_path)]) == 0
    receipt = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert receipt['provider_provenance_ref'] == {'path': str(provenance),
        'sha256': sha256(body).hexdigest(), 'media_type': 'application/x-ndjson'}
    assert 'PRIVATE_MARKER' not in repr(receipt)
    assert receipt['graph_invoked'] is False and receipt['real_report_quality_pass'] is False
