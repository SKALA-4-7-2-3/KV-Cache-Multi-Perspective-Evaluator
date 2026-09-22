# KV Cache Multi-Perspective Evaluator

RDKV(SW 압축)와 Photonic-CXL(HW 메모리 확장)을 여러 관점에서 평가하는 팀 프로젝트입니다.
이 브랜치에는 백순철 담당 **검증·종합 Agent**만 포함합니다. 상위 조사 Agent와 최종 보고서 생성기는 팀 통합 대상이며 여기서 구현 완료한 것으로 표시하지 않습니다.

## 담당 범위

- technical이 전달한 단계별 근거로 최종 팀 추정 TRL 판정
- 시장·이해관계자·도메인 평가와 출처를 받아 조건부 종합 의견 생성
- 생성문을 입력·근거와 자동 대조하고, 오류 시 한 번 수정 후 재검사
- 미통과·검사 실패는 보고서 전달 차단, 자료 공백은 미확인으로 보존
- 다음 Agent에 `report-input-v1` Markdown 전달

실행 중 사람 승인 단계는 없습니다. 자동 검사가 외부 사실의 진실성이나 모델의 무오류를 보증하지는 않습니다.

## 빠른 시작

Python 3.12 또는 3.13에서 `agent/review` 폴더를 기준으로 실행합니다.

```bash
cd agent/review
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install ".[review-graph,review-llm]"
python -m unittest discover -s team_review/tests -v
```

테스트는 API 키 없이 실행합니다. 생성기·검사기 스텁으로 제어 흐름을 검사하며 모델 정확도 측정은 아닙니다.

### API 없이 입력·출력 확인

```bash
python -m team_review --demo all --output-dir outputs/demo
python -m team_review.check_report_input outputs/review.output.md
```

`--demo all`은 형식·TRL 규칙만 검사합니다. 새 종합/의미 검사가 미실행이므로 생성된 진단 MD는 `blocked`입니다.
저장소의 [출력 샘플](outputs/review.output.md)은 실제 종합·검사 API를 거친 별도 결과입니다.
이 샘플도 상위 평가가 모의 입력(`demo: true`)이고 시장·도입 근거가 부족하므로 초안·연결 테스트용입니다.

### 실제 종합 실행

`.env.example`을 참고해 로컬 `.env`에 `OPENAI_API_KEY`를 설정한 뒤 실행합니다. 키를 공유하거나 커밋하지 마세요.

```bash
python -m team_review --input team_review/examples/paper.input.md --synthesize --env-file .env --output-dir outputs
python -m team_review.handoff --input outputs/review.output.md --output-dir outputs/report_handoff
```

기본 모델은 `gpt-4.1-mini`입니다. 정상 생성·검사 2회, 수정 포함 최대 4회 호출하며 비용이 발생할 수 있습니다.
실패하면 `blocked`로 종료합니다. API 접근·요금 설정은 사용자 환경에 따라 다릅니다.
모의 입력의 출처·라이선스는 [PAPER-CASE.md](team_review/PAPER-CASE.md)에 있습니다. 논문 PDF 자체는 포함하지 않습니다.

## 팀 연결

| 담당 | 연결 파일·함수 |
|---|---|
| 상위 Agent | [입력 예시](team_review/examples/paper.input.md), `RoleResult`, `Evidence` |
| LangGraph 통합 | `review_agent_node`, `route_to_report`, `ReviewState` |
| 보고서 Agent | [출력 샘플](outputs/review.output.md), [출력 계약](team_review/OUTPUT-CONTRACT.md), [연결 안내](team_review/REPORT-HANDOFF.md) |

Graph의 세 분석 분기를 합류시킨 뒤 `review_agent_node`를 연결합니다. 팀의 checkpointer를 재사용합니다.
후단은 `read_report_input(md)`가 통과한 입력만 사용해야 합니다. `.env`·캐시·원문 PDF·대형 출력은 업로드하지 않습니다.
전체 연결 예시와 실행 한도는 [모듈 README](team_review/README.md)를 참고하세요.

## 구성

```text
team_review/          # 검증·종합, 프롬프트, 계약, 테스트
  examples/           # 논문 근거 + 모의 상위 평가 입력
  tests/              # API 없는 회귀·LangGraph·전달 파일 테스트
outputs/review.output.md  # 모의 입력 기반 API 실행 샘플
pyproject.toml        # 이 모듈만 독립 설치
```

## Contributors

- 백순철: 평가 기준·TRL 판정, 검증·종합 Agent, 자동 의미 검사, 보고서 입력 계약 및 테스트
