"""실제 LLM과 명시적으로 가상인 오프라인 제공자."""

import json
from datetime import date

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from .prompts import SYSTEM_PROMPT
from .schemas import Analysis, CRITERIA, Question, unknown
from .tools import ProviderError


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
        self._structured = self._llm.with_structured_output(Analysis, method="json_schema", strict=True, include_raw=True)

    def analyze(self, data, evidence, previous=None, issues=None):
        material = []
        for e in evidence.values():
            item = e.model_dump(mode='json')
            if e.segments:
                item.pop('excerpt')  # 문단 본문 중복 전송 방지
            material.append(item)
        payload = {"scope": {"domain": data.domain, "as_of": str(data.as_of)},
            "input_markdown": data.raw_markdown, "input_warnings": data.warnings,
            "criteria": CRITERIA, "evidence": material,
            "previous": previous.model_dump(mode="json") if previous else None, "validation_issues": issues or []}
        try:
            response = self._structured.invoke([("system", SYSTEM_PROMPT), ("human", json.dumps(payload, ensure_ascii=False))])
        except (ValidationError, OutputParserException):
            raise ProviderError("invalid_structured_output") from None
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            fatal = status in {401, 403} or code == "insufficient_quota"
            retryable = not fatal and (status in {408, 429, 500, 502, 503, 504} or type(exc).__name__ in {"APITimeoutError", "APIConnectionError"})
            raise ProviderError(f"openai_{status or type(exc).__name__}", retryable=retryable, fatal=fatal) from None
        self.usage.append(getattr(response.get("raw"), "usage_metadata", None) or {})
        if not isinstance(response.get("parsed"), Analysis) or response.get("parsing_error"):
            raise ProviderError("invalid_structured_output")
        parsed = response['parsed']
        if self.debug:
            self.debug_analyses.append(parsed.model_dump(mode='json'))
        required = {'verdict', 'citations', 'context_findings'}
        checks = [{'tech_id': r.tech_id, 'criterion_id': r.criterion_id,
            'missing': sorted(required - r.model_fields_set), 'basis': r.basis,
            'citations': len(r.citations), 'contexts': len(r.context_findings)} for r in parsed.assessments]
        self.output_checks.append(checks)
        if any(check['missing'] for check in checks):
            raise ProviderError('missing_required_handoff_fields')
        return parsed

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

    def analyze(self, data, evidence, previous=None, issues=None):
        rows = [unknown(t, c, "미확인: fixture 모드에는 실제 시장 근거가 없습니다") for t in data.technologies for c in CRITERIA]
        questions = [Question(tech_id=t.id, criterion_id="market_size_growth", query=f"{t.name} market size adoption official",
            reason="실제 시장 규모·채택 자료 필요") for t in data.technologies.values()]
        return Analysis(assessments=rows, followup_questions=questions)
