"""항목별 판단 범위. 관련 시장 근거는 조건부 추론에만 사용한다."""
CONDITIONAL_CRITERIA = {
    'market_size_growth': '관련 시장의 규모·성장 신호이며 선정 기술의 매출·점유율·TAM을 입증하지 않음',
    'ecosystem_support': '관련 기술군의 지원 경로이며 선정 구현의 플러그인·커널·인터페이스 호환성 검증 필요',
    'standardization': '활용 가능한 관련 규격이며 선정 구현의 규격 준수·인증을 입증하지 않음',
    'business_value': '기술 효과가 고객 비용 절감으로 이어지는지는 워크로드·품질·통합비·운영비 검증 필요',
}


def assessment_eligible(claim):
    return claim.relation_to_technology == 'exact' or claim.criterion_id in CONDITIONAL_CRITERIA


def conditional_scope(criterion, relation):
    scope = '관련 기술군' if relation == 'method_family' else '인접 시장'
    return f'{scope} 근거에 따른 조건부 평가', CONDITIONAL_CRITERIA[criterion]


QUOTE_PATTERNS = {
    'market_size_growth': r'market|revenue|production|forecast|growth|cagr|시장|매출|생산량',
    'commercialization': r'product|commercial|launch|releas|licen[cs]e|available|repository|github|제품|출시|라이선스',
    'adoption': r'customer|production|deployed|adopted|uses? |using |고객|도입|운영',
    'ecosystem_support': r'support|integrat|compatib|framework|library|runtime|interoperab|지원|통합',
    'standardization': r'standard|specification|consortium|IEEE|JEDEC|표준|규격',
    'business_value': r'cost|price|memory efficiency|energy efficiency|latency|throughput|speedup|speed.up|footprint|reduc.{0,45}memory|memory.{0,45}(reduc|sav|capac|utiliz)|utilization|energy|비용|메모리.{0,20}절약',
}


def quote_relevant(criterion, text):
    import re
    text=re.sub(r'no cost to efficiency','',text,flags=re.I)
    if criterion=='ecosystem_support':
        text=re.sub(r'hardware[- ]supported(?: bit[- ]widths)?','',text,flags=re.I)
    return bool(re.search(QUOTE_PATTERNS[criterion],text,re.I))
