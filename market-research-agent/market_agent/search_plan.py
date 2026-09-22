"""항목 목적과 두 회차 한도에 맞춘 결정적 검색 계획."""
import re
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
        title = re.sub(r'https?://\S+', '', tech.paper).strip(' ()') or tech.name
        query = f'"{title[:180]}" implementation license product deployment'
        questions.append(Question(tech_id=tech.id, criterion_id='commercialization',
            criteria=['commercialization', 'adoption', 'ecosystem_support'], query=query,
            reason='선정 기술의 직접 구현·제품화 단서와 관련 제품의 연결 확인', source_type='논문·공식 저장소·공식 제품 문서'))
    return questions[:2]


def repair_questions(data, rows, proposed, queries):
    """미조사 목적을 기술별로 번갈아 배분한다. 모델의 검색 문장은 실행하지 않는다."""
    seen = {' '.join(q['query'].lower().split()) for q in queries}
    pending = {(r.tech_id,r.criterion_id) for r in rows if r.verdict=='unknown' or r.gaps}
    result = []
    groups = [
        ('market_size_growth',['market_size_growth','business_value']),
        ('standardization',['standardization','ecosystem_support']),
    ]
    for primary,criteria in groups:
        for tech in data.technologies.values():
            if not any((tech.id,c) in pending for c in criteria):
                continue
            family = 'KV cache inference optimization' if tech.approach=='SW' else 'CXL memory pooling'
            suffix = SUFFIXES[primary]
            if primary=='standardization':
                suffix += ' vLLM compatibility' if tech.approach=='SW' else ' official CXL consortium'
            query = f'{family} {suffix}'
            if query.casefold() in seen:
                continue
            result.append(Question(tech_id=tech.id,criterion_id=primary,criteria=criteria,query=query,
                reason='미조사 목적의 관련 기술군 자료 확인; 선정 논문의 시장 실적과 구분',
                source_type='공식 표준·제품 문서·시장 정의와 방법론을 공개한 자료'))
            seen.add(query.casefold())
    return result[:4]
