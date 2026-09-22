# 시장조사 에이전트 JSON 전달 계약 1.0.0

최종 파일은 **`market_handoff.json` 한 개**다. CLI의 fixture/live, 저장 결과 재검증 모두 이 파일을 출력한다. 기존 MD 출력은 과거 기록으로 보존하며 새 실행은 MD를 생성하지 않는다.

## 소비 방법

```python
import json

with open("market_handoff.json", encoding="utf-8") as file:
    handoff = json.load(file)
assert handoff["schema_version"] == "1.0.0"
assert handoff["role"] == "market"
for row in handoff["assessments"]:
    key = (row["tech_id"], row["criterion_id"])
    # verdict와 evaluation_mode, generation_method, conditions, gaps를 함께 전달한다.
    print(key, row["judgment"])
```

## 최상위 필드

| 필드 | 의미 |
| --- | --- |
| schema_version, role | JSON 전달 계약 버전과 역할 `market` |
| run_id, as_of, domain | 실행 식별자, 평가 기준일, 적용 도메인 |
| mode, status, execution_status | fixture/live, 평가 상태, 실제 처리 상태 |
| provenance | 입력 해시, 사용 모델, 원래 내부 결과 버전 |
| coverage | expected/provided 및 grounded/provisional/scenario/research_plan 개수 |
| technologies | tech_id, name, approach, paper, paper_url, status |
| assessments | 입력 기술마다 시장성 평가 6개. 기술 2개면 12개 |
| sources | 평가에서 실제 사용한 evidence_id를 키로 하는 출처 사전 |
| errors | 처리 실패의 stage/code 및 관련 기술·항목·공개 URL |
| warnings | fixture 표시와 입력 해석 시의 경고 |

## 평가 항목과 출처

`assessments`에는 `tech_id`, `criterion_id`, `criterion_name`, `observation`, `judgment`, `verdict`, `basis`, `relation_to_technology`, `evaluation_mode`, `generation_method`, `evaluation_level`, `confidence`, `conditions`, `gaps`, `metric`, `research_status`, `unknown_reasons`, `citations`, `supporting_materials`, `context_findings`가 들어간다.

항목 ID: `market_size_growth`, `commercialization`, `adoption`, `ecosystem_support`, `standardization`, `business_value`.

- `citations`는 검증 주장에 연결된 출처, `supporting_materials`는 참고자료다. 서로 같은 검증 수준으로 취급하지 않는다.
- `context_findings`의 진술·조건·수치·출처도 보존한다.
- 모든 참조의 `evidence_id`는 `sources`에 존재한다. 출처에는 제목, 공개 URL, 발행자·날짜, 접근 상태·범위와 짧은 발췌가 있다. 원문 위치는 해당 참조에 포함한다.
- `sources[evidence_id].quote_excerpt`는 URL당 최대 25단어 범위의 짧은 발췌다. `quote_truncated`가 true이면 전체 인용문이 아니다. 같은 URL의 다른 출처에 발췌가 있으면 null일 수 있다. 전체 원문은 내부 캐시에 보존한다.
- 값이 없는 수치는 null, 목록은 []다. v1.4 이력에는 evaluation_level 기록이 없어 null이며 생성 방식은 당시 grounded/정형 평가 경로를 기준으로 표시한다. 한국어는 UTF-8로 저장하고 Markdown 이스케이프나 HTML 표로 변환하지 않는다.

## 해석과 이전 결과

`provisional`은 관련 자료에 따른 잠정 판단이다. `deterministic_fallback`은 정형 비상 출력이고 `model_synthesis`는 모델 종합 결과다. 처리 상태가 `partial`/`failed`이면 결과의 조건·한계와 오류를 함께 전달해야 한다. fixture는 실시장 평가로 사용하지 않는다.

출력 형식 변경은 판단 내용을 다시 조사하거나 검증했다는 뜻이 아니다. 내부 상태 버전 0.6과 외부 JSON 계약 1.0.0은 별개다. 내부 캐시의 프롬프트·검색 기록·토큰 사용량·전체 원문·원본 JSON은 전달하지 않는다. 부모 Graph 내부 연결 함수 `parent_update`는 기존 계약을 유지한다. 메모리에서 최종 JSON과 같은 객체가 필요하면 `market_agent.handoff.build_handoff(state)`를 사용한다.
