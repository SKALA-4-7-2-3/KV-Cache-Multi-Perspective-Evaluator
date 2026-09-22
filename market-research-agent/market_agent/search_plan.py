"""항목 목적과 두 회차 한도에 맞춘 결정적 검색 계획."""
from .schemas import CRITERIA, Question


SUFFIXES = {
    'market_size_growth': 'market size forecast region revenue methodology',
    'commercialization': 'implementation repository license product release',
    'adoption': 'customer deployment production case study',
    'ecosystem_support': 'inference engine support implementation version documentation',
    'standardization': 'standards specification compatibility documentation',
    'business_value': 'pricing integration cost benchmark limitations',
}


def initial_questions(data):
    questions = []
    for tech in data.technologies.values():
        name = 'Marvell Photonic Fabric' if 'Marvell Photonic Fabric' in tech.summary else tech.name
        query = f'"{tech.name}" "KV cache" implementation license' if tech.approach == 'SW' else f'{name} memory appliance product'
        questions.append(Question(tech_id=tech.id, criterion_id='commercialization',
            criteria=['commercialization', 'adoption', 'ecosystem_support'], query=query,
            reason='선정 기술의 직접 구현·제품화 단서와 관련 제품의 연결 확인', source_type='논문·공식 저장소·공식 제품 문서'))
    return questions[:2]


def repair_questions(data, rows, proposed, queries):
    seen = {' '.join(q['query'].lower().split()) for q in queries}
    pending = {(r.tech_id, r.criterion_id): r for r in rows if r.verdict == 'unknown' or r.gaps}
    result = []
    for tech in data.technologies.values():
        priorities = list(dict.fromkeys([q.criterion_id for q in proposed if q.tech_id == tech.id
            and (tech.id, q.criterion_id) in pending] + list(CRITERIA)))
        candidates = []
        for criterion in priorities:
            row = pending.get((tech.id, criterion))
            if not row:
                continue
            name = f'"{tech.name}" "KV cache"' if tech.approach == 'SW' else f'"{tech.name}" memory'
            if criterion == 'market_size_growth':
                name = 'KV cache inference optimization' if tech.approach == 'SW' else 'CXL memory pooling'
            candidates.append(Question(tech_id=tech.id, criterion_id=criterion, criteria=[criterion],
                query=f'{name} {SUFFIXES[criterion]}', reason='해당 항목의 남은 근거 공백 보완'))
        # 동일성 공백이 있으면 직접 연결 자료를 먼저 확인한다.
        candidates.sort(key=lambda q: 'identity_unverified' not in pending[(tech.id, q.criterion_id)].unknown_reasons)
        for q in candidates:
            key = ' '.join(q.query.lower().split())
            if key in seen or not q.query.strip() or len(q.query) > 400:
                continue
            if not q.criteria:
                q = q.model_copy(update={'criteria': [q.criterion_id]})
            result.append(q)
            seen.add(key)
            break
    return result[:2]
