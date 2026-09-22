"""실제 LLM과 명시적으로 가상인 오프라인 제공자."""

import json
from copy import deepcopy
from datetime import date

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from .prompts import EXTRACTION_PROMPT, COMPOSITION_PROMPT, SYNTHESIS_PROMPT, SYNTHESIS_REVIEW_PROMPT
from .schemas import CRITERIA, Extraction, SourceReview, DraftAnalysis, DraftAssessment, SelectedExtraction, ClaimReview, ReviewedDraftAnalysis
from .extraction_contract import extraction_schema, flatten_extraction
from .premises import technical_evidence
from .policy import assessment_eligible, CONDITIONAL_CRITERIA
from .quotes import quote_bank, resolve_quotes
from .tools import ProviderError
from .schemas import Synthesis, SynthesisRow, SynthesisReviews
from .adaptive_materials import POLICIES
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


def synthesis_schema(packet, level, targets):
    cells={}
    for tech,criterion in targets:
        owned=[q for q,p in packet.items() if tech in p['tech_ids']]
        if not owned:
            cells[tech+'::'+criterion]={'type':'null'}
            continue
        cell=deepcopy(strict_schema(SynthesisRow));fields=cell['properties']
        fields['tech_id']['enum']=[tech];fields['criterion_id']['enum']=[criterion]
        fields['relation_to_technology']['enum']=POLICIES[level]['relations']
        fields['quote_ids']['items']['enum']=owned;fields['quote_ids']['minItems']=1
        fields['conditions']['minItems']=1;fields['conditions']['items']['minLength']=1
        for field in ['observation','judgment']:fields[field]['minLength']=1
        cells[tech+'::'+criterion]={'anyOf':[cell,{'type':'null'}]}
    return {'title':'MarketSynthesisByCell','type':'object','additionalProperties':False,'required':['assessments'],
        'properties':{'assessments':{'type':'object','additionalProperties':False,'required':list(cells),'properties':cells}}}


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
                if schema is SelectedExtraction:parsed=flatten_extraction(parsed)
                if schema is Synthesis and isinstance(parsed.get('assessments'),dict):
                    parsed={'assessments':[row for row in parsed['assessments'].values() if row is not None]}
                parsed = schema.model_validate(parsed)
            except (ValidationError,ValueError):
                raise ProviderError('invalid_structured_output') from None
        if not isinstance(parsed, schema) or response.get('parsing_error'):
            raise ProviderError('invalid_structured_output')
        if self.debug:
            self.debug_analyses.append({'stage': stage, 'result': parsed.model_dump(mode='json')})
        self.output_checks.append({'stage': stage, 'schema': schema.__name__, 'valid': True})
        return parsed

    def extract(self, data, evidence, previous=None, issues=None):
        technical=technical_evidence(data,evidence)
        bank=quote_bank(evidence,technical_ids=technical)
        if not bank:
            return Extraction(claims=[], reviews=[])
        material = []
        for e in evidence.values():
            if e.id not in technical and not (e.access_status=='full_text' and e.content_status=='substantive'):
                continue
            item={'evidence_id':e.id,'title':e.title,'url':e.url,'published_at':str(e.published_at) if e.published_at else None,
                'scope':e.access_scope,'access_status':e.access_status,'technology_candidates':e.tech_ids,'requested_criteria':e.criteria,
                'quotes':{k:v for k,v in bank.items() if v['evidence_id']==e.id}}
            material.append(item)
        payload = {'scope': {'domain':data.domain,'as_of':str(data.as_of)},
            'criteria':CRITERIA,'comparison_constraints':comparison_background(data),
            'technologies': {k:{'name':v.name,'paper_url':v.url,
                **({'technical_context':model_background(data,v)[:2000],'technical_context_truncated':len(v.summary)>2000,
                    'input_warnings':v.issues} if data.input_format!='markdown' else {})}
                for k,v in data.technologies.items()},
            'evidence': material, 'previous_claims': {k:{'tech_id':v.tech_id,'criterion_id':v.criterion_id,'statement':v.statement} for k,v in (previous or {}).items()},
            'validation_issues':[{k:v for k,v in issue.items() if k!='candidate'} for issue in (issues or [])]}
        schema=extraction_schema(strict_schema(SelectedExtraction),data,evidence,bank,technical)
        extractor=self._llm.with_structured_output(schema,method='json_schema',strict=True,include_raw=True)
        selected=self._invoke('extract',extractor,SelectedExtraction,EXTRACTION_PROMPT,payload)
        return resolve_quotes(data,selected,bank,evidence)

    def compose(self, data, claims, previous=None, issues=None, *, audit=False):
        payload = {'scope':{'domain':data.domain,'as_of':str(data.as_of)},
            'technologies':{k:v.name for k,v in data.technologies.items()}, 'criteria':CRITERIA,
            'conditional_criteria':CONDITIONAL_CRITERIA,
            'expected_assessment_count':len(data.technologies)*len(CRITERIA),
            'claims':{k:v.model_dump(mode='json') for k,v in claims.items()},
            'allowed_assessment_claims':{t:{c:[k for k,v in claims.items() if
                (v.tech_id,v.criterion_id)==(t,c) and assessment_eligible(v)] for c in CRITERIA}
                for t in data.technologies},
            'previous':previous.model_dump(mode='json') if previous else None,'validation_issues':issues or []}
        prompt=COMPOSITION_PROMPT
        if audit:
            prompt += '\n최종 독립 검토다. 앞 단계 판정을 신뢰하지 말고 각 statement를 인용문과 대조한다. '+\
                '인용에 없는 세부 내용을 하나라도 추가했으면 supported=false다. '+\
                '벤치마크 성능을 생태계 지원/제품화로, 일반 기술 소개를 실고객 채택으로 분류했으면 market_relevant=false다. '+\
                '정확히 뒷받침되는 주장만 남긴다. 연구 효과 및 공급사 전망의 조건을 반드시 보존한다.'
        return self._invoke('audit' if audit else 'compose',self._composer,ReviewedDraftAnalysis,prompt,payload)

    def audit(self,data,claims):
        return self.compose(data,claims,audit=True)

    def synthesize(self, data, packet, level, targets, previous=None, issues=None):
        payload={'research_policy':POLICIES[level], 'as_of':str(data.as_of),'domain':data.domain,
            'technologies':{k:{'name':v.name,'approach':v.approach,'paper_url':v.url} for k,v in data.technologies.items()},
            'criteria':CRITERIA,'targets':[{'tech_id':t,'criterion_id':c} for t,c in targets],
            'packet':packet,'comparison_constraints':comparison_background(data),
            'previous':previous.model_dump(mode='json') if previous else None,'issues':issues or []}
        schema=synthesis_schema(packet,level,targets)
        runnable=self._llm.with_structured_output(schema,method='json_schema',strict=True,include_raw=True)
        return self._invoke('synthesize',runnable,Synthesis,SYNTHESIS_PROMPT,payload)

    def review_synthesis(self, data, draft, packet, level):
        used={q for row in draft.assessments for q in row.quote_ids}
        payload={'research_policy':POLICIES[level],'as_of':str(data.as_of),'criteria':CRITERIA,
            'technologies':{k:v.name for k,v in data.technologies.items()},
            'assessments':draft.model_dump(mode='json'),'packet':{q:v for q,v in packet.items() if q in used},
            'comparison_constraints':comparison_background(data)}
        runnable=self._llm.with_structured_output(strict_schema(SynthesisReviews),method='json_schema',strict=True,include_raw=True)
        return self._invoke('review_synthesis',runnable,SynthesisReviews,SYNTHESIS_REVIEW_PROMPT,payload)

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


class AdaptiveFixtureAnalyst(FixtureAnalyst):
    """새 Graph의 오프라인 검사. 실제 시장 평가나 실제 모델 응답이 아니다."""
    def synthesize(self,data,packet,level,targets,previous=None,issues=None):
        from .schemas import SynthesisRow
        rows=[]
        if level:
            for tech,criterion in targets:
                refs=[q for q,p in packet.items() if tech in p['tech_ids']][:1]
                if refs:rows.append(SynthesisRow(tech_id=tech,criterion_id=criterion,
                    observation='가상 검사 자료이며 실제 시장 실적을 입증하지 않는다.',
                    judgment=CRITERIA[criterion]+': 실제 자료 종합과 구별한 오프라인 처리 경로를 검사한다.',
                    quote_ids=refs,relation_to_technology='method_family',conditions=['합성 fixture 결과'],limitations=['실제 시장 평가 아님']))
        return Synthesis(assessments=rows)

    def review_synthesis(self,data,draft,packet,level):
        from .schemas import SynthesisReview
        return SynthesisReviews(reviews=[SynthesisReview(tech_id=r.tech_id,criterion_id=r.criterion_id,
            supported=True,relevant=True,scope_preserved=True,uncertainty_preserved=True,reason='가상 응답 계약 검사') for r in draft.assessments])
