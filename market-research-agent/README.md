# 시장조사 에이전트

기술 조사 결과 JSON을 받아 RDKV와 Photonic-CXL의 시장성을 조사하고, 통합 에이전트에 전달할 **`market_handoff.md` 한 개**를 생성합니다. LangGraph로 검색·본문 검사·근거 추출·평가 작성·단계별 최대 1회 보완을 제어합니다.

## 폴더 구성

| 위치 | 내용 |
| --- | --- |
| `market_agent/` | Python 코드, 입력 샘플, 회귀 테스트, 상세 사용 안내 |
| `docs/` | 설계, 시장성 출력 양식, 이전 실습 가이드 검토 기록 |
| `tasks/` | 구현·수정 계획과 완료 기록 |
| [`deliverables/market_handoff_20260922_v11_reviewed.md`](deliverables/market_handoff_20260922_v11_reviewed.md) | v1.1 실행 후 원문과 대조하여 표현을 교정한 공유용 검토본 |
| `deliverables/market_handoff.md` | 최신 자동 생성 통합 전달본 |
| `requirements.txt`, `requirements.lock.txt`, `.env.example` | 직접·간접 의존성 고정 버전과 빈 API 키 양식 |

## 설치와 실행

VS Code에서 이 `market-research-agent` 폴더를 열거나, 저장소 루트에서 `cd market-research-agent`로 이동합니다. **Python 3.11**을 사용합니다. `requirements.txt`는 함께 있는 `requirements.lock.txt`의 하위 의존성 버전도 적용합니다. 두 파일을 함께 보관하세요.

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

`live` 실행은 Tavily와 OpenAI API를 호출하며 계정 사용량이 발생합니다. 기본 모델은 `gpt-4.1-mini`입니다. 현재 팀 입력은 dossier 1.0.0 두 개 + evidence_registry.json + comparison 1.0.0의 **JSON 네 개**입니다. 기존 paper_analysis 1.1.0 한 개 또는 두 개도 지원합니다. 기본 조사 기준일은 실행일이며 `--as-of YYYY-MM-DD`로 고정할 수 있습니다. [JSON 입력 안내](docs/JSON_INPUT.md)에 필드 연결·옵션·실제 첨부 검증 결과가 있습니다. 기존 MD v0.1 입력도 지원합니다. 프로세스 환경변수가 `.env`보다 우선하며, `--env-file`로 별도 설정 파일을 지정할 수 있습니다.

기본 출력은 `market_agent/outputs/<실행시각>/market_handoff.md`입니다. `--output <새 폴더>`로 바꿀 수 있습니다. 전체 원문·상태·사용량은 `market_agent/.cache/`에 분리하며 두 경로 모두 Git에서 제외됩니다. 통합 에이전트에는 출력 MD만 전달합니다.

### 팀의 JSON 4개 입력

```bash
python -m market_agent.cli --input \
  /path/to/evidence_registry.json /path/to/comparison.json \
  /path/to/dossiers/2605.08317-25836a41.json \
  /path/to/dossiers/2607.27187-d6a67efd.json \
  --as-of 2026-09-22 --mode live
```

파일 순서는 자유이며 파일명보다 내용 구조로 구분합니다. 누락·중복 근거, 논문 소유 관계, snippet SHA-256, 문서 SHA-256, 비교 대상 observation 참조를 API 호출 전에 검사합니다. 원본 PDF 경로는 열지 않습니다. 비교 불가능한 성능 수치와 공동 실험이 없는 결합 가설을 모델의 배경 제한사항으로 전달합니다.

## 팀 통합

- 외부 계약: 기술 조사 **JSON 입력 → 시장성 평가 MD 출력**.
- 출력 범위: 입력된 기술마다 시장 규모·성장, 제품화, 실제 채택, 생태계 지원, 표준화, 비용·고객 가치·사업화 조건의 6개 항목과 실제 인용 근거.
- Python에서 연결할 때: `market_agent.node.run_market`과 `parent_update`. 다른 역할의 State를 덮어쓰지 않도록 역할별 변경분을 병합합니다.
- 부모 Graph가 보완을 관리하면 `auto_repair=False`로 실행하고 회차 간 같은 시장 예산 객체를 유지합니다. 팀 부모 Graph 연결은 아직 별도 작업입니다.

상세 계약과 예제는 [상세 사용 안내](market_agent/README.md#6-부모-graph에-연결)와 [설계 문서](docs/MARKET_AGENT_DESIGN.md)를 참고합니다.

## 최종 전달본과 실행 상태

통합 에이전트에는 `deliverables/market_handoff.md` 한 개를 전달합니다. 선정 기술의 판정과 관련 제품·기술군 정보를 구분하고 각 주장에 인용·조건을 연결합니다. 실행별 자동 결과와 원문은 outputs/ 및 .cache/에 별도로 보존합니다.

**최신 4파일 검증 결과:** 12개 직접 판정은 미확인, 관련 정보 5개·출처 4개입니다. 원문 조회 실패 및 수치 후보 제외가 남아 실행 상태는 partial입니다. 자세한 내용은 검증 기록에 있습니다.

내부 계약은 **0.4**입니다. `execution_status=completed/partial/failed`는 처리 완료 여부이며, 기존 `status=completed/unknown/failed`와 각 항목의 verdict는 시장 평가 결과입니다. 정상 조사 후에도 직접 근거가 없으면 unknown일 수 있습니다. 부분 처리 결과는 유효 항목을 보존하지만 자동으로 완료 결과로 취급하지 않습니다. CLI 종료 코드는 완료 0 / 부분 처리 3 / 치명적 실패 2입니다.

`fixture`는 실제 시장 조사가 아닙니다. 라이브 검증 결과·남은 한계는 [검증 기록](market_agent/LIVE_VALIDATION.md)에 기록합니다. 논문의 메모리·속도 효과는 실제 고객의 비용 절감이나 도입 실적을 자동으로 입증하지 않습니다.

## 검증

```bash
python -m unittest discover -s market_agent/tests -v
python -m compileall -q market_agent
```

현재 **130개 회귀 테스트와 compileall**을 통과했습니다. JSON 인용 경계·조사 분기·주장 의미·부분 상태의 회귀 검사와 compileall로 검증합니다. 라이브 결과의 내용 검토는 아래 검증 기록에서 별도로 확인합니다. 이관 검증과 원본 추적 정보는 [이관 기록](MIGRATION.md), 실제 조사 한계는 [라이브 검증 기록](market_agent/LIVE_VALIDATION.md)에 있습니다.
