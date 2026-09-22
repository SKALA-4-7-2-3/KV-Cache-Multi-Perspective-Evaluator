"""저장된 라이브 결과를 현재 로컬 검증기로 축소 재검증한다. API 호출은 없다."""
import argparse
import json
import re
from pathlib import Path

from .delivery import complete_delivery, delivery_coverage, technology_status
from .claims import criterion_supported, validate_claims, materialize, pool_dispositions
from .cli import file_hash, fingerprint, save_run
from .parser import InputError
from .policy import assessment_eligible
from .research import annotate
from .schemas import MarketInput, MarketResult, Evidence, Claim, DraftAnalysis, DraftAssessment
from .tools import Budget
from .validation import validate_analysis, normalized


def revalidate(saved, sources):
    if saved['result'].get('progress',{}).get('engine')=='adaptive-v1':
        return revalidate_adaptive(saved,sources)
    data=MarketInput.model_validate(saved['input'])
    result=MarketResult.model_validate(saved['result'])
    evidence={k:Evidence.model_validate(v) for k,v in saved['evidence'].items()}
    original={k:Claim.model_validate(v) for k,v in saved['claim_pool'].items()}
    validated,errors=validate_claims(data,list(original.values()),evidence)
    pool={k:c for k,c in validated.items() if criterion_supported(c)}
    rows=[]
    for r in result.assessments:
        ids=[k for k,c in pool.items() if (c.tech_id,c.criterion_id)==(r.tech_id,r.criterion_id) and assessment_eligible(c)
            and any(x.evidence_id==c.citation.evidence_id and normalized(x.quote)==normalized(c.citation.quote) for x in r.citations)]
        rows.append(DraftAssessment(tech_id=r.tech_id,criterion_id=r.criterion_id,judgment=r.judgment,
            verdict=r.verdict,basis=r.basis,claim_ids=ids,conditions=r.conditions,gaps=r.gaps))
    analysis,links=materialize(data,DraftAnalysis(assessments=rows,followup_questions=result.followup_questions),pool)
    analysis,checks=validate_analysis(data,analysis,evidence)
    errors=result.errors+errors+links+checks
    budget=Budget(data.limits);budget.used.update(result.usage)
    examined={(r['tech_id'],r['criterion_id']):r['evidence_ids'] for r in result.progress.get('examined',[])}
    analysis=annotate(analysis,data,evidence,saved['queries'],errors,budget,True,reviewed=examined)
    dispositions=pool_dispositions(pool,analysis)
    for k in original.keys()-pool.keys():dispositions[k]='rejected: local_scope_revalidation'
    analysis=complete_delivery(data,analysis,evidence,errors)
    statuses=technology_status(data,analysis)
    incomplete=bool(errors) or any(r.research_status=='not_started' for r in analysis.assessments)
    updated=result.model_copy(update={'output_schema_version':'0.6','assessments':analysis.assessments,'errors':errors,
        'progress':{**result.progress,'errors':errors,'delivery_coverage':delivery_coverage(analysis)},'technology_status':statuses,
        'status':'failed' if result.status=='failed' else ('completed' if all(v=='completed' for v in statuses.values()) else 'provisional'),
        'execution_status':'failed' if result.execution_status=='failed' else ('partial' if incomplete else 'completed')})
    return dict(data=data,result=updated,evidence=evidence,sources=sources,queries=saved['queries'],
        events=saved['events'],token_usage=saved['token_usage'],model=saved['model'],
        initial_evidence_ids=list(data.evidence),claim_pool=pool,
        candidate_pool={k:Claim.model_validate(v) for k,v in saved.get('candidate_pool',{}).items()},
        claim_review_log={**saved.get('claim_review_log',{}),**dispositions},
        claim_dispositions={**saved.get('claim_dispositions',{}),**dispositions},
        extraction_history=saved.get('extraction_history',[]),reviews=saved.get('source_reviews',{}),
        history=[*saved.get('graph_history',[]),'local_scope_revalidation'],
        output_checks=[*saved.get('output_checks',[]),{'stage':'local_scope_revalidation','new_api_calls':0}])


def revalidate_adaptive(saved,sources):
    from .adaptive import restore_records, merge_verified
    from .schemas import Analysis, unknown
    data=MarketInput.model_validate(saved['input']);old=MarketResult.model_validate(saved['result'])
    evidence={k:Evidence.model_validate(v) for k,v in saved['evidence'].items()}
    analysis,issues,records=restore_records(data,old.progress,evidence,sources)
    analysis=merge_verified(data,analysis,Analysis(assessments=old.assessments,followup_questions=[]),evidence)
    rows={(r.tech_id,r.criterion_id):r for r in analysis.assessments}
    from .schemas import CRITERIA
    analysis=Analysis(assessments=[rows.get((t,c),unknown(t,c,'저장된 자료 종합 평가 재검증 실패'))
        for t in data.technologies for c in CRITERIA],followup_questions=[])
    errors=old.errors+issues
    budget=Budget(data.limits);budget.used.update(old.usage)
    reviewed={(r.tech_id,r.criterion_id):r.reviewed_evidence_ids for r in analysis.assessments}
    analysis=annotate(analysis,data,evidence,saved['queries'],errors,budget,True,reviewed=reviewed)
    analysis=complete_delivery(data,analysis,evidence,errors)
    statuses=technology_status(data,analysis)
    result=old.model_copy(update={'output_schema_version':'0.6','assessments':analysis.assessments,'errors':errors,
        'technology_status':statuses,'status':'failed' if old.status=='failed' else ('completed' if all(v=='completed' for v in statuses.values()) else 'provisional'),
        'execution_status':'failed' if old.execution_status=='failed' else ('partial' if errors or any(r.generation_method=='deterministic_fallback' for r in analysis.assessments) else 'completed'),
        'progress':{**old.progress,'errors':errors,'synthesis_records':records,'delivery_coverage':delivery_coverage(analysis)}})
    return dict(data=data,result=result,evidence=evidence,sources=sources,queries=saved['queries'],events=saved['events'],
        model=saved['model'],token_usage=saved['token_usage'],initial_evidence_ids=list(data.evidence),claim_pool={},
        history=[*saved.get('graph_history',[]),'local_synthesis_revalidation'],
        output_checks=[*saved.get('output_checks',[]),{'stage':'local_synthesis_revalidation','new_api_calls':0}])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    cache=args.snapshot.parent
    manifest=json.loads((cache/'manifest.json').read_text())
    if args.snapshot.name!='run.json' or 'run.json' not in manifest.get('files',{}):
        raise InputError('snapshot_integrity')
    for name,digest in manifest['files'].items():
        if not re.fullmatch(r'(run\.json|input\.(?:md|json)|debug\.json|sources/[\w-]+\.md)',name):
            raise InputError('snapshot_integrity')
        path=cache/name
        if path.is_symlink() or not path.is_file() or file_hash(path)!=digest:
            raise InputError('snapshot_integrity')
    saved=json.loads(args.snapshot.read_text())
    sources={Path(n).stem:(cache/n).read_text() for n in manifest['files'] if n.startswith('sources/')}
    state=revalidate(saved,sources)
    state['output_checks'][-1]['source_snapshot_hash']=file_hash(args.snapshot)
    save_run(state,args.output,fingerprint(state['data'],state['result'].mode,state['model']))
    print(f"execution={state['result'].execution_status}; new API calls: 0; handoff: {args.output/'market_handoff.md'}")
    return {'completed':0,'partial':3,'failed':2}[state['result'].execution_status]


if __name__=='__main__':
    raise SystemExit(main())
