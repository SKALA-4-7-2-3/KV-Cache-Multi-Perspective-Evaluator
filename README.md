# KV Cache Multi-Perspective Evaluator

논문 PDF 2개와 자연어 요청을 받아 시장성·이해관계자·도메인 적합성을 분석하고, 종합 보고서 PDF를 만드는 프로젝트입니다. 현재 평가 대상은 **RDKV**와 **Photonic-CXL**입니다.

기본 요청:

> 장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해.

## 처리 흐름

```text
논문 PDF 2개 + 자연어 요청
             ↓
RAG: 논문 분석·실험 조건·원문 근거
     기본값은 기존 저장 결과 불러오기
             ↓
domain · market · stakeholder
적용성    시장성    운영 조직의 이익·부담
             ↓
review: 세 관점 연결·조건부 종합·검토 사항
             ↓
report: 보고서 작성 → LaTeX → PDF
```

`agent/`에는 **domain, market, stakeholder, review의 4개 에이전트**가 있습니다. 논문을 조사하는 `rag/`와 최종 문서를 만드는 `report/`는 별도 모듈입니다. 세 관점은 같은 논문 자료와 사용자 요청을 받으며, 현재 실행기는 domain → stakeholder → market 순서로 호출합니다.

## 폴더 구조

```text
config/pipeline.json   PDF 경로·요청·평가 맥락·RAG 모드
pipeline/              전체 흐름과 단계 간 입력 변환
rag/                   기존 Research 코드·의존성·저장 결과
  papers/              평가 대상 PDF
  examples/results/    기존 논문 분석 결과
agent/
  domain/              도메인 적합성
  market/              시장성
  stakeholder/         이해관계자
  review/              종합
report/                보고서 작성·PDF 변환
docs/pipeline.md       상세 실행 안내
outputs/               실행별 중간 결과와 최종 보고서
pyproject.toml         Python 3.12 통합 실행 환경
```

## 실행

저장소 루트의 `.env` 또는 환경변수에 `OPENAI_API_KEY`, `TAVILY_API_KEY`를 설정합니다. 저장된 RAG 결과를 쓰는 기본 실행에도 후속 분석·웹 검색·보고서 작성 API 호출이 있습니다.

```bash
uv sync --frozen
uv run --frozen python -m pipeline
```

기본 입력은 [config/pipeline.json](config/pipeline.json)입니다. PDF 경로와 자연어 요청을 이 파일에서 함께 관리합니다.

```bash
# 외부 API 호출 없이 입력 준비까지만 수행
uv run --frozen python -m pipeline --stop-after prepare

# 설정 파일과 출력 폴더 지정
uv run --frozen python -m pipeline --input config/pipeline.json --output outputs/my-report

# 자연어 요청 변경
uv run --frozen python -m pipeline --instruction "장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해."
```

기본 RAG 입력은 `rag/examples/results/technical-bge-e2e-two-papers`의 과거 실행 결과입니다. **새 자연어 요청은 후속 에이전트의 평가 맥락에 적용됩니다. 기존 논문 분석이 이 새 요청으로 재생성된 것은 아닙니다.** RAG를 실제로 다시 실행하려면 `--run-rag`를 명시하거나 설정에서 `rag.mode`를 `live`로 선택합니다. RAG 의존성과 환경은 루트 환경과 분리되어 있습니다.

## 결과

실행 폴더의 `report.pdf`가 최종 산출물입니다. 단계별 JSON과 `run.json`에 입력·출처·처리 상태가 남습니다. 출처가 보고한 내용과 에이전트의 해석을 구분하고, 개별 검토 문제는 한계와 검토 사항으로 보존합니다. 본문에서 실제 인용한 자료만 `REFERENCE`에 포함합니다.

기본 출력은 출처 기반 분석 초안입니다. PDF 생성이 내용의 정확성 검증이나 최종 제출 검토의 완료를 뜻하지는 않습니다.

재개·단계별 실행은 [파이프라인 안내](docs/pipeline.md), 에이전트별 역할은 [agent 안내](agent/README.md)를 참고하세요.
