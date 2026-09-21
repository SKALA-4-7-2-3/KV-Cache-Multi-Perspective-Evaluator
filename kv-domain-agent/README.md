# KV Cache 도메인 평가 에이전트

설계보고서의 `domain` 역할만 독립 구현한 패키지입니다. 평가 대상은 **RDKV(SW-01)** 와 **Photonic-CXL(HW-01)**, 주 도메인은 **장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙**입니다.

이 모듈은 **RAG를 사용하지 않습니다.** 검색기·벡터DB·웹 도구를 만들거나 호출하지 않고, 선행 `technical` 에이전트가 State에 넣은 기술 요약과 근거만 읽습니다. LLM 호출은 근거를 도메인 요구조건에 대응시키는 구조화 분석 1회뿐입니다.

## 구현 범위

- 두 기술 × 도메인 10개 기준을 동일한 스키마로 평가
- `favorable / conditional / unfavorable / unknown / not_applicable` 판정
- 입력에 존재하지 않는 `evidence_id` 인용 차단
- SW 평가의 HW 근거 인용 및 HW 평가의 SW 근거 인용 차단
- 기술 조사 에이전트의 원본 `paper_analysis` JSON 2개를 변경 없이 변환
- 실제 실행에서 `is_demo=true` 근거 차단
- 근거가 없으면 LLM을 호출하지 않고 `unknown` 반환
- 에이전트 실행 실패(`failed`)와 기술의 부적합(`unfavorable`) 분리
- 병렬 실행 시 `assessments["domain"]`만 갱신
- 동일 회차 충돌을 막고 새 회차만 교체하는 reducer 제공
- API 없이 배선·스키마를 확인하는 `--mock` 모드와 단위 테스트 제공

## 디렉터리

```text
kv-domain-agent/
├── main.py                       # 간단 실행 진입점
├── requirements.txt             # 팀 환경용 의존성 목록
├── examples/
│   ├── input_state.json          # 입력 계약 + 모의 데이터
│   └── langgraph_integration.py  # 팀 그래프 연결 예시
├── src/kv_domain_agent/
│   ├── agent.py                  # 입력 구성, LLM 호출, 근거 검증
│   ├── adapters.py               # 팀원 paper_analysis JSON → 공용 State
│   ├── models.py                 # Pydantic 입력·출력 스키마
│   ├── node.py                   # LangGraph node factory
│   ├── prompt.py                 # 중립 평가·RAG 금지 프롬프트
│   ├── state.py                  # 병렬 병합 reducer 예시
│   ├── mock_model.py             # 오프라인 배선 확인용
│   └── cli.py                    # 독립 실행 CLI
└── tests/test_agent.py
```

## 1. 설치

팀 프로젝트의 Python 3.11+ 가상환경에서 실행합니다.

```bash
cd kv-domain-agent
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[openai,graph]"
```

팀이 `requirements.txt` 방식을 쓰면 `pip install -r requirements.txt`로 설치해도 됩니다.

`pydantic`만으로 테스트·모의 실행을 하려면 다음으로 충분합니다.

```bash
pip install -e .
```

## 2. API 없이 먼저 확인

```bash
kv-domain-agent \
  --input examples/input_state.json \
  --output outputs/domain.mock.json \
  --mock
```

또는 설치하지 않고:

```bash
PYTHONPATH=src python -m kv_domain_agent.cli \
  --input examples/input_state.json \
  --output outputs/domain.mock.json \
  --mock
```

editable 설치 후에는 같은 명령을 `python main.py ...`로 실행할 수도 있습니다.

`examples/input_state.json`의 `DEMO-*` 근거는 연결 시험용 가짜 자료입니다. 생성된 mock 결과를 최종 평가보고서에 사용하면 안 됩니다.

## 3. 실제 LLM으로 실행

```bash
export OPENAI_API_KEY="..."       # Windows PowerShell: $env:OPENAI_API_KEY="..."
export DOMAIN_AGENT_MODEL="gpt-4.1-mini"

kv-domain-agent \
  --input path/to/team_state.json \
  --output outputs/domain.json
```

팀원이 생성한 `paper_analysis` JSON 두 개를 그대로 사용할 때는 `--sw-analysis`와
`--hw-analysis`를 함께 지정합니다. 기존 파일을 수정하거나 이름을 바꿀 필요가 없습니다.

Windows CMD:

```bat
python main.py --input examples\input_state.json --sw-analysis path\to\rdkv_paper_analysis.json --hw-analysis path\to\photonic_cxl_paper_analysis.json --output outputs\domain.real.json --model gpt-4.1-mini
```

macOS/Linux:

```bash
python main.py \
  --input examples/input_state.json \
  --sw-analysis path/to/rdkv_paper_analysis.json \
  --hw-analysis path/to/photonic_cxl_paper_analysis.json \
  --output outputs/domain.real.json \
  --model gpt-4.1-mini
```

adapter는 팀원 JSON의 `status: succeeded`, `analysis`, `paper`,
`evidence_registry`를 읽어 `assessments.technical`, `documents`, `evidence`로
변환합니다. 근거 ID는 `SW-01::...`, `HW-01::...`로 이름공간을 분리합니다.
`examples/input_state.json`의 DEMO 근거는 변환 시 제거됩니다.

실제 모드에서 DEMO 근거가 남아 있으면 API 호출 대신 오류로 종료합니다. DEMO 자료는
`--mock` 모드에서만 허용됩니다.

설계서와 맞춰 `temperature=0`, 요청 timeout 60초, 전송 재시도 1회, Pydantic 구조화 출력을 사용합니다. 모델명은 팀 공통 설정에 맞춰 `--model` 또는 `DOMAIN_AGENT_MODEL`로 바꿀 수 있습니다.

## 4. 팀 LangGraph에 합치기

팀 공용 State에는 최소한 다음 세 경로가 있어야 합니다.

```text
config.domain
assessments.technical
evidence
```

노드를 생성합니다.

```python
from kv_domain_agent.node import make_domain_node

domain_node = make_domain_node(model_name="gpt-4.1-mini")
builder.add_node("domain", domain_node)
```

기술 조사 후 시장·이해관계자·도메인을 병렬로 연결하고 세 분기가 끝난 뒤 review로 합류합니다.

```python
builder.add_edge("technical", "market")
builder.add_edge("technical", "stakeholders")
builder.add_edge("technical", "domain")
builder.add_edge(["market", "stakeholders", "domain"], "review")
```

세 병렬 노드가 모두 `assessments`를 갱신하므로 공용 State의 해당 키에는 reducer가 필요합니다.

```python
from typing import Annotated
from typing_extensions import TypedDict
from kv_domain_agent.state import merge_role_assessments, merge_strict_by_key

class TeamState(TypedDict, total=False):
    config: dict
    evidence: Annotated[dict, merge_strict_by_key]
    assessments: Annotated[dict, merge_role_assessments]
    errors: Annotated[dict, merge_strict_by_key]
    review: dict
```

이 노드는 성공 시 아래 **부분 업데이트**만 반환합니다.

```python
{"assessments": {"domain": {...}}}
```

실패 시에도 그래프를 깨지 않고 다음처럼 합류합니다.

```python
{
  "assessments": {"domain": {"status": "failed", "...": "..."}},
  "errors": {"domain:r0:...": {...}}
}
```

`failed`는 에이전트/입력/API 실패이고, `unfavorable`은 근거가 있는 기술 부적합 판정입니다. review 에이전트에서 둘을 섞지 마십시오.

## 5. 입력 계약

### `config.domain`

10개 기준을 정확히 한 번씩 정의해야 합니다.

1. `capacity`
2. `quality`
3. `latency_predictability`
4. `throughput`
5. `gpu_compatibility`
6. `dedicated_hardware_dependency`
7. `deployment_complexity`
8. `maturity`
9. `customer_value`
10. `domain_fit`

각 항목의 `target`은 가능하면 수치 또는 검증 가능한 정성 조건으로 작성합니다. 목표가 미정이면 모델이 적합·부적합을 단정하지 못하도록 프롬프트와 후처리 규칙을 두었습니다.

### `assessments.technical`

기술 조사 에이전트가 다음 구조로 넘겨야 합니다.

```json
{
  "status": "completed",
  "technologies": [
    {
      "technology_id": "SW-01",
      "name": "RDKV",
      "approach": "SW",
      "summary": "...",
      "experimental_conditions": ["모델", "GPU", "문맥 길이", "동시성"],
      "limitations": ["..."],
      "evidence_ids": ["SW-01-p12-c03"]
    },
    {
      "technology_id": "HW-01",
      "name": "Photonic-CXL",
      "approach": "HW",
      "summary": "...",
      "experimental_conditions": ["에뮬레이션/시뮬레이션 여부", "호스트 경로"],
      "limitations": ["..."],
      "evidence_ids": ["HW-01-p08-c02"]
    }
  ]
}
```

### `evidence`

키와 내부 `id`가 같아야 합니다. 도메인 모델에는 기술 요약이 참조한 ID와 `config.domain.shared_evidence_ids`만 전달됩니다. 다른 역할의 근거나 미참조 문서는 자동 제외됩니다.

```json
{
  "SW-01-p12-c03": {
    "id": "SW-01-p12-c03",
    "doc_id": "SW-01",
    "page": 12,
    "location": "§4.2, Table 3",
    "excerpt": "원문 발췌",
    "conditions": ["모델/하드웨어/문맥 조건"],
    "criterion_ids": ["capacity", "quality"],
    "basis": "direct"
  }
}
```

## 6. 테스트

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

테스트는 다음을 확인합니다.

- 두 기술 각각 10개 기준 출력
- 미참조 근거가 LLM 입력에 포함되지 않음
- 모델이 만든 가짜 근거 ID 거부
- 다른 기술에 속한 근거 ID 인용 거부
- 실제 실행에서 DEMO 근거 거부
- 원본 paper_analysis JSON adapter 검증
- 근거가 없을 때 LLM 미호출 + `unknown`
- 노드가 자기 역할 키만 갱신
- 잘못된 입력을 명시적 `failed` 상태로 변환
- reducer의 동일 회차 충돌 차단과 새 회차 교체

## 7. 담당자 체크리스트

- `examples/input_state.json`의 DEMO 자료를 기술 조사 에이전트 출력으로 교체
- 팀의 공용 기술 ID와 `SW-01`/`HW-01` 일치 확인
- 10개 목표 요구조건을 팀 합의 값으로 구체화
- domain 노드에 retriever·vector store·web tool을 bind하지 않기
- 실제 결과의 핵심 인용을 원문 페이지와 사람이 대조
- review에서 기술 × 관점 8칸 및 evidence ID 존재 여부 검사
- repair 회차에서는 `review.round`를 올려 새 결과만 이전 결과를 교체

## 설계 의도

LangGraph 노드는 전체 State가 아니라 부분 업데이트를 반환할 수 있으므로, 도메인 노드는 병렬 분기에서 자기 역할 키만 씁니다. `assessments` reducer가 역할별 결과를 병합하고 같은 회차의 이중 작성을 오류로 처리합니다. LLM 구조화 출력은 형식을 보장하지만 사실성을 보장하지 않기 때문에, 코드가 다시 허용 근거 ID와 판정-근거 관계를 검사합니다.
