# 시장조사 에이전트

기술 조사 결과를 Markdown으로 받아 RDKV와 Photonic-CXL의 시장성을 조사하고, 통합 에이전트에 전달할 **`market_handoff.md` 한 개**를 생성합니다. LangGraph로 검색·평가·검증·최대 1회 보완을 제어합니다.

## 폴더 구성

| 위치 | 내용 |
| --- | --- |
| `market_agent/` | Python 코드, 입력 샘플, 회귀 테스트, 상세 사용 안내 |
| `docs/` | 설계, 시장성 출력 양식, 이전 실습 가이드 검토 기록 |
| `tasks/` | 구현·수정 계획과 완료 기록 |
| [`deliverables/market_handoff.md`](deliverables/market_handoff.md) | 실제 조사 후 출처 대조·재검증한 최종 전달본 |
| `requirements.txt`, `requirements.lock.txt`, `.env.example` | 직접·간접 의존성 고정 버전과 빈 API 키 양식 |

## 설치와 실행

VS Code에서 이 `market-research-agent` 폴더를 열거나, 저장소 루트에서 `cd market-research-agent`로 이동합니다. **Python 3.11**을 사용합니다. `requirements.txt`는 함께 있는 `requirements.lock.txt`의 하위 의존성 버전도 적용합니다. 두 파일을 함께 보관하세요.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 입력 구조 확인: API 호출 없음
python -m market_agent.cli --input market_agent/fixtures/input.md --mode parse

# 고정 응답으로 전체 흐름 확인: API 호출 없음
python -m market_agent.cli --input market_agent/fixtures/input.md --mode fixture
```

Windows에서는 가상환경 생성에 `py -3.11 -m venv .venv`, PowerShell 활성화에 `.venv\Scripts\Activate.ps1`을 사용합니다. Windows 실행은 별도로 검증하지 않았습니다.

실제 조사에는 이 폴더의 `.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`, `TAVILY_API_KEY`를 입력합니다. `.env`가 이미 있다면 새 파일로 덮어쓰지 않습니다. 실제 키는 저장소에 포함하지 않았습니다.

```bash
python -m market_agent.cli --input market_agent/fixtures/input.md --mode live
```

`live` 실행은 Tavily와 OpenAI API를 호출하며 계정 사용량이 발생합니다. 기본 모델은 `gpt-4.1-mini`입니다. 다른 입력도 샘플의 5개 필수 구역 형식을 따라야 합니다. 팀 기술 조사 결과 파일로 `--input` 경로를 바꾸면 됩니다. 프로세스 환경변수가 `.env`보다 우선하며, `--env-file`로 별도 설정 파일을 지정할 수 있습니다.

기본 출력은 `market_agent/outputs/<실행시각>/market_handoff.md`입니다. `--output <새 폴더>`로 바꿀 수 있습니다. 전체 원문·상태·사용량은 `market_agent/.cache/`에 분리하며 두 경로 모두 Git에서 제외됩니다. 통합 에이전트에는 출력 MD만 전달합니다.

## 팀 통합

- 외부 계약: 기술 조사 **MD 입력 → 시장성 평가 MD 출력**.
- 출력 범위: SW/HW 각각 시장 규모·성장, 제품화, 실제 채택, 생태계 지원, 표준화, 비용·고객 가치·사업화 조건의 6개 항목과 실제 인용 근거.
- Python에서 연결할 때: `market_agent.node.run_market`과 `parent_update`. 다른 역할의 State를 덮어쓰지 않도록 역할별 변경분을 병합합니다.
- 부모 Graph가 보완을 관리하면 `auto_repair=False`로 실행하고 회차 간 같은 시장 예산 객체를 유지합니다. 팀 부모 Graph 연결은 아직 별도 작업입니다.

상세 계약과 예제는 [상세 사용 안내](market_agent/README.md#6-팀의-상위-graph에-연결하기)와 [설계 문서](docs/MARKET_AGENT_DESIGN.md)를 참고합니다.

## 최종 전달본의 의미

포함된 전달본은 기준일 **2026-09-21**, 검토일 **2026-09-22**의 결과입니다. 선정 기술에 대한 판정 12개는 모두 `unknown`이며, HW 관련 제품군 정보 1건을 별도 조건과 출처로 보존했습니다. `unknown`은 이번 조사에서 직접 판단할 근거가 부족하다는 뜻입니다. 초기 모델 결과를 확정된 시장 사실로 사용하지 않습니다.

`fixture` 모드는 실제 시장 조사가 아닙니다. 최신 조사에는 기준일·예산을 검토한 새 입력과 새 출력 폴더를 사용해야 합니다. 포함된 최종 MD는 내부 캐시가 없는 전달용 파일이므로 `--reuse` 대상이 아닙니다.

## 검증

```bash
python -m unittest discover -s market_agent/tests -v
python -m compileall -q market_agent
```

기존 구현은 58개 테스트와 실제 API 연결·출처 검토를 완료했습니다. 이관 검증과 원본 추적 정보는 [이관 기록](MIGRATION.md), 실제 조사 한계는 [라이브 검증 기록](market_agent/LIVE_VALIDATION.md)에 있습니다.
