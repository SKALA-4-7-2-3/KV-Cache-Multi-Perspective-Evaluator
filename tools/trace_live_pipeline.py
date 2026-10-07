"""Run the unchanged real pipeline with payload-free LangSmith callbacks.

Pass ordinary pipeline CLI arguments, including --env-file and --output.
--trace-project optionally selects the LangSmith project. No providers are mocked.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from langchain_core.tracers.langchain import LangChainTracer
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import tracing_context

SAFE_ERROR = 'Pipeline run failed; details retained locally.'


class PayloadFreeTracer(LangChainTracer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent_ids = set()

    def _clean(self, run):
        run.inputs, run.outputs, run.extra, run.serialized, run.events = {}, {}, {}, {}, []
        run.error = SAFE_ERROR if run.error else None
        run.tags = list(self.tags)
        run.ls_client = self.client

    def _persist_run_single(self, run):
        # Ambient tracing is disabled; this explicitly supplied sanitized tracer is allowed.
        self.sent_ids.add(run.id)
        self._clean(run)
        run.post()

    def _update_run_single(self, run):
        self._clean(run)
        run.patch()


def call_delta(before, after):
    calls = {k: v for k, v in after.get('calls', {}).items() if k not in before.get('calls', {})}
    return {'call_ids': sorted(calls),
        'counts': {kind: sum(c.get('kind') == kind for c in calls.values())
                   for kind in ('llm', 'search', 'extract', 'fetch')},
        'actual_tokens': sum(c['actual_tokens'] for c in calls.values()
                             if c.get('kind') == 'llm' and type(c.get('actual_tokens')) is int),
        'unconfirmed_reserved_tokens': sum(c.get('reserved_tokens', 0) for c in calls.values()
            if c.get('kind') == 'llm' and c.get('actual_tokens') is None),
        'failed_calls': sum(c.get('status') == 'failed' for c in calls.values()),
        'successful_llm_by_task': {task: sum(c.get('task_id') == task and c.get('kind') == 'llm'
            and c.get('status') == 'finished' for c in calls.values())
            for task in sorted({c.get('task_id', 'pipeline') for c in calls.values()})},
        'by_task': {task: {kind: sum(c.get('task_id') == task and c.get('kind') == kind
                                   for c in calls.values())
                          for kind in ('llm', 'search', 'extract', 'fetch')}
                    for task in sorted({c.get('task_id', 'pipeline') for c in calls.values()})}}


def artifact_receipt(context, state, delta, event_offset=0):
    """Verify actual references/files; distinguish accepted cached output from new API work."""
    result = {'accepted_report_quality_pass': False, 'live_report_quality_pass': False, 'stages': {}}
    events = context.output_dir / 'events.jsonl'
    stages = {}
    if events.exists():
        with events.open('rb') as stream:
            stream.seek(event_offset)
            stages = {e['name']: e['reused'] for line in stream for e in [json.loads(line)]
                      if e.get('event') == 'stage'}
    report, quality = None, None
    for kind in ('report', 'quality'):
        ref = state.get(kind + '_ref')
        if not ref:
            continue
        value = context.store.get(ref)
        result[kind + '_ref'] = ref
        stage_ref = value.get('controller', {}).get('base_quality_ref', ref)
        if stage_ref != ref:
            context.store.get(stage_ref)
        stage = '-'.join(Path(stage_ref['relative_path']).name.split('-')[:2])
        result['stages'][kind] = {'stage': stage, 'reused': stages.get(stage),
            'new_successful_llm_calls': delta.get('successful_llm_by_task', {}).get(stage, 0)}
        if kind == 'report':
            report = value
            result['files'] = {}
            for file_kind in ('tex', 'pdf'):
                path = Path(value[file_kind + '_path'])
                actual = sha256(path.read_bytes()).hexdigest()
                if actual != value.get(file_kind + '_sha256'):
                    raise ValueError('Final report bytes differ from the stored hash')
                result['files'][file_kind] = {'path': str(path), 'sha256': actual}
        else:
            quality = value
            result['quality'] = {'route': value.get('route'), 'weighted_score': value.get('weighted_score'),
                'gates': {name: gate['status'] for name, gate in value.get('gates', {}).items()},
                'hashes': value.get('hashes', {})}
    gates = (quality or {}).get('gates', {})
    required = {*(f'H{n}' for n in range(1, 8)), 'all_checks_completed'}
    accepted = bool(report and quality and state.get('phase') == 'content_quality_pass'
        and quality.get('route') == 'passed' and required.issubset(gates)
        and all(gate.get('status') == 'pass' for gate in gates.values())
        and all(quality.get('hashes', {}).get(k) == result['files'][k]['sha256'] for k in ('pdf', 'tex')))
    result['accepted_report_quality_pass'] = accepted
    result['live_report_quality_pass'] = bool(accepted and all(
        s['reused'] is False and s['new_successful_llm_calls'] > 0 for s in result['stages'].values()))
    return result


def verify_remote(client, trace_id, sent_ids, *, timeout=30):
    """Bound foreground verification, including flush and all server reads."""
    result = queue.Queue()
    deadline = time.monotonic() + min(30, timeout)

    def verify():
        from langsmith.utils import LangSmithNotFoundError
        def walk(run):
            yield run
            for child in run.child_runs or []:
                yield from walk(child)
        try:
            wait_for_all_tracers()
            client.flush(timeout=max(0, min(5, deadline - time.monotonic())))
            while time.monotonic() < deadline:
                try:
                    run = client.read_run(trace_id, load_child_runs=True)
                    uploaded = list(walk(run))
                    if sent_ids and sent_ids.issubset({r.id for r in uploaded}) and all(r.end_time for r in uploaded):
                        for item in uploaded:
                            extra = item.extra or {}
                            metadata = extra.get('metadata', {})
                            if (item.inputs or item.outputs or item.serialized or item.events
                                or (item.error and item.error != SAFE_ERROR)
                                or set(extra) - {'metadata'} or set(metadata) - {'ls_run_depth'}
                                or type(metadata.get('ls_run_depth', 0)) is not int):
                                raise ValueError('Remote trace contains an unexpected payload field')
                        result.put({'remote_verified': True, 'uploaded_run_count': len(uploaded),
                            'expected_run_count': len(sent_ids),
                            'langsmith_run_url': client.get_run_url(run=run)})
                        return
                except LangSmithNotFoundError:
                    pass
                time.sleep(max(0, min(.2, deadline - time.monotonic())))
            raise TimeoutError('Remote trace indexing incomplete')
        except Exception as exc:
            result.put(exc)

    threading.Thread(target=verify, daemon=True).start()
    try:
        value = result.get(timeout=max(.001, deadline - time.monotonic()))
    except queue.Empty:
        raise TimeoutError('Remote trace verification deadline reached') from None
    if isinstance(value, Exception):
        raise value
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--trace-project')
    options, forwarded = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    preview = argparse.ArgumentParser(add_help=False)
    preview.add_argument('--output', type=Path)
    output = preview.parse_known_args(forwarded)[0].output
    from langsmith import Client
    import dotenv
    from pipeline import __main__ as cli, governance, graph as graph_module
    original = graph_module.build_graph
    receipt = {'schema_version': 'traced-live-pipeline-v1', 'provider': 'not_selected',
        'offline_test_only': False, 'graph_invoked': False, 'remote_verified': False,
        'real_report_quality_pass': False, 'langsmith_trace_id': None, 'status': 'not_invoked'}
    captured = {}
    tracing_keys = ('LANGCHAIN_TRACING_V2', 'LANGSMITH_TRACING', 'LANGSMITH_TRACING_V2')
    prior_env = {key: os.environ.get(key) for key in tracing_keys}
    original_load = dotenv.load_dotenv

    def disable_ambient():
        for name in tracing_keys:
            os.environ[name] = 'false'

    def load_env(*args, **kwargs):
        try:
            return original_load(*args, **kwargs)
        finally:
            disable_ambient()

    def save_receipt():
        if output is not None and output.exists():
            try:
                cli.save(output / 'live.trace.receipt.json', receipt)
            except Exception as exc:
                receipt['receipt_write_error_type'] = type(exc).__name__

    def factory(context, checkpoint=None):
        nonlocal output
        output = context.output_dir
        # The real CLI has already loaded --env-file. Disable default callbacks now.
        disable_ambient()
        key = os.getenv('LANGSMITH_API_KEY') or os.getenv('LANGCHAIN_API_KEY')
        if not key:
            raise RuntimeError('Missing LangSmith API key')
        project = options.trace_project or os.getenv('LANGSMITH_PROJECT') or os.getenv('LANGCHAIN_PROJECT') or 'SKALA-Live-Pipeline'
        client = Client(api_key=key, api_url=os.getenv('LANGSMITH_ENDPOINT') or os.getenv('LANGCHAIN_ENDPOINT')
                        or 'https://api.smith.langchain.com', hide_inputs=True, hide_outputs=True,
                        hide_metadata=True, omit_traced_runtime_info=True, timeout_ms=(1000, 2000))
        tracer = PayloadFreeTracer(client=client, project_name=project,
            tags=['kv-cache', 'live-model', 'payloads-hidden', f'evaluation-run:{context.run_id}'])
        compiled, ledger = original(context, checkpoint), governance._ledger
        captured.update(client=client, tracer=tracer, ledger=ledger, context=context, event_offset=0)
        receipt.update(provider=os.getenv('KV_MODEL_PROVIDER', 'openai_api'),
            evaluation_run_id=context.run_id, model=context.model,
            report_model=context.report_model or context.model, judge_model=context.judge_model or context.model)

        class Proxy:
            def __getattr__(self, name):
                return getattr(compiled, name)

            def invoke(self, inputs, configuration, **kwargs):
                trace_id = uuid4()
                receipt.update(graph_invoked=True, langsmith_trace_id=str(trace_id), status='running')
                before = ledger.snapshot()
                events = output / 'events.jsonl'
                captured['event_offset'] = events.stat().st_size if events.exists() else 0
                save_receipt()
                config = {**configuration, 'run_id': trace_id, 'callbacks': [tracer],
                          'run_name': live_run_name(receipt['provider']), 'tags': tracer.tags}
                try:
                    state = compiled.invoke(inputs, config, **kwargs)
                    receipt.update(status='completed', phase=state.get('phase'),
                                   termination_reason=state.get('termination_reason'))
                    captured['state'] = state
                    return state
                except Exception:
                    receipt['status'] = 'failed'
                    raise
                finally:
                    receipt['live_call_delta'] = call_delta(before, ledger.snapshot())
                    save_receipt()
        return Proxy()

    code = 1
    try:
        disable_ambient()
        with tracing_context(enabled=False, parent=False), patch.object(dotenv, 'load_dotenv', load_env), \
             patch.object(graph_module, 'build_graph', factory), patch.object(sys, 'argv', [sys.argv[0], *forwarded]):
            code = cli.main()
    except SystemExit as exc:
        code = exc.code if type(exc.code) is int else 1
        if code:
            receipt['status'] = 'failed'
    except KeyboardInterrupt:
        code, receipt['status'] = 130, 'interrupted'
    except Exception as exc:
        receipt.update(status='failed', pipeline_error_type=type(exc).__name__)
    finally:
        receipt['pipeline_exit_code'] = code
        if output is not None:
            try:
                provenance = output / 'codex.calls.jsonl'
                if provenance.is_file():
                    receipt['provider_provenance_ref'] = {'path': str(provenance),
                        'sha256': sha256(provenance.read_bytes()).hexdigest(),
                        'media_type': 'application/x-ndjson'}
            except OSError as exc:
                receipt['provenance_error_type'] = type(exc).__name__
        if captured.get('context'):
            try:
                state = captured.get('state')
                if state is None and code in (0, 2):
                    manifest = json.loads((output / 'run.json').read_text())
                    state = captured['context'].store.get(manifest['state_ref'])
                if state is not None:
                    receipt.update(artifact_receipt(captured['context'], state,
                        receipt.get('live_call_delta', {}), captured['event_offset']))
            except Exception as exc:
                receipt['artifact_error_type'] = type(exc).__name__
        save_receipt()
        if receipt['graph_invoked']:
            try:
                receipt.update(verify_remote(captured['client'], receipt['langsmith_trace_id'],
                                             captured['tracer'].sent_ids))
            except Exception as exc:
                receipt['trace_error_type'] = type(exc).__name__
        receipt['real_report_quality_pass'] = bool(code == 0 and receipt['graph_invoked']
            and receipt.get('live_report_quality_pass'))
        save_receipt()
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
        for key, value in prior_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return code


def live_run_name(provider):
    label = 'Codex' if provider == 'codex_cli_chatgpt' else 'API'
    return f'LIVE {label} - KV-Cache Orchestrator-Workers'


if __name__ == '__main__':
    raise SystemExit(main())
