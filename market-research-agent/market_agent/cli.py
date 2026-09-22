"""paper_analysis JSON(1~2개) 또는 기존 MD 입력을 처리하는 CLI."""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from .node import parent_update, run_market
from .parser import InputError, read_input
from .prompts import PROMPT_VERSION
from .providers import FixtureAnalyst, FixtureWeb, OpenAIAnalyst
from .report import render_report
from .tools import ProviderError, TavilyWeb
from .schemas import Limits


def fingerprint(data, mode, model):
    code = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        code.update(path.name.encode())
        code.update(path.read_bytes())
    value = [data.input_hash, data.input_format, str(data.as_of), data.domain, data.limits.model_dump(),
        [(t.id,t.approach,t.name) for t in data.technologies.values()], mode, model, PROMPT_VERSION, code.hexdigest()]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def cache_path(output):
    identity = hashlib.sha256(str(output.resolve()).encode()).hexdigest()
    return Path(__file__).parent / '.cache' / identity


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_run(state, output, key):
    cache = cache_path(output)
    if output.exists():
        raise InputError('output_exists')
    cache.mkdir(parents=True, exist_ok=False)
    (cache / 'sources').mkdir()
    data = state["data"]
    if data.input_format != 'markdown':
        document=([data.source_registry,data.comparison,*data.source_documents] if data.input_format=='technical_bundle_json'
            else (data.source_documents[0] if len(data.source_documents)==1 else data.source_documents))
        (cache/'input.json').write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        (cache / "input.md").write_text(data.raw_markdown, encoding="utf-8")
    for doc_id, body in state["sources"].items():
        if not re.fullmatch(r'[\w-]+', doc_id):
            raise InputError('invalid_document_id')
        (cache / "sources" / f"{doc_id}.md").write_text(body, encoding="utf-8")
    snapshot = {"output_schema_version": '0.5', "fingerprint": key, "created_at": datetime.now(timezone.utc).isoformat(),
        "model": state["model"], "input": data.model_dump(mode="json"),
        "result": state["result"].model_dump(mode="json"),
        "evidence": {k: v.model_dump(mode="json") for k, v in state["evidence"].items()},
        "queries": state["queries"], "events": state["events"],
        "token_usage": state["token_usage"],
        "output_checks": state.get('output_checks', []),
        "claim_pool": {k:v.model_dump(mode='json') for k,v in state.get('claim_pool',{}).items()},
        "candidate_pool": {k:v.model_dump(mode='json') for k,v in state.get('candidate_pool',{}).items()},
        "claim_review_log": state.get('claim_review_log',{}),
        "source_reviews": state.get('reviews',{}),
        "extraction_history": state.get('extraction_history',[]),
        "graph_history": state.get('history',[]),
        "claim_dispositions": state.get('claim_dispositions',{}),
        "parent_update": parent_update(state)}
    (cache / "run.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    if state.get('debug_analyses'):
        (cache / 'debug.json').write_text(json.dumps({'analyses': state['debug_analyses'], 'history': state['history']}, ensure_ascii=False, indent=2), encoding='utf-8')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'market_handoff.md').write_text(render_report(state), encoding='utf-8')
    files = {str(p.relative_to(cache)): file_hash(p) for p in cache.rglob('*') if p.is_file()}
    manifest = {'files': files, 'handoff_hash': file_hash(output / 'market_handoff.md')}
    (cache / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def check_reuse(output, key):
    cache = cache_path(output)
    if not cache.is_dir():
        raise InputError('legacy_or_missing_snapshot: 구형 출력은 보존되며 새 검증 결과로 재사용하지 않습니다')
    saved = json.loads((cache / 'run.json').read_text())
    if saved.get('output_schema_version') != '0.5' or saved.get('fingerprint') != key:
        raise InputError('snapshot_mismatch: 입력·모델·코드·프롬프트·출력 버전이 다릅니다')
    manifest = json.loads((cache / 'manifest.json').read_text())
    files = manifest.get('files', {})
    input_name='input.json' if saved.get('input',{}).get('input_format','markdown')!='markdown' else 'input.md'
    if not {'run.json', input_name} <= files.keys():
        raise InputError('snapshot_integrity: 필수 내부 자료 누락')
    for name, digest in files.items():
        if not re.fullmatch(r'(run\.json|input\.(?:md|json)|debug\.json|sources/[\w-]+\.md)', name):
            raise InputError('snapshot_integrity: 잘못된 저장 경로')
        p = cache / name
        if not p.is_file() or p.is_symlink() or file_hash(p) != digest:
            raise InputError('snapshot_integrity: 내부 저장 자료가 변경됐습니다')
    handoff = output / 'market_handoff.md'
    if not handoff.is_file() or file_hash(handoff) != manifest.get('handoff_hash'):
        raise InputError('snapshot_integrity: 전달 MD가 없거나 변경됐습니다')
    result = saved.get('result', {})
    if result.get('execution_status')!='completed' or result.get('errors', True):
        raise InputError('failed_snapshot: 오류가 남은 실행을 성공 캐시로 재사용하지 않습니다')
    return handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description="기술 조사 JSON 입력 기반 시장조사 에이전트")
    parser.add_argument("--input", required=True, type=Path, nargs='+', action='extend',
        help='dossier·registry·comparison JSON 4개, paper_analysis JSON 1~2개 또는 MD 한 개')
    parser.add_argument('--as-of', type=date.fromisoformat, help='조사 기준일 YYYY-MM-DD (JSON 기본: 실행일)')
    parser.add_argument('--domain', help='조사 도메인 (JSON 기본: cloud_datacenter)')
    parser.add_argument('--approach', nargs='+', choices=['SW','HW'], help='새 논문은 JSON 문서 순서대로 SW/HW 지정')
    for name in ['search','extract','llm']:
        parser.add_argument(f'--{name}-limit',type=int,help='시장 에이전트의 전체 실행 시도 상한')
    parser.add_argument("--mode", choices=["parse", "fixture", "live"], default="fixture")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reuse", action="store_true", help="같은 입력·코드·모델의 저장 결과만 재사용")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument('--debug', action='store_true', help='내부 캐시에 회차별 모델 결과 보존; 전달 MD는 동일')
    parser.add_argument("--env-file", type=Path, default=Path(__file__).parents[1] / ".env")
    args = parser.parse_args(argv)
    web = analyst = None
    try:
        data = read_input(args.input,as_of=args.as_of,domain=args.domain,approaches=args.approach)
        overrides={name:getattr(args,f'{name}_limit') for name in ['search','extract','llm']
            if getattr(args,f'{name}_limit') is not None}
        if overrides:
            if any(value<0 for value in overrides.values()):
                raise InputError('invalid_limits: 호출 한도는 0 이상의 정수여야 합니다')
            data.limits=Limits(**{**data.limits.model_dump(),**overrides})
        if args.mode == "parse":
            print(json.dumps({"role": data.role, "run_id": data.run_id, "domain": data.domain,
                "as_of": str(data.as_of), "limits": data.limits.model_dump(),
                "technologies": list(data.technologies), "evidence": list(data.evidence),
                "input_format":data.input_format,"schema_version":data.schema_version,
                "warnings": data.warnings, "input_hash": data.input_hash}, ensure_ascii=False, indent=2))
            return 0
        output = args.output or Path(__file__).parent / "outputs" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        model = args.model if args.mode == "live" else "fixture-no-llm"
        key = fingerprint(data, args.mode, model)
        if args.reuse:
            if args.output is None:
                raise InputError("reuse_requires_output: 재사용할 --output 폴더를 지정하세요")
            handoff = check_reuse(output, key)
            print(f"snapshot reused (new API calls: 0): {handoff.resolve()}")
            return 0
        if output.exists():
            raise InputError("output_exists: 새 출력 폴더를 지정하거나 --reuse를 사용하세요")
        if args.mode == "live":
            values = {**dotenv_values(args.env_file), **os.environ}
            missing = [k for k in ["OPENAI_API_KEY", "TAVILY_API_KEY"] if not values.get(k)]
            if missing:
                raise InputError("missing_credentials: " + ", ".join(missing))
            web, analyst = TavilyWeb(values["TAVILY_API_KEY"]), OpenAIAnalyst(values["OPENAI_API_KEY"], args.model, debug=args.debug)
        else:
            web, analyst = FixtureWeb(), FixtureAnalyst()
        state = run_market(data, web, analyst, mode=args.mode)
        save_run(state, output, key)
        result = state["result"]
        print(f"status={result.status}; execution={result.execution_status}; mode={args.mode}; attempts={result.usage}")
        print(f"handoff: {output.resolve() / 'market_handoff.md'}")
        return {'completed':0,'partial':3,'failed':2}[result.execution_status]
    except (InputError, OSError, ValueError, ProviderError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        for provider in [web, analyst]:
            if hasattr(provider, "close"):
                provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
