# KV-Cache Technical Research Agent

다중 논문에서 기술 개요·적용 범위·한계·실험 조건을 추출하고, 모든 결과를 원문
페이지·문장·표 셀로 역추적하는 LangGraph 기반 RAG Agent다.

이 폴더에는 기존 기술조사 Agent를 유지한다. 상위 프로젝트의 `agent/`와 `report/`는
`TechnicalResearchEnvelope` JSON 결과를 받아 평가·종합·보고서를 생성한다.
전체 흐름은 [루트 안내](../README.md)를 따른다. 기본 통합 실행은 RAG 재실행 없이 저장 결과를 사용한다.

기술조사 코드·테스트·의존성·예제 결과는 `feat/research-agent`의
`9e427c50961ab5541c603a410ea116d0a41a5c72`에 동기화되어 있다.
`runner.py`, `papers/`와 이 안내 문서는 통합 프로젝트의 실행 구조를 유지한다.

## 주요 구성

- PyMuPDF 페이지·블록·caption 추출과 pdfplumber native table 복원
- 로컬 BGE-M3 dense + learned sparse + ColBERT 검색
- OpenAI structured output 기반 개요·범위·한계 병렬 추출 및 근거 감사
- 수치·표·그림 locator와 `UnverifiedItem`
- 논문 간 관계·비교 가능성·결합 가설을 담는 `TechnicalComparison`
- SQLite LangGraph checkpoint와 원자적 결과 게시

상세 RAG 구현과 다른 팀 Agent의 JSON 소비 방법은
[기술조사 Agent RAG 설계 및 외부 평가 Agent 연계 명세](docs/technical-research-rag-integration.md)를 참고한다.

## 설치 및 실행

아래 명령은 RAG를 새로 실행할 때만 `rag/` 폴더에서 사용한다.

```bash
uv sync --extra dev
cp .env.example .env
uv run paper-review models pull bge-m3

uv run paper-review research \
  --source paper-a.pdf \
  --source paper-b.pdf \
  --instruction '클라우드 서버 구축 관점에서 기술적으로 비교해줘'
```

성공 출력:

```text
outputs/<job-id>/technical/
├── run.json
├── dossiers/<paper-id>.json
├── comparison.json
├── evidence_registry.json
└── retrieval_traces.jsonl
```

검증:

```bash
uv run paper-review validate-technical outputs/<job-id>/technical/run.json
uv run paper-review export-technical-md outputs/<job-id>/technical/run.json
uv run pytest
```

두 논문 실제 성공 결과는
[`examples/results/technical-bge-e2e-two-papers`](examples/results/technical-bge-e2e-two-papers)에
포함되어 있다. PDF 원본과 비밀 정보는 포함하지 않았고 공개 저장소용 상대경로와 해시를
사용한다.

동일한 장문맥 문서 QA 요청의 성공 결과는
[`examples/results/technical-long-context-qa-datacenter`](examples/results/technical-long-context-qa-datacenter)에
포함되어 있다. 두 예제의 `markdown/README.md`에서 사람이 읽기 쉬운 분석을 확인할 수 있다.

## 보안·운영 원칙

- `.env`, API key, PDF, 출력 결과와 모델 weight는 Git에 포함하지 않는다.
- OpenAI embedding은 사용하지 않는다. 임베딩은 고정 revision의 로컬 BGE-M3만 허용한다.
- 기술조사 Agent는 웹 검색을 하지 않는다. arXiv ID를 입력한 경우 해당 PDF만 내려받는다.
- 승인된 공통 코퍼스는 배경 문맥으로만 사용하고 논문 주장은 해당 논문의 근거로 지지한다.
