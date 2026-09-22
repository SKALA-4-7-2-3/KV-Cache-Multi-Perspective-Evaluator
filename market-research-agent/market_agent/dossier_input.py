"""두 dossier + 공통 registry + comparison의 참조를 검증하는 입력 어댑터.

원문 경로와 지시는 실행하지 않는다. 첨부 발췌는 독립 확인된 시장 근거가 아니다.
"""
import copy
import hashlib
import json
from .json_input import parse_paper_analyses
from .parser import InputError


def parse_bundle(documents, **options):
    registries=[d for d in documents if isinstance(d,list)]
    dossiers=[d for d in documents if isinstance(d,dict) and 'dossier_version' in d]
    comparisons=[d for d in documents if isinstance(d,dict) and 'comparison_version' in d]
    if len(documents)!=4 or len(registries)!=1 or len(dossiers)!=2 or len(comparisons)!=1:
        raise InputError('invalid_bundle: dossier 2개 + evidence_registry 배열 + comparison 1개 필요')
    if any(d['dossier_version']!='1.0.0' for d in dossiers) or comparisons[0]['comparison_version']!='1.0.0':
        raise InputError('unsupported_bundle_version: dossier/comparison 1.0.0 필요')
    try:
        return normalize_bundle(dossiers,registries[0],comparisons[0],options)
    except (KeyError,TypeError,AttributeError,ValueError) as exc:
        if isinstance(exc,InputError):raise
        raise InputError('invalid_bundle_fields: dossier/registry/comparison 필드 형식 확인 필요') from None


def normalize_bundle(dossiers,registry,comparison,options):
    owners={d['paper']['paper_id']:d for d in dossiers}
    if len(owners)!=2:raise InputError('duplicate_paper_id')
    evidence={}
    for entry in registry:
        eid=entry['evidence_id'];owner=entry['document_id']
        if eid in evidence:raise InputError('duplicate_evidence_id')
        if owner not in owners:raise InputError('unknown_evidence_document')
        if hashlib.sha256(entry['snippet'].encode()).hexdigest()!=entry['content_hash']:
            raise InputError('evidence_hash_mismatch')
        if entry['locator'].get('document_sha256')!=owners[owner]['paper']['source_hash']:
            raise InputError('document_hash_mismatch')
        evidence[eid]=entry
    observations={};claims={}
    for d in dossiers:
        for field,key,target in [('experiment_observations','observation_id',observations),('claims','claim_id',claims)]:
            for entry in d[field]:
                if entry[key] in target:raise InputError('duplicate_'+key)
                target[entry[key]]=d['paper']['paper_id']
    def references(value,owner=None):
        if isinstance(value,list):
            for item in value:references(item,owner)
        elif isinstance(value,dict):
            local=value.get('paper_id',owner)
            if local and local not in owners:raise InputError('unknown_paper_reference')
            for key,item in value.items():
                target={'evidence_ids':{k:e['document_id'] for k,e in evidence.items()},
                    'context_evidence_ids':{k:e['document_id'] for k,e in evidence.items()},
                    'observation_ids':observations,'claim_ids':claims,'paper_ids':{k:k for k in owners}}.get(key)
                if target is not None:
                    if not isinstance(item,list) or any(ref not in target or (local and key!='paper_ids' and target[ref]!=local) for ref in item):
                        raise InputError('invalid_bundle_reference: '+key)
                else:references(item,local)
    for d in dossiers:references(d,d['paper']['paper_id'])
    references(comparison)
    normalized=[]
    for d in dossiers:
        entries=[]
        for entry in registry:
            if entry['document_id']==d['paper']['paper_id']:
                loc=entry['locator']
                entries.append({**entry,'page':loc.get('physical_page'),
                    'section':' / '.join(loc.get('section_path',[]))})
        normalized.append({'schema_version':'1.1.0','status':'succeeded','paper':d['paper'],
            'analysis':d['analysis'],'evidence_registry':entries})
    result=parse_paper_analyses(normalized,**options)
    # 디스크에 받은 원문을 내부 provenance로 보존한다. 모델에는 별도 투영한다.
    canonical=sorted(dossiers,key=lambda d:d['paper']['paper_id'])
    payload=[sorted(registry,key=lambda e:e['evidence_id']),comparison,*canonical]
    digest=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
    result.input_format='technical_bundle_json';result.schema_version='1.0.0'
    result.source_documents=copy.deepcopy(dossiers)
    result.source_registry=copy.deepcopy(registry);result.comparison=copy.deepcopy(comparison)
    result.input_hash=digest;result.run_id='market-'+digest[:16]
    result.provenance='상위 기술 조사 dossier/comparison 1.0.0 및 공통 evidence_registry'
    result.warnings.append('comparison의 결합 가설은 공동 실험 결과가 아니며 not_comparable 수치는 직접 비교 금지')
    return result


def comparison_background(data):
    """비교 금지·미검증 조건만 투영; 상위 참조 ID는 모델 선택지와 분리한다."""
    return {key:[{k:v for k,v in row.items() if k in {'metric','comparability','reason','text','assumptions','validation_needed','implication'}}
        for row in data.comparison.get(key,[])][:3]
        for key in ['metric_comparisons','integration_hypotheses','differing_assumptions']}
