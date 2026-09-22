# PDF·자연어 요청 → RAG → 평가·종합 → 보고서

기본 실행은 Research를 다시 실행하지 않고 research 브랜치 `3c19ec6`의 저장 결과
`rag/examples/results/technical-bge-e2e-two-papers`를 사용합니다. 기존 코드와 결과는 `rag/`에 있습니다.

입력은 [config/pipeline.json](../config/pipeline.json)에서 관리합니다.

| 항목 | 내용 |
| --- | --- |
| `pdfs` | `rag/papers/2605.08317.pdf`, `rag/papers/2607.27187.pdf` 등 논문 경로 |
| `instruction` | 사용자가 요청한 자연어 문장 |
| `request` | 평가 목적·도메인·요구조건·추가 맥락 |
| `rag.mode` | 기본값 `saved`; 명시적으로 다시 조사할 때 `live` |
| `rag.saved_output` | 기존 RAG 결과 폴더 |

기본 요청은 “장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해.”입니다.
**새 요청은 후속 평가·종합·보고서의 맥락에 적용됩니다. 과거 RAG 결과가 새 요청으로 재생성된 것은 아닙니다.**

## 실행

저장소 루트에서 실행합니다. 통합 환경은 Python 3.12이며 Research용 임베딩·GPU 패키지는 설치하지 않습니다.
무거운 논문 처리 의존성과 가상환경은 `rag/`에 분리되어 있습니다.

```bash
uv sync --frozen
uv run --frozen python -m pipeline --output outputs/my-report
```

`OPENAI_API_KEY`, `TAVILY_API_KEY`를 환경변수로 제공하거나 기존
루트 `.env`에 설정합니다. 루트 파일이 없을 때는 기존 `agent/stakeholder/.env`를 사용합니다.
지정된 환경 파일이 기존 환경변수보다 우선합니다.
다른 파일은 `--env-file`로 지정할 수 있습니다.
기본 모델은 `gpt-4.1-mini`이며 `--model`로 선택합니다.
실제 외부 API를 호출합니다. `.env`나 인증 정보는 결과에 저장하지 않습니다.

```bash
# 입력, 모델, 조사 기준일이 같은 실행을 이어서 진행
uv run --frozen python -m pipeline --output outputs/my-report --resume

# 특정 단계만 다시 실행 (그 출력이 바뀌면 이후 결과도 다시 생성)
uv run --frozen python -m pipeline --output outputs/my-report --resume --rerun review

# 저장 결과 입력 변환까지만 수행 (외부 API 호출 없음)
uv run --frozen python -m pipeline --output outputs/prepare-only --stop-after prepare

# 기본 설정 파일 또는 자연어 요청 변경
uv run --frozen python -m pipeline --input config/pipeline.json
uv run --frozen python -m pipeline --instruction "장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해."
```

실행일이 달라진 후 재개하려면 기존 `run.json`의 날짜를 `--as-of YYYY-MM-DD`로 전달합니다.
`--research`, `--request`로 다른 결과 폴더와 사용자 요청 JSON을 지정할 수 있습니다.
입력·모델이 바뀌면 새로운 출력 폴더를 사용합니다.

`--instruction`으로 자연어 요청을 덮어쓰고, `--pdf`를 반복하여 논문 경로를 지정할 수 있습니다.
PDF를 바꿔 새 논문을 분석하려면 그에 맞는 저장 결과를 지정하거나 RAG를 명시적으로 다시 실행해야 합니다.

```bash
# RAG까지 실제 실행하려는 경우에만 선택
uv run --frozen python -m pipeline --run-rag \
  --pdf rag/papers/2605.08317.pdf \
  --pdf rag/papers/2607.27187.pdf \
  --output outputs/fresh-research-report
```

`--run-rag` 또는 설정의 `rag.mode: live`는 실제 논문 처리·조사를 선택하는 옵션입니다.
기본 `saved` 모드에서는 RAG를 재실행하지 않습니다. RAG의 별도 의존성과 설정은
[RAG 안내](../rag/README.md)를 참고하세요. 저장 결과 기반 통합을 위해 RAG 처리 로직을 변경하지 않았습니다.

## 연결 구조

전체 시스템은 기술 조사, 시장 평가, 이해관계자 평가, 도메인 평가, 평가 종합, 보고서 생성의 **6개 에이전트**로 구성됩니다. 이 중 평가·종합 에이전트 4개는 `agent/`에, 기술 조사 에이전트는 `rag/`에, 보고서 생성 에이전트는 `report/`에 배치되어 있습니다.

| 에이전트 | 위치 | 역할 |
| --- | --- | --- |
| 기술 조사 | `rag/` | 논문 분석·실험 조건·원문 근거 또는 저장 결과 제공 |
| 시장 평가 | `agent/market/` | 시장·제품·생태계 |
| 이해관계자 평가 | `agent/stakeholder/` | 운영 조직의 이익·부담·도입 조건 |
| 도메인 평가 | `agent/domain/` | 데이터센터·클라우드 서빙 적용성 |
| 평가 종합 | `agent/review/` | 세 관점의 연결과 조건부 종합 |
| 보고서 생성 | `report/` | 보고서 작성·LaTeX·PDF 생성 |

1. `pipeline/research_input.py`: 원본 실행·논문 dossier·비교·근거 파일을 읽고 역할별 입력으로 변환합니다.
2. `pipeline/runtime.py`: Domain → Stakeholder → Market을 실제 호출합니다.
3. `pipeline/review_bridge.py`: 결과와 근거를 Review 입력으로 연결하고 종합을 실행합니다.
4. `pipeline/reporting.py`: 실제 종합 결과로 기존 ReportAgent를 호출해 LaTeX와 PDF를 생성합니다.

원본 자료는 `research.bundle.json`, 모델에 전달한 파생 입력은 `papers.compat.json`,
전달한 문맥과 원본 연결 기록은 `research.context_manifest.json`에 저장합니다.
각 단계 출력과 `run.json`은 중간 실패 후 재사용할 수 있습니다.

후속 평가에 전달하는 논문별 호환 입력은 36,000자, 도메인 평가 입력은 85,000자 이내로 구성합니다.
논문 분석은 기술 개요·적용 범위·한계를 번갈아 선택하고, 각 영역 안에서도 필드를 번갈아 선택합니다.
각 주장은 참조하는 근거 발췌 전체와 함께 포함하며, 한도 때문에 제외한 내용은 문맥 기록에 남깁니다.
전체 원본 분석과 근거는 `research.bundle.json`에 보존합니다.

최종 산출물은 `review.output.md`, `report.input.md`, `report.tex`, `report.pdf`입니다.
기본 실행은 출처를 명시하는 분석 초안(`annotated_draft`)입니다. 앞 단계에서 인용되지 않은
웹 출처도 제목·URL·발행 주체·날짜·활용 상태와 함께 종합 입력으로 전달합니다.
웹 본문은 상위 에이전트 결과 파일에 보존합니다. 종합에는 세 에이전트의 분석과 함께
실제 수집한 웹 발췌·출처 정보를 전달해, 앞 단계에서 인용하지 못한 유용한 자료도 분석에 활용합니다.
제목·URL만으로 내용을 추측하지 않으며, 탐색 메뉴만 수집된 페이지는 분석 근거로 사용하지 않습니다.
종합 의견은 `draft_opinions`, 개별 표현·근거 연결 및 검사 응답 문제는 `review_notes`에 보존합니다.
의미 검사 미통과 때문에 전체 의견을 삭제하지 않으며, 검사 통과로 표시하지도 않습니다.
PDF의 단일 `REFERENCE`에 논문과 웹 자료의 제목·URL·저자/기관을 함께 넣습니다.
동일 URL은 중복 제거하고, 실제 본문에서 활용하여 인용한 자료만 참고문헌에 넣습니다.
수집 목록 전체를 참고문헌으로 출력하거나 목표 개수를 맞추기 위한 인용을 만들지 않습니다.
검토에서 보류된 시장·이해관계자 분석은 `retained_draft_findings`로 보존해 종합에 전달하고,
종합 의견과 검토 사항을 함께 보고서에 포함합니다.
수집된 본문은 `stakeholders.output.json`, `market.output.json`에서 확인할 수 있습니다.
보고서 작성 전 수집 본문을 출처별로 읽어 구체적 관찰·인용 구절·운영/시장 해석을
`report.source-analysis.json`에 저장합니다. 앞 단계에서 미채택된 유용한 웹 내용도
본문에 반영하고, 메뉴만 수집된 자료 등은 생략 사유를 남깁니다. 같은 입력으로 재개하면 이 분석도 재사용합니다.
최종 본문은 보고서 에이전트가 평가 주제별 줄글로 작성하고, 근거를 사용한 문장에 인용을 붙입니다.
코드는 출처별 설명 문단이나 본문 인용을 추가하지 않습니다. 활용 가능한 웹 자료가 미인용이면
기존 초안과 누락 자료를 에이전트에 전달해 최대 한 번 보완하며, 남은 누락과 처리 결과는
`report.source-coverage.json`에 기록합니다. 보완 실패 시 기존 유효 초안을 보존합니다.

`--draft`는 추가 종합 생성·의미 검토 호출을 생략하고 관점별 결과와 수집 자료로 초안을 만듭니다.
세 관점 정보를 연결한 새 종합 의견이 필요하면 이 옵션을 생략합니다.
보고서에는 근거 부족, 판단 보류, 일부 역할 실패가 남을 수 있습니다.
PDF 생성은 전체 평가 정확도나 제출 품질 검증의 완료를 의미하지 않습니다.

## 원래 한도와 자료 보존

통합에서 줄였던 호출 한도를 제거하고 각 에이전트의 기본값을 사용합니다.
시장은 `feat/market-agent`의 `93281d1`을 통합했으며, 세 단계의 조사·종합을 위한
새 기본 한도를 `pipeline/runtime.py`에 명시했습니다.

| 에이전트 | 검색 | 본문 수집 | 모델 호출 |
| --- | ---: | ---: | ---: |
| 이해관계자 | 6 | 10 | 5 |
| 시장 | 18 | 24 | 10 |

새 시장 결과의 `observation`과 `supporting_materials`도 종합에 전달합니다.
검토에서 보류된 모델 의견은 출처와 검토 이유를 붙여 보존합니다. 자료가 부족할 때
시장 모듈이 채운 `deterministic_fallback` 문장은 모델의 결론으로 사용하지 않고
조사 상태로 구분합니다. 외부 전달용 `market_handoff.json`은 축약본이므로,
내부 파이프라인은 계속 전체 `evidence`를 포함한 `market.output.json`을 사용합니다.

수집 한도는 성공한 고유 출처 수를 보장하지 않습니다. 확보된 자료가 8개라면 8개 전체를,
그보다 많거나 적으면 실제 확보한 자료 전체를 전달하며 개수를 맞추기 위해 자료를 만들지 않습니다.
논문 분석 입력과 참고문헌 형식은 기존 방식을 유지합니다. 근거 조각 191개를 추가로 모두 투입하지 않습니다.
Research 결과의 authors가 비어 있으면 공식 arXiv에서 확인한 `pipeline/paper_authors.json`을 사용해
참고문헌의 저자만 보완합니다. Research 원본은 수정하거나 재실행하지 않습니다.
각 에이전트가 원래 사용하던 웹 페이지당 수집 길이와 내부 정책은 그대로 사용합니다.

## PDF 컴파일

XeLaTeX 또는 Tectonic을 사용합니다. PATH, 일반 설치 경로, Codex에 설치된 Tectonic을 자동 탐색합니다.
필요하면 `XELATEX_BIN` 또는 `TECTONIC_BIN`에 실행 파일 절대 경로를 지정합니다.
생성 응답과 컴파일 오류는 실행 폴더에 남기며, 컴파일 오류는 제한된 횟수로 보고서 에이전트에 돌려보냅니다.

전체 글꼴은 **나눔명조**이며 NanumMyeongjo Regular/Bold 설치가 필요합니다.
[Google Fonts 배포본](https://github.com/google/fonts/tree/main/ofl/nanummyeongjo)을 사용할 수 있습니다.
첫 문단도 1em 들여쓰기하고, SUMMARY의 보고서 소개 문단을 생략합니다.
본문은 출처마다 문단을 나누지 않고 같은 평가 주제의 관찰·해석·조건을 연결합니다.
참고문헌은 자료 유형에 맞는 저자·날짜·전체 제목·발행처·식별자 형식으로 출력하고 열람일과 유형명은 표시하지 않습니다.
발행일을 확인할 수 없으면 시카고의 날짜 미상 표기인 `n.d.`를 사용합니다. 날짜 없는 웹 자료에 열람일을 병기하는 공식 시카고 규칙과 달리, 이 보고서는 사용자의 열람일 제외 요청을 유지합니다.
최종 문서 상단의 초안·자동 검사 상태 안내문은 출력하지 않고, 검토 절 제목은 **종합 검토 사항**으로 표시합니다.
종합 검토 사항의 문서·근거 ID는 식별되는 참고문헌의 인용 번호로 표시합니다. 이는 검사 기록에 등장한 **검토 대상 자료**의 연결이며, 미확인된 검토 의견을 검증 통과로 바꾸지는 않습니다. 원본 ID와 검토 상태는 입력 자료에 보존합니다.
확인한 전체 서지 정보는 `pipeline/reference_metadata.json`에 URL별로 보존합니다.
본문 내용과 문단 재구성은 보고서 에이전트가 수행하며, 코드 후처리는 글꼴·들여쓰기·서지 형식에 한정합니다.

이번 통합의 우선 목표는 실제 저장 결과로 보고서를 생성하는 것입니다.
전체 테스트, 원본 논문 재검증, 상세 품질 평가는 별도로 수행합니다.
