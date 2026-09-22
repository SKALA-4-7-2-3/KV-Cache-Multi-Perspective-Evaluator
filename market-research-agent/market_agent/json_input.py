"""기술 조사 paper_analysis 1.1.0을 시장 에이전트 입력으로 정규화한다.

원본의 지시·모델 설정·로컬 파일 경로는 실행하지 않는다. 논문 발췌는
상위 에이전트가 제공한 배경 자료이며 독립 조회한 시장 근거로 승격하지 않는다.
"""
import copy
import hashlib
import json
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .parser import InputError
from .schemas import Evidence, Limits, MarketInput, Technology


class UpstreamRecord(BaseModel):
    model_config = ConfigDict(extra='allow', strict=True)


class Paper(UpstreamRecord):
    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    arxiv_id: str | None = None
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    source_path: str = ''


class PaperEvidence(UpstreamRecord):
    evidence_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    source_kind: str


class TechnicalClaim(UpstreamRecord):
    text: str = Field(min_length=1)
    claim_type: str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    context_evidence_ids: list[str] = Field(default_factory=list)


class PaperAnalysis(UpstreamRecord):
    schema_version: Literal['1.1.0']
    status: Literal['succeeded']
    paper: Paper
    analysis: dict[str, dict[str, list[TechnicalClaim] | list[str]]]
    evidence_registry: list[PaperEvidence]


def identify(paper, override):
    if re.search(r'\bRDKV\b', paper.title, re.I):
        name, inferred = 'RDKV', 'SW'
    elif re.search(r'Photonic[\s-]+CXL', paper.title, re.I):
        name, inferred = 'Photonic-CXL', 'HW'
    else:
        name, inferred = paper.title.strip(), None
    approach = override or inferred
    if approach not in {'SW', 'HW'}:
        raise InputError('approach_required: 새 논문의 SW/HW 구분을 --approach로 지정하세요')
    return name, approach


def technical_summary(doc, registered):
    lines = []
    if not {'technical_overview', 'scope', 'limitations'} <= doc.analysis.keys():
        raise InputError('missing_analysis_sections: technical_overview/scope/limitations 필요')
    for group, fields in doc.analysis.items():
        lines.append(f'[{group}]')
        for field, items in fields.items():
            if field == 'not_reported':
                if not all(isinstance(item,str) for item in items):
                    raise InputError('invalid_not_reported: 문자열 목록 필요')
                lines.append(f'not_reported: {", ".join(items)}')
                continue
            for item in items:
                if not isinstance(item,TechnicalClaim):
                    raise InputError(f'invalid_claim: {group}.{field}')
                missing=set(item.evidence_ids + item.context_evidence_ids)-registered
                if missing:
                    raise InputError(f'unknown_evidence_reference: {group}.{field}: {", ".join(sorted(missing))}')
                lines.append(f'{field} [{item.claim_type}; confidence={item.confidence}; '
                    f'evidence={",".join(item.evidence_ids)}; context={",".join(item.context_evidence_ids)}]: {item.text}')
    return '\n'.join(lines)


def model_background(data, technology):
    """원본 참조는 내부에 남기고 모델에는 기술 내용·한계만 투영한다."""
    document = next((d for d in data.source_documents
        if d.get('paper', {}).get('paper_id') == technology.paper_id), None)
    if not document:
        return technology.summary[:6000]
    lines = []
    for obs in document.get('experiment_observations',[])[:8]:
        lines.append('[experiment] ' + json.dumps({k:v for k,v in obs.items()
            if k not in {'evidence_ids','context_evidence_ids','observation_id'}},ensure_ascii=False))
    for group, fields in document['analysis'].items():
        lines.append(f'[{group}]')
        for field, items in fields.items():
            if field == 'not_reported':
                lines.append(f'not_reported: {", ".join(items)}')
            else:
                for item in items:
                    lines.append(f'{field} [{item["claim_type"]}; confidence={item["confidence"]}]: {item["text"]}')
    return '\n'.join(lines)[:6000]


def parse_paper_analyses(documents, *, as_of=None, domain=None, limits=None, approaches=None):
    documents = documents if isinstance(documents,list) else [documents]
    if not 1 <= len(documents) <= 2:
        raise InputError('paper_count: 논문 JSON 1개 또는 2개가 필요합니다')
    if approaches is not None and len(approaches)!=len(documents):
        raise InputError('approach_count: --approach는 JSON 문서 순서대로 한 개씩 지정하세요')
    try:
        parsed=[PaperAnalysis.model_validate(doc) for doc in documents]
    except ValidationError as exc:
        # 원문·개인 경로·모델 응답을 오류에 그대로 노출하지 않는다.
        fields=[ '.'.join(map(str,e['loc'])) for e in exc.errors() ]
        raise InputError('invalid_paper_analysis: ' + ', '.join(fields[:8])) from None
    technologies, evidence, warnings, paper_ids = {}, {}, [], set()
    for index, doc in enumerate(parsed):
        paper = doc.paper
        if paper.paper_id in paper_ids:
            raise InputError('duplicate_paper_id: 같은 논문을 두 번 입력했습니다')
        paper_ids.add(paper.paper_id)
        name, approach=identify(paper,approaches[index] if approaches else None)
        tech_id=f'{approach}-{1+sum(t.approach==approach for t in technologies.values()):02d}'
        url=''
        if paper.arxiv_id:
            if not re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?',paper.arxiv_id):
                raise InputError('invalid_arxiv_id: arxiv_id 형식 오류')
            url=f'https://arxiv.org/abs/{paper.arxiv_id}'
        issues=[] if url else ['공개 논문 URL 미제공: 제목으로 조사하며 source_path를 읽거나 URL로 추정하지 않음']
        if url and 'v' not in paper.arxiv_id:
            issues.append('arXiv 버전 미제공: 조회 자료와 입력 분석의 버전 동일성 추가 확인 필요')
        registered=set()
        for entry in doc.evidence_registry:
            if entry.document_id!=paper.paper_id:
                raise InputError('cross_document_evidence: 근거 document_id와 paper_id 불일치')
            if entry.evidence_id in evidence:
                raise InputError('duplicate_evidence_id: ' + entry.evidence_id)
            registered.add(entry.evidence_id)
            evidence[entry.evidence_id]=Evidence(id=entry.evidence_id,doc_id=paper.paper_id,
                title=paper.title,url=url,publisher=', '.join(paper.authors),
                locator='; '.join(filter(None,[f'page {entry.page}' if entry.page else '',entry.section])),
                excerpt=entry.snippet,content_hash=hashlib.sha256(entry.snippet.encode()).hexdigest(),
                source_type=f'상위 기술 조사 JSON의 {entry.source_kind} 발췌; 독립 원문 조회 전',
                access_status='provided_summary',tech_ids=[tech_id],
                access_scope='evidence_registry 발췌; 전체 논문·시장 사실 검증 아님')
        summary=technical_summary(doc,registered)
        technologies[tech_id]=Technology(id=tech_id,name=name,approach=approach,paper=paper.title,
            paper_id=paper.paper_id,url=url,summary=summary,evidence_ids=sorted(registered),issues=issues)
        warnings.extend(f'{tech_id}: {issue}' for issue in issues)
    serialized=json.dumps(documents,ensure_ascii=False,sort_keys=True,allow_nan=False)
    digest=hashlib.sha256(serialized.encode()).hexdigest()
    try:
        return MarketInput(schema_version='1.1.0',run_id='market-'+digest[:16],
            domain=domain or 'cloud_datacenter',as_of=as_of or date.today(),language='ko',
            limits=limits or Limits(search=18,extract=24,llm=10),technologies=technologies,evidence=evidence,
            raw_markdown='',input_hash=digest,input_format='paper_analysis_json',
            source_documents=copy.deepcopy(documents),provenance='상위 기술 조사 paper_analysis JSON 1.1.0',
            notes='상위 quality/confidence는 기술 분석의 기록이며 시장성 검증을 대신하지 않음',warnings=warnings)
    except ValidationError:
        raise InputError('invalid_market_options: 조사 기준일·도메인·호출 한도를 확인하세요') from None
