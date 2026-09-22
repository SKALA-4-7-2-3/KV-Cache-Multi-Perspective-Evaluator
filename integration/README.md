# Saved Research → Agent Pipeline → PDF

Research는 다시 실행하지 않습니다. 기본 입력은 research 브랜치 `3c19ec6`의
`examples/results/technical-bge-e2e-two-papers`이며, 원본 코드와 저장 결과를 유지합니다.
기본 요청은 `stakeholder-agent/examples/request.json`의 클라우드 데이터센터 LLM 운영 상황입니다.

## 실행

저장소 루트에서 실행합니다. 통합 환경은 Python 3.12이며 Research용 임베딩·GPU 패키지는 설치하지 않습니다.

```bash
uv sync --project integration
integration/.venv/bin/python -m pipeline --output outputs/integration/first-report --draft
```

`OPENAI_API_KEY`, `TAVILY_API_KEY`를 환경변수로 제공하거나 기존
`stakeholder-agent/.env`에 설정합니다. 명시적인 프로젝트 파일이 기존 환경변수보다 우선합니다.
다른 파일은 `--env-file`로 지정할 수 있습니다.
기본 모델은 `gpt-4.1-mini`이며 `--model`로 선택합니다.
실제 외부 API를 호출합니다. `.env`나 인증 정보는 결과에 저장하지 않습니다.

```bash
# 입력, 모델, 조사 기준일이 같은 실행을 이어서 진행
integration/.venv/bin/python -m pipeline --output outputs/integration/first-report --resume --draft

# 특정 단계만 다시 실행 (그 출력이 바뀌면 이후 결과도 다시 생성)
integration/.venv/bin/python -m pipeline --output outputs/integration/first-report --resume --rerun review --draft

# 저장 결과 입력 변환까지만 수행 (외부 API 호출 없음)
integration/.venv/bin/python -m pipeline --output outputs/integration/prepare-only --stop-after prepare
```

실행일이 달라진 후 재개하려면 기존 `run.json`의 날짜를 `--as-of YYYY-MM-DD`로 전달합니다.
`--research`, `--request`로 다른 결과 폴더와 사용자 요청 JSON을 지정할 수 있습니다.
입력·모델이 바뀌면 새로운 출력 폴더를 사용합니다.

## 연결 구조

1. `pipeline/research_input.py`: 원본 실행·논문 dossier·비교·근거 파일을 읽고 역할별 입력으로 변환합니다.
2. `pipeline/runtime.py`: Domain → Stakeholder → Market을 실제 호출합니다.
3. `pipeline/review_bridge.py`: 결과와 근거를 Review 입력으로 연결하고 종합을 실행합니다.
4. `pipeline/reporting.py`: 실제 종합 결과로 기존 ReportAgent를 호출해 LaTeX와 PDF를 생성합니다.

원본 자료는 `research.bundle.json`, 모델에 전달한 파생 입력은 `papers.compat.json`,
선택된 문맥과 원본 연결 기록은 `research.context_manifest.json`에 저장합니다.
각 단계 출력과 `run.json`은 중간 실패 후 재사용할 수 있습니다.

최종 산출물은 `review.output.md`, `report.tex`, `report.pdf`입니다.
`--draft`는 실제 8개 관점 결과가 있고 역할 실패가 없을 때, Review의 형식 정리만 수행하고
추가 종합 생성·의미 검토 호출을 생략하여 검증 전 초안을 생성합니다. 검토 미실시/미통과를
그대로 표시하며, 반려된 종합 의견은 포함하지 않습니다.
이 옵션을 생략하면 기존의 종합 검토 통과 요건을 유지합니다.
보고서에는 근거 부족, 판단 보류, 일부 역할 실패가 남을 수 있습니다.
PDF 생성은 전체 평가 정확도나 제출 품질 검증의 완료를 의미하지 않습니다.

## PDF 컴파일

XeLaTeX 또는 Tectonic을 사용합니다. PATH, 일반 설치 경로, Codex에 설치된 Tectonic을 자동 탐색합니다.
필요하면 `XELATEX_BIN` 또는 `TECTONIC_BIN`에 실행 파일 절대 경로를 지정합니다.
생성 응답과 컴파일 오류는 실행 폴더에 남기며, 컴파일 오류는 제한된 횟수로 보고서 에이전트에 돌려보냅니다.

이번 통합의 우선 목표는 실제 저장 결과로 보고서를 생성하는 것입니다.
전체 테스트, 원본 논문 재검증, 상세 품질 평가는 별도로 수행합니다.
