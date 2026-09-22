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
                for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z가-힣])',paragraph[0]):
                    if not re.search(keywords,sentence,re.I):
                        continue
                    text=sentence.strip()
                    # 조각난 25단어 창은 인용과 주장 범위가 어긋났다. 내부 검토에는
                    # 완전한 문장만 사용한다. 외부 보고서의 발췌는 별도로 25단어 제한.
                    if not 6 <= len(text.split()) <= 100 or not re.search(r'[.!?][*\"\u201d]*$',text):
                        continue
                    if re.search(r'\d+\.\d+\.\d+|\b(\d{2,})\1(?:K|\s*GB)|costs?.{0,30}\bpoints\b',text,re.I):
                        continue
                    score=len(re.findall(keywords,text,re.I))
                    score+=4*len(re.findall(r'product|license|customer|serving cost|deploy|available|standard',text,re.I))
                    position=body.find(text,paragraph.start())
                    context=body[max(0,position-300):position+len(text)+300]
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
            found=re.search(re.escape(tech.name),q['text']+' '+q.get('context',''),re.I)
            identity=found[0] if found else ''
        citation=Citation(evidence_id=e.id if e else 'unknown_quote:'+item.quote_id,
            quote=q['text'] if q else '',subject=item.subject,
            source_character=f'웹 발행자 설명 ({e.publisher or e.url}); 독립 검증 미확인' if e else '잘못된 구절 ID',
            identity_quote=identity,locator=q['locator'] if q else '',context=q.get('context','') if q else '')
        values=item.model_dump(exclude={'quote_id','subject'})
        if e:
            # 사실의 주체를 발행자로 고정한다. 독립 재현 또는 고객 실적을 뜻하지 않는다.
            values['statement']=f"자료 발행자의 설명: {values['statement']}"
        if q and (values['evidence_level'] in {'projection','inference','planned_release'} or
            re.search(r'\b(could|may|might|potential(?:ly)?|expected|plans? to)\b|가능성',q['text'],re.I)):
            values['basis']='inference'
            values['conditions']=list(dict.fromkeys([*values['conditions'],
                '원문이 제시한 가능성·조건부 전망이며 실제 시장 성과로 검증된 결과가 아님']))
        claims.append(Claim(**values,citation=citation))
    return Extraction(claims=claims,reviews=selected.reviews)
