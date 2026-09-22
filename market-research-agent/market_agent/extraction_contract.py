"""기술·항목별 추출 슬롯으로 특정 논문/항목의 후보 독점을 막는다."""
import copy
from .schemas import CRITERIA
from .policy import quote_relevant


def extraction_schema(schema, data, evidence, bank, technical):
    base=schema['$defs'].pop('SelectedClaim')
    cells={}
    schema['$defs']['ExtractionReview']=copy.deepcopy(schema['$defs'].pop('SourceReview'))
    review=schema['$defs']['ExtractionReview']
    review['properties'].pop('evidence_id');review['required'].remove('evidence_id')
    for tech_id,tech in data.technologies.items():
        names=list(dict.fromkeys(s for q in bank.values() if tech_id in evidence[q['evidence_id']].tech_ids for s in q['subjects']))
        subject_name='Subject_'+tech_id.replace('-','_')
        if names:schema['$defs'][subject_name]={'type':'string','enum':names}
        for criterion in CRITERIA:
            variants=[]
            for provided in (False,True):
                if provided and criterion!='business_value':continue
                choices={key:q for key,q in bank.items() if tech_id in evidence[q['evidence_id']].tech_ids
                    and (q['evidence_id'] in technical)==provided}
                # 키워드는 우선순위 신호다. 표현 차이만으로 추출 슬롯을 닫지 않는다.
                choices=dict(sorted(choices.items(), key=lambda item: (quote_relevant(criterion,item[1]['text']),
                    criterion in evidence[item[1]['evidence_id']].criteria), reverse=True)[:16])
                if not choices:continue
                branch=copy.deepcopy(base);props=branch['properties']
                for field in ('tech_id','criterion_id'):
                    props.pop(field);branch['required'].remove(field)
                props['quote_id']={'type':'string','enum':list(choices)}
                if names:props['subject']={'$ref':f'#/$defs/{subject_name}'}
                if provided:
                    props['basis']={'type':'string','enum':['inference']}
                    props['relation_to_technology']={'type':'string','enum':['exact']}
                    props['metric']={'type':'null'}
                elif not any(tech.name.casefold() in (q['text']+' '+q['context']).casefold() for q in choices.values()):
                    props['relation_to_technology']={'type':'string','enum':['method_family','adjacent']}
                name=f'Claim_{tech_id.replace("-","_")}_{criterion}_{"provided" if provided else "web"}'
                schema['$defs'][name]=branch
                variants.append({'$ref':f'#/$defs/{name}'})
            cells[f'{tech_id}::{criterion}']={'type':'array',
                'items':{'anyOf':variants} if variants else {'type':'string'},'maxItems':2 if variants else 0}
    schema['properties']['claims']={'type':'object','properties':cells,'required':list(cells),'additionalProperties':False}
    sources={e.id:{'$ref':'#/$defs/ExtractionReview'} for e in evidence.values() if e.id in technical or (e.access_status=='full_text' and e.content_status=='substantive')}
    schema['properties']['reviews']={'type':'object','properties':sources,'required':list(sources),'additionalProperties':False}
    return schema


def flatten_extraction(parsed):
    """동적 모델 응답을 기존 내부 계약으로 변환한다. 배열 응답은 테스트/이전 제공자 호환."""
    if isinstance(parsed.get('claims'),dict):
        claims=[]
        for key,items in parsed['claims'].items():
            tech,criterion=key.split('::',1)
            if criterion not in CRITERIA or len(items)>2:raise ValueError('invalid_extraction_cell')
            for item in items:
                if 'tech_id' in item or 'criterion_id' in item:raise ValueError('duplicate_cell_identity')
                claims.append({**item,'tech_id':tech,'criterion_id':criterion})
        parsed={**parsed,'claims':claims}
    if isinstance(parsed.get('reviews'),dict):
        parsed={**parsed,'reviews':[{'evidence_id':key,**value} for key,value in parsed['reviews'].items()]}
    return parsed
