# 평가 검증·종합 Agent
판교 7반 2조 / 백순철. RDKV(SW-01)와 Photonic-CXL(HW-01)의 상위 평가를 받아 검증하고, 세 관점을 연결한 새 의견을 보고서 담당자에게 전달한다.

## 현재 역할과 범위

상위 technical·market·stakeholders·domain → 규칙 검사·최종 TRL 판정 → 새 종합 의견 → 입력·근거와 의미 대조 → Markdown.
의미 검사에서 반려되면 한 번 수정하고 재검사한다. 계속 반려되거나 검사에 실패하면 보고서 전달을 차단한다. 실행 중 사람 승인 단계는 없다.
새 의견은 시장·이해관계자·도메인 평가를 각각 연결한 조건부 추론이다. 최종 보고서 편집·LaTeX/PDF는 후단 담당이다.
technical은 단계별 `trl_checks`와 출처를 제공한다. review가 유효한 v1 근거를 확인하고, 1단계부터 연속 확인된 최고 단계를 최종 추정 TRL로 정한다.
근거가 없으면 `null`/미확인으로 남긴다. 비용·독립 재현 자료 부족으로 확인된 하위 TRL을 취소하지 않는다.
MD 5절에는 최종 TRL과 1~9단계의 판정·이유·Evidence ID를 전달한다. 이 판정은 규칙 처리이며 추가 LLM 호출이 없다.
별도 검색·논문 재인덱싱·별도 Graph Agent는 추가하지 않는다. 의미 검사기는 이 모듈 내부의 제한된 모델 호출이다.
시장·도메인 브랜치의 파일은 확인했으나 네 상위 역할의 계약 입력이 모두 준비되지는 않았다. 후단 보고서 Agent까지의 전체 실행은 미검증이다.

## 설치와 실행

Python 3.12 또는 3.13. 저장소의 `agent/review` 폴더에서:

```bash
python -m pip install ".[review-graph,review-llm]"
python -m team_review.examples.paper_case --output-dir outputs/check-only
python -m team_review.examples.paper_case --synthesize --env-file .env --output-dir outputs
```

기존 환경은 python 대신 ./.venv/bin/python을 쓰면 된다.
첫 실행은 API 없는 진단 모드(보고서 생성 차단), 마지막 명령은 생성·검사 API 2회, 수정 시 최대 4회(과금 가능).
명시한 --env-file은 셸의 같은 이름 설정보다 우선한다. 키·.env 파일은 GitHub나 팀원에게 보내지 않는다.

출력은 기본적으로 **outputs/review.output.md 하나**다.
개발용 JSON은 --debug-json을 추가했을 때만 생성한다.
모의 상위 Agent 입력은 [examples/paper.input.md](examples/paper.input.md)에 포함되어 PDF 없이 재생 가능하다.
PDF 재대조는 --verify-sources에서만 실행하며 pypdf, pdftotext와 프로젝트 data/team_review_sources/ 원문 두 편이 필요하다.
과거 로컬 실험 기록과 JSON·ZIP은 이 브랜치에 포함하지 않는다. outputs/review.output.md가 전달 형식의 실행 샘플이다.

## 앞 Agent 연결

Graph 안에서는 dict를 전달한다. CLI 파일 입력은 동일 State 구조의 JSON 또는 review-input-v1 Markdown의 단일 YAML 블록이다.
자유 형식 MD를 추측해서 변환하지 않는다. [실행 가능한 입력 예시](examples/paper.input.md)를 따른다.

```python
from team_review import ReviewState, parse_input_markdown
from team_review.schema import RoleResult

# 각 역할은 다른 역할의 결과를 덮어쓰지 않는다.
return {"assessments": {"market": RoleResult.model_validate(result).model_dump(mode="json")},
        "documents": new_documents, "evidence": new_evidence}
```

- 역할 키: technical / market / stakeholders / domain. 각 results에 SW-01/HW-01.
- documents/evidence/errors: 동일 ID·동일 값은 병합, 다른 값은 오류.
- assessments: 역할별 단일 작성자. 같은 회차의 다른 결과는 오류, 다음 회차만 교체.
- 검색 담당자가 Evidence ID와 verified_source를 발급한다. LLM이 새 출처를 만들면 안 된다.
- config.normalized_domain의 id/name 필수. config.raw_domain_input은 사용자의 원문 그대로.
- 도메인 요구값은 config.domain_requirements, favorable/unfavorable의 criterion별 근거 요구는 config.requirements.
- Evidence에 원문 위치·방법·독립성, 웹 Document에 source_type을 명시한다.
- 필수 항목 46개 및 TRL 기준: [DESIGN-6.md](DESIGN-6.md), rubric.py, schema.py.
- 선택 도메인 밖의 자료는 analysis_scope=global/mixed 및 domain_relevance로 한계를 표시한다.
- 입력 기본값 mixed/unclear/unavailable은 독립 검증이나 높은 신뢰도를 뜻하지 않는다.
- 실제 실행은 `config.demo=false`를 명시한다. 생략·모의 근거·역할의 `demo=true`·테스트 생성기 사용은 최종 실행으로 표시하지 않는다.
- `config.domain_requirements` 키: context_tokens, concurrency, ttft, tpot, quality, gpu_model, gpu_memory, energy, cost, prefix_cache_hit_rate, input_output_token_ratio. 입력한 0·범위·시나리오는 보존하고 미입력은 TBD.
- `basis=opinion`은 `attributed_to`(발언 주체)와 Evidence가 필요하다. `stakeholder_group`에는 경쟁사/도입 운영자/개발자/공급사/투자·분석·미디어 등 입력의 실제 집단을 쓴다.
- 평가와 Evidence의 `technology_relevance=direct/indirect/unknown`은 선택 기술과의 관련성이다. 인접 CXL 시장과 선택 논문의 직접 시장을 구분한다.
- Evidence `independence=author/independent/unknown`; 기존 vendor/third_party 입력도 호환한다. `method=hardware_measurement`를 GPU 실험·에뮬레이션·시뮬레이션과 구분한다.
- 원문 조건 일부가 빠진 유효 Metric은 값·출처와 함께 남기되 조건을 unknown으로 표시하고 직접 비교를 제외한다.

## LangGraph 연결

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from team_review import ReviewState, review_agent_node, route_to_report, prepare_repair

builder = StateGraph(ReviewState)
# 상위 역할 노드 등록 및 technical → 세 분석 병렬 실행은 팀 Graph가 담당
builder.add_node("review", review_agent_node)
builder.add_edge(["market", "stakeholders", "domain"], "review")
builder.add_conditional_edges("review", route_to_report, {
    "repair": "repair", "report": "report", "diagnostic": "diagnostic"
})
# repair/report/diagnostic 노드는 팀 Graph에 등록한다.
# repair에서 prepare_repair(state)를 적용하고 dirty_roles만 다시 실행한다.
graph = builder.compile(checkpointer=InMemorySaver())
```

이 코드는 연결 지점을 설명하는 조각이며 독립 실행 스크립트가 아니다.
팀이 이미 checkpoint를 쓰면 그 saver를 재사용한다. InMemorySaver는 테스트용이며 프로세스 종료 뒤 복구되지 않는다.
SQLite 영속성은 팀 통합 Graph에 연결해야 한다. 이 모듈이 별도 DB를 몰래 만들지 않는다.
thread_id와 max_concurrency=3, recursion_limit=20은 호출자가 지정한다.

모델: gpt-4.1-mini (config.synthesis_model로 변경 가능).
생성→검사는 정상 2회, 내용 수정이 필요해도 최대 4회다. 호출당 timeout=120초, SDK 재시도는 0회다.
생성 출력 상한은 8000토큰, 검사 출력 상한은 4500토큰이다. 검사 응답 오류·거절은 통과가 아니라 차단이다.
도구: review_node, validate_opinions, validate_audit의 Python 전·후처리. 별도 tool calling/검색 없음.
시스템 프롬프트: [SYNTHESIS-PROMPT.md](SYNTHESIS-PROMPT.md), [GROUNDING-PROMPT.md](GROUNDING-PROMPT.md).
체크포인터: 위 Graph의 saver. 입력·모델·두 프롬프트가 같고 의미 검사 통과 및 출력 해시가 일치할 때만 재사용한다.
상위 4회 + 종합부 2회가 정상 경로이며 최종 보고서 Agent의 호출은 별도다.
종합 실패를 성공으로 위장하지 않고 미완료와 한계를 출력한다.

## 뒷 Agent 연결

필수 입력은 **outputs/review.output.md 원문 하나**다. 별도 환경에 검사기까지 전달하려면 `python -m team_review.handoff`로 만든 outputs/report_handoff.zip을 사용한다.
[REPORT-HANDOFF.md](REPORT-HANDOFF.md)는 전달 폴더 기준 경로와 실제 포함된 검사 패키지를 설명한다.
출력은 [OUTPUT-CONTRACT.md](OUTPUT-CONTRACT.md)의 최종 계약(report-input-v1/reference-v1/kv-cache-rubric-v1)을 따른다.
묶음에서는 계약서명을 `review.output.contract.final.md`로 통일한다.

```python
from pathlib import Path
from team_review import read_report_input
md = Path("outputs/review.output.md").read_text(encoding="utf-8")
metadata, body = read_report_input(md)
# 차단/보완 대기라면 위에서 예외. 통과 후 md 전체를 후단 LLM의 입력 데이터로 제공.
```

## 검증

```bash
python -m unittest discover -s team_review/tests -v
python -m team_review --demo all --output-dir outputs/demo
```

테스트: 기존 검수, 실제 production State 병렬 합류/재평가/체크포인트, MD 왕복,
8칸/46블록 집계, 실패·미확인 구분, 인용/Reference/placeholder 검사, 새 의견 3관점 연결과 실패 처리.
생성 문장의 결론·조건·위험·미확인을 연결된 입력·근거와 자동 대조한다. 자료 공백을 실제 부재로 바꾸거나 추론을 당사자 발언으로 바꾸면 반려한다.
검사 모델도 오판할 수 있으므로 완전한 진실성 보증은 아니다. 상위 자료 자체의 오류·공백을 새 사실로 채우지 않는다.
단위 테스트의 생성기·검사기는 명시적 스텁이다. 제어 흐름 테스트 통과가 모델의 의미 판단 정확도 측정값은 아니다.
human_review_required는 기존 계약 호환용이며 human_review_scope=final_submission_only다. 실행 중 사람의 수정·승인을 기다리지 않는다.
코드가 업무별 입력 평가를 배정하고 해당 근거 ID를 그대로 계승한다. 모델은 배정된 범위에서 분석 문장만 작성한다.
요약의 위험·제약은 네 관점의 counter_evidence/gaps와 검증된 종합 의견에서 함께 수집한다.
상위가 위험을 작성하지 않았으면 ‘미평가·미확인’으로 남기며 ‘위험 없음’으로 바꾸지 않는다.
일치·상충·조건 비교·병행은 두 기술 각각 결과나 구체적인 보류 사유가 필요하다.
병행 결론은 joint에서만 작성해 조건 비교 섹션과 모순되지 않게 한다.
`read_report_input(md, for_submission=True)`는 모의·차단·보완 대기·종합 미완료를 거부한다. 실제 실행의 partial은 unknown을 보존한 allowed_with_gaps로 허용한다.
공식 Structured Outputs를 참고해 Pydantic 응답 스키마와 거절/미완료 처리를 적용했다:
[OpenAI 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs).

2026-09-22 전달 요구 반영 검증: 회귀 테스트 102개 통과. 첫 API 시험은 미확인을 실제 미검증으로 표현해 규칙 검사에서 차단되었다.
표현 예시·조건 필드 지시를 보완한 두 번째 시험은 생성 1회 + 의미 검사 1회로 통과했다. 실행마다 최대 1회 수정 한도는 유지했다.
현재 샘플은 8/8칸·46/46항목, unknown 10개·Evidence 13개·Reference 2개이며 `demo:true`, `partial/allowed_with_gaps`다.
프롬프트 보완은 [GPT-4.1 공식 안내의 구체적인 지시·예시·평가 원칙](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-4.1)을 참고했다. 모델·API·호출 한도는 바꾸지 않았다.

## GitHub에 올릴 범위

team_review/ 전체와 루트 pyproject.toml을 함께 올린다. 설치 패키지에 모듈·프롬프트·입력 fixture가 포함된다.
원하면 outputs/review.output.md를 공개 논문 기반 실험 샘플로 첨부한다.
.env, .venv, 비공개 자료, 캐시·빌드 파일은 제외한다. 이 브랜치의 pyproject.toml은 team_review만 독립 설치한다.
