"""Record the real OW graph with explicit synthetic model/report/Quality boundaries.

This is a control-flow smoke test, not live research or report-quality approval.
Do not submit its fake report bytes as a PDF or reuse its verdict as a real score.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def strip_payload(run):
    """Keep only graph topology, labels, timestamps and safe tags for upload."""
    run.inputs = {}
    run.outputs = {} if run.outputs is not None else None
    run.extra = {}
    run.serialized = {}
    run.events = []
    if run.error:
        run.error = 'Control test failed; details retained locally.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--project', default='SKALA-7-2-Agent')
    args = parser.parse_args()
    from dotenv import dotenv_values
    from langsmith import Client
    from langsmith.utils import LangSmithNotFoundError
    from langchain_core.tracers.langchain import LangChainTracer, wait_for_all_tracers
    from pipeline.graph import PipelineContext, build_graph, initial_state
    from pipeline.inputs import load_inputs
    from pipeline.research_input import load_saved_research
    from pipeline.tests.test_orchestration import OfflineBoundaries, TARGET

    settings = dotenv_values(args.env_file)
    key = settings.get('LANGSMITH_API_KEY') or settings.get('LANGCHAIN_API_KEY')
    if not key:
        raise SystemExit('Missing LangSmith API key; key values are never printed.')
    # Explicit callback avoids duplicate global tracers. The user's file is not changed.
    os.environ['LANGCHAIN_TRACING_V2'] = 'false'
    os.environ['LANGSMITH_TRACING'] = 'false'
    # Only control-flow timing/names/IDs/tags leave the workspace. No source text,
    # result payloads, State body, credentials or runtime-machine metadata is sent.
    client = Client(api_key=key, api_url='https://api.smith.langchain.com',
        hide_inputs=True, hide_outputs=True, hide_metadata=True,
        omit_traced_runtime_info=True)
    assert client._hide_run_inputs({'private_test_marker': 'never-send'}) == {}
    assert client._hide_run_outputs({'private_test_marker': 'never-send'}) == {}
    guard = SimpleNamespace(inputs={'private': 'never-send'}, outputs={'private': 'never-send'},
        extra={'runtime': 'never-send', 'metadata': 'never-send'}, serialized={'private': 'never-send'},
        events=[{'private': 'never-send'}], error='private traceback')
    strip_payload(guard)
    assert guard.inputs == guard.outputs == guard.extra == guard.serialized == {}
    assert guard.events == [] and 'private' not in guard.error

    sent_ids = set()

    class PayloadFreeTracer(LangChainTracer):
        # The parent inserts runtime metadata itself, so sanitize before both writes.
        def _persist_run_single(self, run):
            if run.extra.get('__disabled'):
                return
            run.tags = self._get_tags(run)
            strip_payload(run)
            run.ls_client = self.client
            run.post()
            sent_ids.add(run.id)

        def _update_run_single(self, run):
            if run.extra.get('__disabled'):
                return
            strip_payload(run)
            run.ls_client = self.client
            run.patch()

    tracer = PayloadFreeTracer(client=client, project_name=args.project)
    request, _, saved, mode = load_inputs(ROOT / 'config/pipeline.json')
    assert mode == 'saved'
    bundle = load_saved_research(saved)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace_id = uuid4()
    evaluation_id = f'offline-control-{trace_id.hex[:12]}'
    fixture = OfflineBoundaries(routes=('report_repair', 'upstream_replan', 'passed'))
    context = PipelineContext(output_dir=output, bundle=deepcopy(bundle),
        request=deepcopy(request), run_id=evaluation_id, as_of='2026-10-07',
        model='offline-synthetic-fixture', draft=True,
        planner=fixture.planner, worker=fixture.worker, trl=fixture.trl,
        review=fixture.review, report=fixture.report, quality=fixture.quality)
    graph = build_graph(context)
    with patch('team_review.review.call_trl_grounding',
               side_effect=AssertionError('No live TRL audit allowed in this smoke test')):
        result = graph.invoke(initial_state(context), {
            'run_id': trace_id, 'run_name': 'OFFLINE CONTROL TEST - synthetic providers and Quality',
            'callbacks': [tracer], 'max_concurrency': 3, 'recursion_limit': 60,
            'tags': ['skala-7-2', 'offline-control-test', 'not-live-report',
                     'payloads-hidden', f'evaluation-run:{evaluation_id}'],
            'metadata': {'evaluation_run_id': evaluation_id,
                'offline_test_only': True, 'model_outputs_synthetic': True,
                'quality_verdict_synthetic': True, 'real_report_quality_pass': False,
                'purpose': 'Verify real graph fan-out, report repair, scoped replan, join and termination'},
        })
    assert result['phase'] == 'content_quality_pass'  # Synthetic verdict only.
    assert len(fixture.workers) == 4
    assert fixture.workers[-1]['role'] == TARGET['role']
    assert fixture.workers[-1]['active_cells'] == [{k: v for k, v in TARGET.items() if k != 'role'}]
    assert len(fixture.reports) == len(fixture.qualities) == 3
    wait_for_all_tracers()
    client.flush()
    receipt = {
        'schema_version': 'traced-control-smoke-v1',
        'evaluation_run_id': evaluation_id, 'langsmith_trace_id': str(trace_id),
        'langsmith_run_url': None, 'remote_verified': False,
        'offline_test_only': True, 'model_outputs_synthetic': True,
        'quality_verdict_synthetic': True, 'real_report_quality_pass': False,
        'trace_input_output_metadata_hidden': True,
        'llm_search_calls': 0, 'initial_worker_count': 3, 'total_worker_count': 4,
        'scoped_replan_cells': fixture.workers[-1]['active_cells'],
        'report_boundary_calls': len(fixture.reports), 'quality_boundary_calls': len(fixture.qualities),
        'routes': fixture.routes, 'phase': result['phase'],
        'note': 'Real LangGraph execution; fixture verdict is not approval of the editorial PDF.',
    }
    receipt_path = output / 'trace.receipt.json'
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    def walk(run):
        yield run
        for child in run.child_runs or []:
            yield from walk(child)

    # Both root and descendants are indexed asynchronously.
    for attempt in range(6):
        try:
            run = client.read_run(trace_id, load_child_runs=True)
            uploaded = list(walk(run))
            if sent_ids.issubset({r.id for r in uploaded}):
                break
        except LangSmithNotFoundError:
            if attempt == 5:
                raise
        if attempt == 5:
            raise RuntimeError('Descendant indexing incomplete; receipt remains unverified.')
        time.sleep(2)
    # LangSmith adds a numeric depth field server-side; this is topology, not payload.
    assert all(not r.inputs and not r.outputs for r in uploaded)
    assert all(set((r.extra or {}).keys()) <= {'metadata'} and
        set((r.extra or {}).get('metadata', {}).keys()) <= {'ls_run_depth'} and
        isinstance((r.extra or {}).get('metadata', {}).get('ls_run_depth', 0), int)
        for r in uploaded)
    receipt.update(langsmith_run_url=client.get_run_url(run=run, project_name=args.project),
        remote_verified=True, uploaded_run_count=len(uploaded),
        expected_run_count=len(sent_ids),
        remote_payload_check='inputs/outputs empty; extra contains only server-added numeric run depth; all callback run IDs verified')
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
