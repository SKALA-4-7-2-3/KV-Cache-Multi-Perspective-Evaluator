# KV cache 이해관계자 에이전트

RDKV와 Photonic-CXL의 논문 분석 JSON 두 개와 사용자 요청 JSON을 받아, 클라우드 데이터센터의 LLM 추론 서비스 운영 조직 관점에서 SW와 HW를 비교한다. 기대 이익, 도입 및 운영 부담, 우려 사항과 도입 검토 조건을 근거 문서와 연결한 JSON을 반환한다. 이 폴더는 독립 패키지이며 팀 저장소의 루트 설정을 바꾸지 않는다.

기본 JSON 실행에서는 도메인마다 운영 조직 하나만 분석 대상으로 둔다. 운영자, 개발자, 구매자와 공급자를 별도 이해관계자로 늘리지 않는다. 추가 관심사는 해당 운영 조직의 검토 사항에 반영한다. 논문을 바탕으로 도출한 조건부 영향과 외부 주체의 실제 발언은 구분한다. 논문 자체에 대한 공개 반응을 찾지 못했더라도 근거 있는 운영 영향 분석을 작성할 수 있다.

## 설치와 실행

Python 3.11~3.14, uv를 사용한다. `agent/stakeholder` 폴더에서 실행한다.

```bash
cd agent/stakeholder
uv sync --extra dev
uv run stakeholder-agent --papers examples/papers/rdkv.json examples/papers/photonic-cxl.json --request examples/request.json --as-of 2026-09-22 --demo --output outputs/stakeholders-demo.json
```

`examples/output.fixture.json`에 바로 열어볼 수 있는 출력 예제를 포함했다.

`--demo`는 실제 LangGraph 흐름과 JSON 계약만 검증하는 오프라인 예제다. 모델과 웹 응답은 fixture이며 실제 조사 결과가 아니다. 결과에 실행 모드를 표시한다.

기본 제공자로 실제 외부 조사까지 수행하려면 `OPENAI_API_KEY`, `TAVILY_API_KEY`가 필요하다. OpenAI는 계획, 분석과 검토에 사용하고 Tavily는 검색과 원문 수집에 사용한다. OpenAI 키만으로 외부 검색이 자동 실행되지는 않는다. `.env.example`을 참고해 로컬 `.env`를 만들고 실행한다. 환경 파일은 지정할 때만 읽으며 기존 환경변수가 우선한다.

Tavily 키가 없으면 외부 검색을 건너뛰고 전달받은 논문 근거로 분석한다. 모델 분석과 검토가 성공해도 외부 조사가 빠진 `partial` 결과이며 실제 이해관계자 조사를 완료한 것으로 취급하지 않는다. 팀에서 공용 검색 도구를 제공한다면 Python 호출의 `web=`에 연결해 기본 Tavily 제공자를 대체할 수 있다. 현재 자동 대체 검색기는 없다.

```bash
uv run stakeholder-agent --papers examples/papers/rdkv.json examples/papers/photonic-cxl.json --request examples/request.json --as-of 2026-09-22 --env-file .env --output outputs/stakeholders.json
```

기본 모델은 `gpt-4.1`이며 `--model` 또는 `STAKEHOLDER_MODEL`로 변경한다. 결과는 JSON이며, 상태 안내는 표준 오류로 출력한다. CLI 종료 코드 0은 completed 또는 partial, 2는 failed 또는 입력 파일 오류다. 코드 0이 근거의 충분함을 보장하지 않는다.

## 입력

두 논문 파일은 제공받은 `paper_analysis` 스키마 `1.1.0`을 지원한다. `paper`, `analysis`, `evidence_registry`, `quality`, `run`을 읽으며 두 파일의 순서는 상관없다. 버전이나 계약이 달라지면 명시적인 입력 오류를 반환한다.

`examples/request.json`은 최초 자연어 요청, 분석 목적, 도메인과 사용 상황, 요구조건 및 추가 맥락을 담는다. 여러 도메인은 `domains`에 여러 객체로 전달한다. 도메인은 논문이 연구한 환경에서 추정하지 않는다. 추가 요청 필드도 분석 맥락으로 보존한다.

논문 예제는 사용자가 전달한 실제 RAG 결과다. Git 예제에서는 `paper.source_path`만 `inputs/논문번호.pdf`로 바꾸었으며 분석, 근거 ID와 원문 발췌는 유지했다. 에이전트는 이 경로의 파일을 열거나 upstream 장비에 접근하지 않는다. 받은 JSON의 불완전한 제목과 URL은 프로젝트에서 선정한 논문 정보로 보완하고 출처를 `project_registry`로 구분한다. 누락된 저자, 논문 버전, 발행일을 생성하지 않는다.

일부 발췌는 1,200자에서 잘려 있다. upstream `content_hash`는 원본 청크 해시로 보존하고, 전달된 snippet의 해시는 별도로 계산한다. upstream의 confidence와 supported 판정은 앞단의 요약 검토 기록이며 기술의 진실성 점수나 독립 검증으로 해석하지 않는다.

두 논문과 요청을 한 JSON에 담는 envelope도 지원한다. `schemas/input.schema.json`이 정확한 규격이며 `schema_version`은 이 모듈의 `1.0`이다. upstream 논문 규격의 `1.1.0`과 별개다.

```json
{
  "schema_version": "1.0",
  "run_id": "team-run-001",
  "role": "stakeholders",
  "paper_analyses": ["첫 번째 논문 객체", "두 번째 논문 객체"],
  "request": {"original_request": "사용자 원문", "domains": [{"id": "D-01", "name": "클라우드 데이터센터", "scenario": "LLM 추론 서비스 운영"}]},
  "config": {"as_of": "2026-09-22"},
  "round": 0,
  "budget": {"llm": 5, "search": 6, "fetch": 10},
  "usage": {"llm": 0, "search": 0, "fetch": 0}
}
```

위 `paper_analyses`의 설명 문자열은 실제 논문 객체 두 개로 대체해야 한다. 파일 경로나 파일명 문자열을 대신 넣지 않는다. envelope 파일은 `--input input.json`으로 실행한다. 기준일을 생략하면 실행일을 사용하고 그 사실을 기록한다.

## Python에서 연결

```python
import json
from pathlib import Path
from stakeholder_agent import run_stakeholder

papers = [json.loads(Path(p).read_text()) for p in
          ["examples/papers/rdkv.json", "examples/papers/photonic-cxl.json"]]
request = json.loads(Path("examples/request.json").read_text())
output = run_stakeholder(papers, request=request, as_of="2026-09-22", run_id="team-run-001")
# output은 문자열이 아닌 JSON 직렬화 가능한 dict다.
```

정상 분석과 입력 오류 모두 JSON 결과를 반환한다. `run_detailed`는 테스트용 내부 상태이며 팀 연결에는 사용하지 않는다. 반환되는 Pydantic 출력 모델은 `StakeholderOutput`이다. 원문 JSON을 Markdown으로 변환해서 재해석하지 않는다.

## 출력과 근거

`schemas/output.schema.json`에 공통 필드와 역할별 상세 결과를 정의한다.

- 공통: `schema_version`, `run_id`, `role`, `round`, `execution_status`, `evidence_status`, `result`, `new_evidence`, `gaps`, `follow_up_questions`, `errors`, `usage`
- `result.by_technology`: SW-01과 HW-01의 요약, 평가 항목, 주장, 자료 공백
- `result.details`: 도메인별 운영 조직과 분석 이유, 확인된 발언, 논문 및 웹 근거 기반 추론, 조사 범위, 시사점, 출처 검토, 실행 기록
- 추가 전달 정보: 전체 근거 레지스트리, 실제 인용된 참고문헌, standalone 실행 상태 및 실행 모드

실행 완료와 근거 확보는 별개다. 근거가 없으면 unavailable, 일부만 확보하면 limited로 표시한다. sufficient는 선정된 핵심 집단에 대한 직접 근거와 검토 조건을 충족한 경우에만 사용한다. fixture 결과는 충분한 실제 조사로 표시하지 않는다.

긍정적인 발언을 기술의 적합 판정으로 바꾸지 않는다. 현재 모듈은 실제 발언과 조건부 영향을 조사하며, 목표 요구조건 대비 종합 적합성 판단은 수행하지 않는다. 따라서 공통 평가 항목의 `judgment`는 unknown으로 보류하고 관련 주장과 이유를 연결한다. 기술 선택이나 종합 판단은 후속 단계가 담당한다.

원본 근거 ID를 보존하고 신규 웹 근거에만 새 ID를 발급한다. 실제 발언, 논문 보고, 추론을 구분하며 actor와 관계를 남긴다. 웹 원문, 작성자와 발행 주체, 발행일과 조회일, 사용 범위, 출처 검토 사유 및 한계를 기록한다. 검토에서 거절된 주장과 그 주장에 의존한 요약은 출력하지 않는다. 의미 검토가 완료되지 않으면 검증된 주장으로 내보내지 않는다. 참고문헌에는 실제 인용된 자료만 포함한다.

운영 조직의 결과는 `result.by_technology["SW-01" 또는 "HW-01"].claims`에 있다. `aspect`의 benefit은 기대 이익, burden은 부담과 우려, adoption_condition은 도입 검토 조건이다. 각 결과의 `evidence_ids`와 `supports`를 `evidence` 및 `references`에 연결해 근거 문서와 인용 구절을 확인한다. 공통 JSON 계약은 그대로 유지한다.

검색 후보는 양쪽 모두 논문 자체와 관련 기술 계열을 포함한다. 기본 JSON 실행에서는 검색 결과를 복잡한 키워드 조합으로 선제 제외하지 않고, 입력으로 받은 논문의 중복만 제거한다. 본문이 있는 후보는 `limited` 참고자료로 분석 단계에 전달하며, 논문명 미언급이나 날짜 및 발행자 미확인만으로 제외하지 않는다. 본문 없이 메뉴와 링크만 수집된 자료는 제외하고 누락된 메타정보는 미확인으로 남긴다. 이 처리는 자료의 신뢰성이나 독립 검증을 인증하지 않는다.

분석 단계에서는 요청과 관련 있는 자료를 출처에 귀속한 `statement` 또는 조건부 `inference`로 사용한다. 실제 발언에는 발언자와 관계를 남기며, 추론을 해당 주체의 실제 찬반으로 해석하지 않는다. 각 주장에 원문 인용과 근거 ID를 연결하고 ID 및 인용 검사와 모델 검토를 유지한다. KV 압축 자료를 RDKV 자체의 성과로, CXL 계열 자료를 Photonic-CXL의 실제 도입 사례로 바꾸지 않는다.

기존 Markdown 실행은 모델의 출처 분류 방식을 유지한다. 출처 검토가 누락되면 기존 본문으로 보완하며, 완료된 검토는 본문, 메타정보와 검토 맥락이 동일할 때 유지한다.

## 상위 Graph 연결과 한도

`make_stakeholder_node()`는 설계서 7장의 State로 연결하는 얇은 어댑터다. `paper_analyses`, `request`, `run_id`, `config`, `usage`, `review.round`를 읽고 자기 역할의 변경분만 반환한다.

```python
from stakeholder_agent import make_stakeholder_node

stakeholder_node = make_stakeholder_node()
# parent_graph.add_node("stakeholders", stakeholder_node)
```

상위 Graph에서 `assessments`와 `usage`는 역할별로 병합하고, `evidence`와 `errors`는 ID별로 병합해야 한다. 누적 사용량을 합산하지 않는다. 상류 논문 근거를 공통 evidence에 등록한 뒤 이 노드를 실행해야 한다. 기존 팀 검증 에이전트의 다른 RoleResult 스키마에 그대로 연결하는 어댑터는 아니다. 자세한 차이는 `INTEGRATION.md`를 참고한다.

기본 실행은 계획, 분석, 의미 검토의 3회 모델 호출이며, 내부 보완 최대 1회와 전체 모델 호출 최대 5회를 적용한다. 검색 6회, 원문 조회 10회가 기본 상한이다. API 제공자의 숨은 재시도는 끄고 전송 재시도는 현재 구현에서 수행하지 않는다. 설계서의 최대 1회 이내인 보수적인 실행 정책이다. 한도는 `AgentConfig` 또는 CLI에서 설정하며 입력 budget은 이 실행 상한을 더 낮출 수 있다. 입력 usage는 앞선 상위 회차까지 사용한 누적값이다. 내부 보완과 재실행에서 이를 초기화하지 않는다.

이번 빠른 결과 확인은 `repair_limit=0`으로 설정해 보완 반복 없이 최대 3회 모델 호출로 끝낸다. 기본 보완 한도 1회는 유지하며, 테스트는 결과 확인 이후로 미룬다.

## 검증과 Git 포함 범위

```bash
uv run pytest -q
uv run ruff check .
uv build
```

코드, 테스트, 예제 JSON, 스키마, 문서와 의존성 잠금 파일을 포함한다. `.env`, `.venv`, 실제 실행 출력, 내부 진단, 빌드 파일과 캐시는 `.gitignore`로 제외한다. 실제 검증 범위와 제약은 `VALIDATION.md`에 기록한다.

이전 Markdown 입출력은 `stakeholder_agent.legacy`와 `stakeholder_agent.legacy_cli`에만 남아 있다. 새 기본 함수와 CLI는 JSON을 사용한다.
