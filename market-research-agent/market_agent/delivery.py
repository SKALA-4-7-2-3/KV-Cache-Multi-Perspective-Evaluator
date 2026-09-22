"""검증된 사실과 참고자료를 구별하면서 모든 시장 평가 항목을 완성한다.

이 단계는 주장 검증기를 우회하지 않는다. 미완료 항목에 도입 판단을 제공하고,
원자료는 별도 supporting_materials 계약으로 전달한다. 외부 호출 없이도 동작한다.
"""
import re

from .policy import quote_relevant
from .sources import relevance, TERMS
from .schemas import Analysis, CRITERIA, SupportingMaterial, unknown


# 현재 프로젝트의 두 접근법에 대한 조건부 의사결정 기준. 실적이나 수치를 생성하지 않는다.
DECISIONS = {
    'SW': {
        'market_size_growth': ('우선 공략 시장을 장문맥·고동시성 추론에서 GPU 메모리 비용이 병목인 운영자로 설정한다. '
            '추론 소프트웨어·AI 서버 시장 자료는 수요의 대리 지표로 사용하고, 선정 기법의 매출 규모는 별도로 산정한다.',
            '목표 고객 수 × 도입 가능 비율 × 연간 소프트웨어 지출로 시장 범위를 산정하고 중복 수요를 제거한다.'),
        'commercialization': ('제품화 경로는 기존 추론 엔진에 추가하는 KV 최적화 기능·플러그인으로 잡는다. '
            '독립 제품 판매 가능성을 결정하기 전에 코드 공개 범위, 상업적 이용 권리, 설치·지원 책임을 검증하는 단계로 평가한다.',
            '저장소·라이선스·배포 버전·지원 GPU를 확인하고 재현 가능한 설치 예제를 확보한다.'),
        'adoption': ('도입 우선순위는 메모리 병목이 있고 품질 허용 오차를 측정할 수 있는 추론 팀의 제한된 PoC로 설정한다. '
            '관련 기술군의 사용 사례는 후보 고객 발굴 자료로 활용하며 선정 기법의 운영 실적과 구분한다.',
            '기존 방식과 같은 모델·문맥 길이·동시성에서 품질 하한과 지연 SLO를 충족하면 단계적으로 도입한다.'),
        'ecosystem_support': ('생태계 진입점은 기존 추론 엔진의 KV 캐시 관리·양자화 확장 경로로 설정한다. '
            '관련 기능의 존재는 통합 가능성의 단서로 활용하고, 선정 알고리즘의 커널·스케줄러 호환성을 별도 검증한다.',
            '추론 엔진 버전, KV 레이아웃, 혼합 정밀도 커널 및 배치 스케줄러 조합의 호환성 표를 작성한다.'),
        'standardization': ('표준화 평가는 특정 인증 획득보다 런타임 인터페이스·KV 저장 형식·정밀도 표현의 호환성을 우선한다. '
            '엔진별 비표준 부분을 어댑터로 분리할 수 있는 경우 통합 후보로 평가한다.',
            '공통 인터페이스와 엔진 전용 커널을 구분하고 버전 변경 시 회귀 검사 범위를 정한다.'),
        'business_value': ('고객 가치는 메모리 절감이 동일 품질·지연 조건에서 동시 처리량 증가 또는 GPU 비용 절감으로 이어질 때 성립한다. '
            '커널 통합·유지보수 비용을 포함한 PoC 경제성 검토 대상으로 평가한다.',
            '토큰당 총비용, 처리량, 지연 p95, 답변 품질을 함께 측정한다. 논문 속 배수 성능을 다른 HW 실험과 직접 대결시키지 않는다.'),
    },
    'HW': {
        'market_size_growth': ('우선 공략 시장을 장문맥·고동시성 추론용 메모리 용량 확대를 검토하는 데이터센터로 설정한다. '
            'CXL·메모리 풀링·AI 인프라 시장은 인접 수요의 대리 지표이며 선정 어플라이언스의 시장 규모와 구분한다.',
            '신규·증설 클러스터 수 × 호환 가능한 호스트 비율 × 설치당 지출로 수요를 산정하고 교체 주기를 반영한다.'),
        'commercialization': ('제품화 경로는 메모리 어플라이언스와 호스트·인터커넥트·관리 소프트웨어를 묶은 공급 모델로 설정한다. '
            '공급사 자료를 바탕으로 구매 가능한 구성과 연구 제안의 범위를 구분하는 실증 단계로 평가한다.',
            '발주 가능한 SKU, 납기, 호스트 지원 목록, 통합 책임 및 보증·운영 지원 범위를 확인한다.'),
        'adoption': ('도입 우선순위는 메모리 확장 수요가 크고 호스트·네트워크 구성을 통제할 수 있는 데이터센터의 실증으로 설정한다. '
            '관련 제품의 고객 사례는 참고하되 선정 구조의 실제 배포 증거를 별도로 확보한다.',
            '단일 호스트 실증 후 동시 접속 부하, 장애 복구, 지연 p95 및 운영 절차를 확인하여 확대한다.'),
        'ecosystem_support': ('생태계 평가는 CXL 호스트·메모리 장치·펌웨어·OS·추론 소프트웨어의 조합 가능성을 중심으로 수행한다. '
            '관련 플랫폼 지원 자료를 통합 후보 목록으로 활용하며 광학 경로를 포함한 종단 호환성을 검증한다.',
            'CXL 세대와 기능, 호스트 토폴로지, 메모리 관리 드라이버, 패브릭 관리자 지원 조합을 확인한다.'),
        'standardization': ('CXL 규격은 호환성 요구를 정의하는 기준으로 활용한다. '
            '규격 존재와 선정 어플라이언스의 적합성 입증을 구분하고, 광학 패브릭·관리 기능의 구현별 차이를 실증 대상으로 평가한다.',
            '대상 CXL 버전·풀링 기능·상호운용 시험 결과를 확인하고 전용 확장 기능의 종속성을 기록한다.'),
        'business_value': ('고객 가치는 외부 메모리 확장이 모델·문맥 수용량을 늘리면서 호스트 경로의 지연과 대역폭 제약을 감당할 때 성립한다. '
            '장비·광학 연결·전력·운영 비용을 포함한 클러스터 단위 경제성 검토 대상으로 평가한다.',
            '기존 GPU 증설안과 같은 워크로드에서 총비용·용량·처리량·지연을 비교한다. 시뮬레이션 효과를 실배포 절감액으로 환산하지 않는다.'),
    },
}


def material_status(e, as_of):
    if e.published_at and e.published_at > as_of:
        return 'excluded', '기준일 이후 발행 자료: 평가 근거에서 제외하고 조사 이력으로 제공'
    if e.access_status == 'failed' or e.content_status in {'metadata_only', 'identity_mismatch'}:
        return 'excluded', e.content_reason or '본문·대상 확인에 실패: 평가 근거에서 제외하고 접근 단서로 제공'
    if e.access_status == 'provided_summary':
        return 'provided_context', '기술 조사 입력의 요약: 도입 시나리오의 전제이며 시장 실적을 증명하지 않음'
    if e.access_status == 'snippet':
        return 'search_excerpt', '검색 발췌: 잠정 검토에 사용하며 원문·문맥의 추가 확인 필요'
    return 'reference_only', '접근한 원자료: 이 항목의 주장 검증과 별개로 재검토 가능한 자료를 보존'


def select_materials(data, tech_id, criterion, evidence, errors):
    usable, excluded = [], []
    for e in evidence.values():
        if tech_id not in e.tech_ids:
            continue
        status, reason = material_status(e, data.as_of)
        if status == 'excluded':
            # 본문 오류도 한 곳에 추적하되 모든 행에 중복 나열하지 않는다.
            if criterion == 'commercialization':
                excluded.append(SupportingMaterial(evidence_id=e.id, quote='', locator=e.locator,
                    review_status=status, reason=reason))
            continue
        segments = [(s.text, s.locator) for s in e.segments] or [(e.excerpt, e.locator)]
        choices = []
        for body, loc in segments:
            for paragraph in re.split(r'\n\s*\n',body):
                paragraph=paragraph.strip()
                if paragraph.startswith(('#','|','![','---','+ ','* [')):
                    continue
                for text in re.split(r'(?<=[.!?。])\s+(?=[A-Z가-힣])',paragraph):
                    text=text.strip()
                    if not 6 <= len(text.split()) <= 180:
                        continue
                    if len(re.findall(r'\]\(',text))>3:
                        continue
                    if re.match(r'[#|!]|https?://|Get (?:Free|a free)|Chat is |Sign (?:in|up)|Subscribe|Require:|Ensure:|Algorithm \d+|You are viewing|\[Click|\[Skip',text,re.I):
                        continue
                    choices.append((text,loc))
        if not choices:
            continue
        def score_pair(pair):
            text,loc=pair
            ranking_text=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',text)
            score=relevance(ranking_text,data.technologies[tech_id],[criterion])
            score+=3*sum(term in text.casefold() for term in TERMS[criterion])
            score+=6*min(3,len(re.findall(r'inference|memory|KV[ -]?cache|CXL',ranking_text,re.I)))
            if re.search(r'train|fundrais',ranking_text,re.I) and not re.search(r'inference|KV[ -]?cache',ranking_text,re.I):
                score-=15
            score-=30 if re.search(r'More Releases|Related (?:Articles|Posts)|Main Navigation',loc,re.I) else 0
            return score
        text, loc = max(choices, key=score_pair)
        match = quote_relevant(criterion, text)
        if status != 'provided_context' and not match and criterion not in e.criteria:
            continue
        related_errors = [err.get('code', '') for err in errors if err.get('evidence_id') == e.id]
        if related_errors:
            reason += '; 생성 주장 검증 오류: ' + ', '.join(dict.fromkeys(related_errors))
        material = SupportingMaterial(evidence_id=e.id, quote=text.strip()[:1200], locator=loc,
            review_status=status, reason=reason)
        score = score_pair((text,loc)) + int(criterion in e.criteria)*2 + int(status == 'reference_only')
        usable.append((score, material))
    # 원문 2개 + 기술 전제 1개. 검색 발췌도 후순위로 남겨 사실 판단과 구별한다.
    web = sorted((x for x in usable if x[1].review_status != 'provided_context'), key=lambda x:x[0], reverse=True)[:2]
    provided = sorted((x for x in usable if x[1].review_status == 'provided_context'), key=lambda x:x[0], reverse=True)[:1]
    return [m for _, m in web + provided] + excluded[:6]


def complete_delivery(data, analysis, evidence, errors):
    """기술 × 기준의 완전한 행을 생성. 기존 유효 평가와 입력 객체는 변경하지 않는다."""
    evidence = {**data.evidence, **evidence}
    prior = {(r.tech_id, r.criterion_id):r for r in analysis.assessments}
    rows = []
    for tech in data.technologies.values():
        for criterion in CRITERIA:
            row = prior.get((tech.id, criterion), unknown(tech.id, criterion, '')).model_copy(deep=True)
            materials = select_materials(data, tech.id, criterion, evidence, errors)
            if row.generation_method=='model_synthesis' and row.verdict!='unknown':
                rows.append(row)
                continue
            row.supporting_materials = materials
            if row.verdict not in {'unknown', 'provisional'} and row.basis != 'unknown':
                row.evaluation_mode = 'grounded'
                row.confidence = 'high' if row.basis == 'fact' and row.relation_to_technology == 'exact' else 'medium'
                rows.append(row)
                continue
            web = [m for m in materials if m.review_status in {'reference_only', 'search_excerpt'}]
            premise = [m for m in materials if m.review_status == 'provided_context']
            judgment, condition = DECISIONS[tech.approach][criterion]
            row.evaluation_mode = 'provisional' if web or row.context_findings else ('scenario' if premise or tech.summary else 'research_plan')
            row.confidence = 'low'
            row.generation_method = 'deterministic_fallback'
            row.verdict, row.basis, row.relation_to_technology = 'provisional', 'inference', 'adjacent'
            row.judgment = f'{tech.name}: {judgment}'
            row.conditions = [*row.conditions, condition, '잠정 도입 판단이며 선정 기술의 매출·상용 출시·고객 채택을 확정하는 평가가 아님']
            row.gaps = list(dict.fromkeys([*row.gaps, '다음 확인: ' + (row.next_action or condition)]))
            row.citations, row.evidence_ids, row.metric = [], [], None
            # 검색·검토 이력과 검증된 관련 정보는 보존한다. 참고자료는 Citation으로 승격하지 않는다.
            rows.append(row)
    return Analysis(assessments=rows, followup_questions=analysis.followup_questions)


def delivery_coverage(analysis):
    return {mode:sum(r.evaluation_mode == mode for r in analysis.assessments)
            for mode in ['grounded', 'provisional', 'scenario', 'research_plan']}


def technology_status(data, analysis):
    return {tech:'completed' if all(r.evaluation_mode == 'grounded' for r in analysis.assessments if r.tech_id == tech)
            else 'provisional' for tech in data.technologies}
