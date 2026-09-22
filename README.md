# KV-Cache Technical Research Agent

다중 논문에서 기술 개요·적용 범위·한계·실험 조건을 추출하고, 모든 결과를 원문
페이지·문장·표 셀로 역추적하는 LangGraph 기반 RAG Agent다.

이 브랜치는 기술조사 Agent만 포함한다. 시장·이해관계자·종합 평가 및 보고서 생성 Agent는
각 팀의 구현을 사용하며, `TechnicalResearchEnvelope` JSON 계약으로 연결한다.

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
uv run pytest
```

## 보안·운영 원칙

- `.env`, API key, PDF, 출력 결과와 모델 weight는 Git에 포함하지 않는다.
- OpenAI embedding은 사용하지 않는다. 임베딩은 고정 revision의 로컬 BGE-M3만 허용한다.
- 기술조사 Agent는 웹 검색을 하지 않는다. arXiv ID를 입력한 경우 해당 PDF만 내려받는다.
- 승인된 공통 코퍼스는 배경 문맥으로만 사용하고 논문 주장은 해당 논문의 근거로 지지한다.
