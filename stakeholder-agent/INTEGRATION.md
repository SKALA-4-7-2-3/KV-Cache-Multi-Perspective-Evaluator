# 팀 통합 메모

이번 모듈은 두 개의 paper_analysis JSON(1.1.0), 별도 request JSON, 설계서 최신 7.1~7.4를 기준으로 작성했다. 다른 역할의 코드나 루트 설정은 수정하지 않는다.

## 현재 확인된 차이

1. 첨부 설계서 22쪽에는 이전 State 표가 남아 있다. completed/unknown/failed와 기존 Assessment 규격보다 16~21쪽의 새 공통 구조를 우선 적용했다.
2. 조사한 시점의 feat/review-agent는 `status/results[tech].items` 형태와 고정 criterion_id 4개(competitors, adopters, developers, investors_analysts_media)를 요구한다. 이 모듈은 도메인별 운영 조직 하나의 영향 분석과 `execution_status/evidence_status/result.by_technology/details`를 사용한다. 검증 담당자가 새 계약을 반영하거나 별도 합의한 변환기를 만들어야 한다. 어떤 집단도 억지로 고정 4개에 포함하거나 의견을 만들어 넣지 않는다.
3. 도메인 에이전트와 검증 에이전트의 config.domain 형식도 다르다. 본 모듈은 request.domains 배열을 사용한다. 팀 전체를 합친 실행을 완료한 것은 아니다.
4. 설계서의 임베딩 모델은 Qwen3-Embedding-0.6B이나 제공받은 JSON run.embedding_model은 gemini-embedding-2다. upstream 실행 기록을 그대로 보존했다. 이해관계자 에이전트가 RAG를 다시 실행하거나 이 기록을 바꾸지 않는다.
5. 제공된 입력에는 논문 버전, 완전한 제목, 발행일 등 일부 메타정보가 없다. 정체성은 선택된 프로젝트 논문 쌍으로 확인하고 보완 경로와 미확인 항목을 기록한다.

## 입출력 계약

직접 함수 호출은 `run_stakeholder([sw_json, hw_json], request=request_json)`이다. envelope에서는 `paper_analyses`에 원본 두 객체를 넣는다. source_path는 다른 장비의 위치 정보일 뿐이며 파일 읽기에 사용하지 않는다.

인증 정보는 입력 JSON에 넣지 않는다. 같은 프로세스에서 실행한다면 부모 프로그램에서 환경변수를 한 번 설정하고 노드를 호출할 수 있다. 기본 외부 조사 도구는 Tavily지만, `run_stakeholder(..., web=shared_web)` 또는 `make_stakeholder_node(web=shared_web)`로 팀 공용 검색 도구를 주입하면 이 모듈의 Tavily 키는 필요 없다. 공용 도구는 `providers.py`의 `WebProvider` 계약에 맞게 `search(query, max_results)`와 `fetch(url)`을 구현해야 하며 검색 결과와 원문을 구분해야 한다.

부모 노드의 입력 State에는 `paper_analyses`, `request`, `run_id`를 둔다. 부모의 `config.budgets.stakeholders`는 llm/search/fetch 절대 한도, `usage.stakeholders`는 같은 키의 누적 사용량이다. `review.round`는 상위 회차이며 내부 보완 회차와 구별한다. 사용한 모델과 프롬프트 버전은 출력 실행 기록에 남는다.

`to_state_update(output)`은 assessments의 stakeholders 키, 신규 evidence, usage의 stakeholders 키, errors만 반환한다. JSON 자체의 status는 이 standalone 모듈 실행 상태이며 부모 전체 Graph의 status를 덮어쓰지 않는다. 부모는 신규 근거 ID 충돌을 검사하고 누적 usage는 교체해야 한다. 상류 논문 근거는 부모의 준비 또는 기술 조사 단계에서 등록한다.

실제 공동 검증 전에 팀이 확정할 사항은 공통 envelope 버전, criterion_id 의미, 근거 객체 형식 및 상태별 종료 규칙이다. API 메서드명만 같다고 데이터 계약이 호환되는 것은 아니다.
