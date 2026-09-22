"""원문 구절 ID를 미리 발급하여 모델의 자유로운 인용문 생성을 제거한다."""
import hashlib
import re

from .schemas import Claim, Citation, Extraction


def quote_bank(evidence):
    bank={}
    keywords=r'product|announc|introduc|support|license|available|customer|deploy|cost|standard|cxl|memory|inference|시장|지원|제품'
    for e in evidence.values():
        if e.access_status!='full_text' or e.content_status!='substantive':
            continue
        candidates=[]
        bodies=[(s.text,s.locator) for s in e.segments] or [(e.excerpt,e.locator)]
        for body,locator in bodies:
            for paragraph in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',body):
                if paragraph[0].startswith(('#','|','![')):
                    continue
                for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z가-힣])|\n',paragraph[0]):
                    if not re.search(keywords,sentence,re.I):
                        continue
                    words=list(re.finditer(r'\S+',sentence))
                    for offset in range(0,len(words),25):
                        window=words[offset:offset+25]
                        if len(window)<6:
                            continue
                        text=sentence[window[0].start():window[-1].end()]
                        score=len(re.findall(keywords,text,re.I))
                        context=sentence[max(0,window[0].start()-150):window[-1].end()+150]
                        candidates.append((score,text,context,locator))
        seen=set()
        for _,text,context,locator in sorted(candidates,key=lambda x:-x[0]):
            if text in seen:
                continue
            seen.add(text)
            key='Q-'+hashlib.sha256((e.id+'\n'+text).encode()).hexdigest()[:12]
            bank[key]={'evidence_id':e.id,'text':text,'context':context,'locator':locator or '인용 구절로 원문 검색'}
            if len(seen)>=10:
                break
    return bank


def resolve_quotes(data, selected, bank, evidence):
    claims=[]
    for item in selected.claims:
        q=bank.get(item.quote_id)
        e=evidence.get(q['evidence_id']) if q else None
        tech=data.technologies.get(item.tech_id)
        identity=''
        if e and tech:
            found=re.search(re.escape(tech.name),e.excerpt,re.I)
            identity=found[0] if found else ''
        citation=Citation(evidence_id=e.id if e else 'unknown_quote:'+item.quote_id,
            quote=q['text'] if q else '',subject=item.subject,
            source_character=f'웹 발행자 설명 ({e.publisher or e.url}); 독립 검증 미확인' if e else '잘못된 구절 ID',
            identity_quote=identity,locator=q['locator'] if q else '')
        values=item.model_dump(exclude={'quote_id','subject'})
        claims.append(Claim(**values,citation=citation))
    return Extraction(claims=claims,reviews=selected.reviews)
