"""실제 LLM과 명시적으로 가상인 오프라인 제공자."""

import json
import copy
from datetime import date

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from .prompts import EXTRACTION_PROMPT, COMPOSITION_PROMPT
from .schemas import CRITERIA, Extraction, SourceReview, DraftAnalysis, DraftAssessment, SelectedExtraction, ClaimReview, ReviewedDraftAnalysis
from .quotes import quote_bank, resolve_quotes
from .tools import ProviderError
from .json_input import model_background
from .dossier_input import comparison_background


def strict_schema(model):
    schema=model.model_json_schema()
    def visit(item):
        if isinstance(item,dict):
            item.pop('default',None)
            if item.get('type')=='object':
                item['additionalProperties']=False
                item['required']=list(item.get('properties',{}))
            for value in item.values():visit(value)
        elif isinstance(item,list):
            for value in item:visit(value)
    visit(schema)
    return schema


class OpenAIAnalyst:
    def __init__(self, api_key: str, model="gpt-4.1-mini", *, debug=False):
        if not api_key:
            raise ProviderError("missing_openai_key", fatal=True)
        from langchain_openai import ChatOpenAI

        self.model = model
        self.usage = []
        self.output_checks = []
        self.debug = debug
        self.debug_analyses = []
        self._llm = ChatOpenAI(api_key=api_key, model=model, temperature=0, max_retries=0, timeout=60)
        self._composer = self._llm.with_structured_output(strict_schema(ReviewedDraftAnalysis), method="json_schema", strict=True, include_raw=True)

    def _invoke(self, stage, runnable, schema, prompt, payload):
        try:
            response = runnable.invoke([("system", prompt), ("human", json.dumps(payload, ensure_ascii=False))])
        except (ValidationError, OutputParserException):
            raise ProviderError("invalid_structured_output") from None
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            fatal = status in {401, 403} or code == "insufficient_quota"
            retryable = not fatal and (status in {408, 429, 500, 502, 503, 504} or type(exc).__name__ in {"APITimeoutError", "APIConnectionError"})
            raise ProviderError(f"openai_{status or type(exc).__name__}", retryable=retryable, fatal=fatal) from None
        self.usage.append({"stage": stage, **(getattr(response.get("raw"), "usage_metadata", None) or {})})
        parsed = response.get('parsed')
        if isinstance(parsed, dict):
            try:
                parsed = schema.model_validate(parsed)
            except ValidationError:
                raise ProviderError('invalid_structured_output') from None
        if not isinstance(parsed, schema) or response.get('parsing_error'):
            raise ProviderError('invalid_structured_output')
        if self.debug:
            self.debug_analyses.append({'stage': stage, 'result': parsed.model_dump(mode='json')})
        self.output_checks.append({'stage': stage, 'schema': schema.__name__, 'valid': True})
        return parsed

    def extract(self, data, evidence, previous=None, issues=None):
        bank=quote_bank(evidence)
        if not bank:
            return Extraction(claims=[], reviews=[])
        material = []
        for e in evidence.values():
            if not (e.access_status=='full_text' and e.content_status=='substantive'):
                continue
            item={'evidence_id':e.id,'title':e.title,'url':e.url,'published_at':str(e.published_at) if e.published_at else None,
                'scope':e.access_scope,'technology_candidates':e.tech_ids,'requested_criteria':e.criteria,
                'quotes':{k:v for k,v in bank.items() if v['evidence_id']==e.id}}
            material.append(item)
        payload = {'scope': {'domain':data.domain,'as_of':str(data.as_of)},
            'criteria':CRITERIA,'comparison_constraints':comparison_background(data),
            'technologies': {k:{'name':v.name,'paper_url':v.url,
                **({'technical_context':model_background(data,v),'technical_context_truncated':len(v.summary)>6000,
                    'input_warnings':v.issues} if data.input_format!='markdown' else {})}
                for k,v in data.technologies.items()},
            'evidence': material, 'previous_claims': {k:{'tech_id':v.tech_id,'criterion_id':v.criterion_id,'statement':v.statement} for k,v in (previous or {}).items()},
            'validation_issues':issues or []}
        schema=strict_schema(SelectedExtraction)
        base=schema['$defs'].pop('SelectedClaim')
        variants=[]
        for tech_id,tech in data.technologies.items():
            choices={key:q for key,q in bank.items() if tech_id in evidence[q['evidence_id']].tech_ids}
            if not choices:
                continue
            branch=copy.deepcopy(base)
            props=branch['properties']
            props['tech_id']={'type':'string','enum':[tech_id]}
            props['quote_id']={'type':'string','enum':list(choices)}
            subjects=list(dict.fromkeys(s for q in choices.values() for s in q['subjects']))
            # 선택지 자체는 원문의 연속 문자열이며, 인용별 연결은 로컬에서 재검사한다.
            if subjects:props['subject']={'type':'string','enum':subjects}
            if not any(tech.name.casefold() in (q['text']+' '+q['context']).casefold() for q in choices.values()):
                props['relation_to_technology']={'type':'string','enum':['method_family','adjacent']}
            variants.append(branch)
        if not variants:
            return Extraction(claims=[],reviews=[])
        schema['properties']['claims']['items']={'anyOf':variants}
        extractor=self._llm.with_structured_output(schema,method='json_schema',strict=True,include_raw=True)
        selected=self._invoke('extract',extractor,SelectedExtraction,EXTRACTION_PROMPT,payload)
        return resolve_quotes(data,selected,bank,evidence)

    def compose(self, data, claims, previous=None, issues=None):
        payload = {'scope':{'domain':data.domain,'as_of':str(data.as_of)},
            'technologies':{k:v.name for k,v in data.technologies.items()}, 'criteria':CRITERIA,
            'expected_assessment_count':len(data.technologies)*len(CRITERIA),
            'claims':{k:v.model_dump(mode='json') for k,v in claims.items()},
            'allowed_exact_claims':{t:{c:[k for k,v in claims.items() if
                (v.tech_id,v.criterion_id,v.relation_to_technology)==(t,c,'exact')] for c in CRITERIA}
                for t in data.technologies},
            'previous':previous.model_dump(mode='json') if previous else None,'validation_issues':issues or []}
        return self._invoke('compose',self._composer,ReviewedDraftAnalysis,COMPOSITION_PROMPT,payload)

    def close(self):
        client = getattr(self._llm, "root_client", None)
        if client:
            client.close()


class FixtureWeb:
    """실제 시장 자료가 아닌 파이프라인 검사 전용 응답."""

    def search(self, query, as_of):
        tech = "SW-01" if "RDKV" in query else "HW-01"
        return [{"title": f"[가상 테스트 자료] {tech}", "url": f"https://example.org/market-fixture/{tech}",
            "content": "KV cache 시장 조사 테스트용 검색 단서. 실제 제품·고객·시장 수치가 없음.", "published_at": date(2026, 9, 1)}]

    def extract(self, url):
        return f"# 가상 테스트 자료 {url.rsplit('/', 1)[-1]}\n파이프라인 검사용 응답이다. 실제 시장의 제품·채택·수치를 입증하지 않는다."

    def close(self):
        pass


class FixtureAnalyst:
    model = "fixture-no-llm"

    def extract(self, data, evidence, previous=None, issues=None):
        return Extraction(claims=[],reviews=[SourceReview(evidence_id=e.id,outcome='no_market_claim',
            reason='가상 테스트 자료에는 실제 시장 근거가 없음',criteria=e.criteria) for e in evidence.values()
            if e.access_status=='full_text' and e.content_status=='substantive'])

    def compose(self, data, claims, previous=None, issues=None):
        rows=[DraftAssessment(tech_id=t,criterion_id=c,judgment='미확인: fixture 모드에는 실제 시장 근거가 없습니다',
            verdict='unknown',basis='unknown',claim_ids=[],conditions=[],gaps=['fixture 자료']) for t in data.technologies for c in CRITERIA]
        return DraftAnalysis(assessments=rows,followup_questions=[],claim_reviews=[
            ClaimReview(claim_id=k,supported=True,reason='합성 테스트 제공자가 미리 검토한 주장') for k in claims])
