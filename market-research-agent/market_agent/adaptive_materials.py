"""형식을 이유로 버리지 않는 단계별 자료 묶음. 점수는 정렬용이며 사실성 점수가 아니다."""
import hashlib
import re
from .schemas import CRITERIA
from .sources import relevance, metadata_fragment


POLICIES = (
    {'level':0,'access':['full_text'],'relations':['exact'],
     'instruction':'선정 기술에 대한 직접 원문으로 평가한다. 관련 기술군만 설명하면 다음 단계로 넘긴다.'},
    {'level':1,'access':['full_text','provided_summary'],'relations':['exact','method_family'],
     'instruction':'같은 기술군 사례와 기술 요약을 모든 항목의 조건부 추론에 활용한다. 실제 출시·채택으로 일반화하지 않는다.'},
    {'level':2,'access':['full_text','provided_summary','snippet'],'relations':['exact','method_family','adjacent'],
     'instruction':'인접 시장·검색 발췌·부분 정보도 잠정 판단에 활용한다. 원문 미확보·시장 정의·지역·연도 공백을 명시한다.'},
)


def eligible(e, data, level):
    return (e.access_status in POLICIES[level]['access']
        and e.content_status not in {'metadata_only','identity_mismatch'}
        and not (e.published_at and e.published_at>data.as_of))


def build_packet(data, evidence, level, targets=None, sources=None):
    """표·짧은 줄·긴 문단 모두 원문 조각으로 유지. 항목별/문서별 순환 선택한다."""
    if level not in {0,1,2}:raise ValueError('invalid_research_level')
    targets=targets if targets is not None else [(t,c) for t in data.technologies for c in CRITERIA]
    sources=sources or {}
    fragments=[]
    for e in evidence.values():
        if not eligible(e,data,level):continue
        bodies=[(sources[e.doc_id],'추출 본문')] if e.doc_id in sources else (
            [(s.text,s.locator) for s in e.segments] or [(e.excerpt,e.locator)])
        for body,locator in bodies:
            for paragraph in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',body):
                # 큰 문단은 겹치는 창으로 분할해 본문 일치와 주변 맥락을 유지한다.
                for start in range(paragraph.start(),paragraph.end(),1100):
                    text=body[start:min(start+1400,paragraph.end())]
                    if not text.strip():continue
                    key='MAT-'+hashlib.sha256((e.id+'\n'+text).encode()).hexdigest()[:16]
                    fragments.append((key,dict(evidence_id=e.id,text=text,locator=f'{locator}; 문자 {start}:{start+len(text)}',
                        start=start,end=start+len(text),tech_ids=e.tech_ids,access_status=e.access_status,content_status=e.content_status,
                        title=e.title,url=e.url,published_at=str(e.published_at) if e.published_at else None)))
    packet={}
    for tech_id,criterion in targets:
        if tech_id not in data.technologies or criterion not in CRITERIA:continue
        ranked=[]
        for key,item in fragments:
            if tech_id not in item['tech_ids']:continue
            clean=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',item['text'])
            score=relevance(clean,data.technologies[tech_id],[criterion])
            score+=2*int(criterion in evidence[item['evidence_id']].criteria)
            score-=30 if re.search(r'More Releases|Main Navigation|Get Free Sample|\[Skip to',item['text'],re.I) else 0
            # 제목은 자료의 신원 단서다. 짧은 실제 본문을 밀어내거나 시장 사실처럼 쓰이지 않게 한다.
            score-=100 if metadata_fragment(item['text'],data.technologies[tech_id]) else 0
            ranked.append((score,key,item))
        ranked.sort(key=lambda x:(-x[0],x[1]))
        # 하나의 긴 문서가 모든 슬롯을 차지하지 않도록 출처당 첫 조각을 우선한다.
        seen=set();ordered=[];remainder=[]
        for _,key,item in ranked:
            identity=(item['access_status'],item['url'] or evidence[item['evidence_id']].doc_id)
            if identity in seen:remainder.append((key,item))
            else:ordered.append((key,item));seen.add(identity)
        candidates=ordered+remainder
        slots=['full_text','full_text'] if level==0 else (['full_text','provided_summary','full_text'] if level==1 else ['full_text','full_text','snippet','provided_summary'])
        selected={}
        for access in slots:
            found=next(((key,item) for key,item in candidates if key not in selected and item['access_status']==access),None)
            if found:selected[found[0]]=found[1]
        for key,item in candidates:
            if len(selected)>=2+level:break
            selected.setdefault(key,item)
        packet.update(selected)
    return packet
