"""검증된 입력 참조에서 고객 가치의 기술적 전제 후보를 소량 선택한다."""
import re


def technical_evidence(data, evidence):
    if data.input_format not in {'technical_bundle_json','paper_analysis_json'}:
        return {}
    selected={}
    for tech in data.technologies.values():
        candidates=[]
        for eid in tech.evidence_ids:
            e=evidence.get(eid)
            if not e or e.access_status!='provided_summary' or tech.id not in e.tech_ids:
                continue
            text=e.excerpt
            # 수식·표 조각보다 자원/운영 효과를 서술하는 문단을 우선한다.
            effect=re.findall(r'reduc\w*|sav\w*|capacity|latency|throughput|speedup|절감|절약|용량|지연',text,re.I)
            if not effect or not re.search(r'memory|cache|메모리|캐시',text,re.I):continue
            score=len(effect)+(4 if re.search(r'conclusion|abstract',e.locator,re.I) else 0)
            candidates.append((score,e))
        for _,e in sorted(candidates,key=lambda x:(-x[0],x[1].id))[:2]:
            selected[e.id]=e.model_copy(update={'criteria':['business_value']})
    return selected
