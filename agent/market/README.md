# 시장조사 에이전트

기술 조사 결과 JSON을 받아 RDKV와 Photonic-CXL의 시장성을 조사하고, 통합 에이전트에 전달할 **`market_handoff.md` 한 개**를 생성합니다. LangGraph로 검색·본문 검사·근거 추출·평가 작성·최대 1회 보완을 제어합니다.

## 폴더 구성

| 위치 | 내용 |
| --- | --- |
| `market_agent/` | Python 코드, 입력 샘플, 회귀 테스트, 상세 사용 안내 |
| `docs/` | 설계, 시장성 출력 양식, 이전 실습 가이드 검토 기록 |
| `tasks/` | 구현·수정 계획과 완료 기록 |
| [`deliverables/market_handoff_20260922_v11_reviewed.md`](deliverables/market_handoff_20260922_v11_reviewed.md) | v1.1 실행 후 원문과 대조하여 표현을 교정한 공유용 검토본 |
| `deliverables/market_handoff.md` | 이전 실행 전달본(비교·추적용 보존) |
| `requirements.txt`, `requirements.lock.txt`, `.env.example` | 직접·간접 의존성 고정 버전과 빈 API 키 양식 |

## 설치와 실행

VS Code에서 이 `agent/market` 폴더를 열거나, 저장소 루트에서 `cd agent/market`으로 이동합니다. **Python 3.11**을 사용합니다. `requirements.txt`는 함께 있는 `requirements.lock.txt`의 하위 의존성 버전도 적용합니다. 두 파일을 함께 보관하세요.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 입력 구조 확인: API 호출 없음
python -m market_agent.cli --input market_agent/fixtures/paper_analysis_sw.json market_agent/fixtures/paper_analysis_hw.json --mode parse

# 고정 응답으로 전체 흐름 확인: API 호출 없음
python -m market_agent.cli --input market_agent/fixtures/paper_analysis_sw.json market_agent/fixtures/paper_analysis_hw.json --mode fixture
```

Windows에서는 가상환경 생성에 `py -3.11 -m venv .venv`, PowerShell 활성화에 `.venv\Scripts\Activate.ps1`을 사용합니다. Windows 실행은 별도로 검증하지 않았습니다.

실제 조사에는 이 폴더의 `.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`, `TAVILY_API_KEY`를 입력합니다. `.env`가 이미 있다면 새 파일로 덮어쓰지 않습니다. 실제 키는 저장소에 포함하지 않았습니다.

```bash
python -m market_agent.cli --input market_agent/fixtures/paper_analysis_sw.json market_agent/fixtures/paper_analysis_hw.json --mode live
```

`live` 실행은 Tavily와 OpenAI API를 호출하며 계정 사용량이 발생합니다. 기본 모델은 `gpt-4.1-mini`입니다. 기술 조사 결과 schema_version 1.1.0 JSON 한 개 또는 두 개를 `--input`에 지정합니다. 기본 조사 기준일은 실행일이며 `--as-of YYYY-MM-DD`로 고정할 수 있습니다. [JSON 입력 안내](docs/JSON_INPUT.md)에 필드 연결·옵션·실제 첨부 검증 결과가 있습니다. 기존 MD v0.1 입력도 지원합니다. 프로세스 환경변수가 `.env`보다 우선하며, `--env-file`로 별도 설정 파일을 지정할 수 있습니다.

기본 출력은 `market_agent/outputs/<실행시각>/market_handoff.md`입니다. `--output <새 폴더>`로 바꿀 수 있습니다. 전체 원문·상태·사용량은 `market_agent/.cache/`에 분리하며 두 경로 모두 Git에서 제외됩니다. 통합 에이전트에는 출력 MD만 전달합니다.

## 팀 통합

- 외부 계약: 기술 조사 **JSON 입력 → 시장성 평가 MD 출력**.
- 출력 범위: 입력된 기술마다 시장 규모·성장, 제품화, 실제 채택, 생태계 지원, 표준화, 비용·고객 가치·사업화 조건의 6개 항목과 실제 인용 근거.
- Python에서 연결할 때: `market_agent.node.run_market`과 `parent_update`. 다른 역할의 State를 덮어쓰지 않도록 역할별 변경분을 병합합니다.
- 부모 Graph가 보완을 관리하면 `auto_repair=False`로 실행하고 회차 간 같은 시장 예산 객체를 유지합니다. 팀 부모 Graph 연결은 아직 별도 작업입니다.

상세 계약과 예제는 [상세 사용 안내](market_agent/README.md#6-부모-graph에-연결)와 [설계 문서](docs/MARKET_AGENT_DESIGN.md)를 참고합니다.

## 최종 전달본의 의미

최신 검토본은 기준일 **2026-09-21**, 검토일 **2026-09-22**의 결과입니다. 선정 기술 평가는 **조건부 1개·미확인 11개**, HW 관련 제품 정보 **1건**입니다. 조건부 항목은 RDKV의 기술 효과를 전제로 한 고객 가치 추론이며 실제 고객 비용 절감의 확정이 아닙니다. 관련 제품의 발표도 선정 Photonic-CXL 논문의 상용화를 입증하지 않습니다.

이 파일은 자동 실행 후 원문과 대조하여 SW의 환경 효과 전망과 HW의 컴퓨트 확장 조건을 교정한 **검토본**입니다. 자동 출력은 별도 outputs 경로에 보존했습니다. 모델의 의미 검토도 오류가 있을 수 있어 보고서에 쓰기 전 주요 주장을 원문과 대조해야 합니다. 미확인은 시장이 없다는 뜻이 아니며, 남은 원문 접근 실패와 제외된 잘못된 연결은 검증 기록에서 확인합니다.

`fixture` 모드는 실제 시장 조사가 아닙니다. 최신 조사에는 기준일·예산을 검토한 새 입력과 새 출력 폴더를 사용해야 합니다. 포함된 최종 MD는 내부 캐시가 없는 전달용 파일이므로 `--reuse` 대상이 아닙니다.

## 검증

```bash
python -m unittest discover -s market_agent/tests -v
python -m compileall -q market_agent
```

현재 근거 분리 구현은 92개 테스트와 compileall을 통과했습니다. 라이브 결과의 내용 검토는 아래 검증 기록에서 별도로 확인합니다. 이관 검증과 원본 추적 정보는 [이관 기록](MIGRATION.md), 실제 조사 한계는 [라이브 검증 기록](market_agent/LIVE_VALIDATION.md)에 있습니다.
