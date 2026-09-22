# KV-Cache Technical Research Agent

여러 논문에서 기술 개요·적용 범위·한계·실험 조건을 추출하고, 결과의 주장과 수치를
원문 페이지·문장·표 셀까지 역추적할 수 있게 만드는 LangGraph 기반 기술조사 RAG
Agent다.

이 브랜치는 기술조사 Agent를 구현한다. 시장·이해관계자·종합 평가 및 보고서 생성은
다른 팀 Agent가 담당하며 `TechnicalResearchEnvelope` 버전형 JSON 계약으로 연결한다.

사람이 검토할 때는 Markdown 변환본을 사용할 수 있지만, Agent 간 전달·스키마 검증과
무결성 판단의 기준은 항상 원본 JSON이다.

## 1. 왜 이렇게 여러 단계를 거치는가

논문 전체를 LLM에 한 번 입력해 요약하면 읽기 쉬운 초안은 만들 수 있지만, 후속 평가
Agent가 사용할 기술 데이터베이스로는 충분하지 않다.

### 중요한 근거가 논문 여러 위치에 흩어져 있다

핵심 방법은 본문에, 실험 조건은 표나 각주에, 재현 조건은 부록에, 한계는 결론 뒤에 있을
수 있다. 전체 문서 요약은 대표 결론을 보여 주더라도 다음 정보를 빠뜨리기 쉽다.

- 어떤 model·hardware·context length에서 측정했는가
- measured, emulated, simulated 중 어떤 결과인가
- baseline, dataset, workload와 측정 방식은 무엇인가
- 저자가 직접 명시한 한계와 분석자가 추론한 한계는 어떻게 다른가

이 구현은 질문별 근거를 먼저 검색하고 검색된 근거 안에서만 구조화 추출한다.

### 숫자가 같아 보여도 직접 비교할 수 없는 경우가 많다

두 논문이 모두 latency 또는 memory saving을 보고해도 model, hardware, batch,
concurrency, context length와 workload가 다르면 직접 순위를 매길 수 없다. 수치를 단독
문자열로 저장하지 않고 `ExperimentObservation`에 metric, unit, baseline, model,
hardware, context, dataset, workload, evaluation mode를 함께 보존한다. 조건이 다르면
`TechnicalComparison.metric_comparisons`에서 `not_comparable`로 표시한다.

### 검색 결과가 곧 검증된 사실은 아니다

RAG가 관련 청크를 찾더라도 PDF parser가 표를 잘못 복원하거나 LLM이 근거를 과도하게
일반화할 수 있다. 따라서 검색 뒤에 구조화 추출, 결정론적 계약 검사, 독립 근거 감사와
보강 검색을 둔다. 끝까지 확인할 수 없는 내용은 일반 지식으로 채우지 않고
`UnverifiedItem`으로 남긴다.

### 여러 팀 Agent가 같은 기술 사실을 사용해야 한다

시장·도메인·이해관계자 Agent가 각각 PDF를 다시 읽으면 서로 다른 수치와 한계를 선택할
수 있다. 기술조사 Agent가 공통의 `claim_id`, `observation_id`, `evidence_id`를 먼저
발행하면 후속 Agent들은 같은 기술 사실을 참조하면서 각자의 평가만 독립적으로 수행할 수
있다.

### 실행 중단과 설정 변경에도 재현할 수 있어야 한다

원문과 artifact SHA-256, BGE-M3 고정 commit과 파일 fingerprint, schema·prompt·index
version, 검색 profile과 trace를 기록한다. SQLite checkpoint는 `thread_id=job_id`로
관리한다. 복잡성의 목적은 Agent 수를 늘리는 것이 아니라 **근거 추적성, 수치 안전성,
재현성, 실패 복구와 팀 간 계약 안정성**을 확보하는 것이다.

## 2. 전체 구조

```text
자연어 지시 + PDF/TXT/Markdown/arXiv ID
                │
                ▼
       source 해석·SHA-256 중복 제거
                │
                ▼
┌──────────────────────────────────────────┐
│ 논문별 TechnicalResearch subgraph        │
│                                          │
│ parse → inventory seed → index           │
│   → query plan → hybrid retrieval        │
│   → 선택적 Vision → facet 병렬 추출      │
│   → 계약 검사·근거 감사                  │
│            │                             │
│ 실패 facet만 보강 검색·재추출, 최대 2회  │
└────────────┬─────────────────────────────┘
             │ TechnicalDossier
             ▼
      논문 간 관계·비교 가능성 분석
             │
             ▼
      최종 품질 gate·원자적 게시
             │
             ▼
 TechnicalResearchEnvelope + evidence registry
             │
   Domain / Market / Stakeholder / Report Agent
```

논문 하나라도 실패하면 일부 논문만으로 성공 결과를 발행하지 않는다.

## 3. LangGraph 실행 흐름

### 상위 그래프

```text
START → resolve_sources → research_documents → compare → finalize → END
```

| 노드 | 책임 |
|---|---|
| `resolve_sources` | `--source` 또는 자연어의 경로/arXiv ID를 해석하고 동일 SHA-256 입력을 제거한다. |
| `research_documents` | 논문별 subgraph를 기본 최대 3개 동시 실행한다. |
| `compare` | 성공 dossier만 사용해 기술 관계, 공통·상이한 가정, 비교 행렬, metric 비교 가능성과 결합 가설을 만든다. |
| `finalize` | 품질 지표와 artifact hash를 계산하고 staging 결과를 원자적으로 게시한다. |

### 논문별 subgraph

```text
index_common_sources
  → parse_documents
  → seed_critical_inventory
  → index_paper_sources
  → plan_paper_queries
  → retrieve_paper_evidence
  → enrich_paper_visuals
  → extract_paper_dossiers
  → audit_paper_dossiers
       ├─ 통과 → collect_documents
       └─ 실패 → 실패 facet 보강·재추출 → audit
```

| 노드 | 구현 이유 |
|---|---|
| `index_common_sources` | 사용자가 명시한 배경 코퍼스만 별도 권한으로 색인한다. |
| `parse_documents` | 페이지, 절, bbox, caption, 표 cell과 정확한 text span을 보존한다. |
| `seed_critical_inventory` | 초록·기여·결론·한계의 핵심 항목을 검색에서 놓치지 않기 위한 seed를 만든다. seed 자체는 claim이 아니다. |
| `index_paper_sources` | 논문별 BGE-M3 generation을 만들며 같은 fingerprint만 재사용한다. |
| `plan_paper_queries` | 사용자 목적과 논문 metadata에서 방법·실험·범위·한계·visual 질의를 만든다. |
| `retrieve_paper_evidence` | dense, learned sparse, ColBERT, RRF와 MMR로 관련성과 다양성을 확보한다. |
| `enrich_paper_visuals` | 검색된 핵심 표·그림 중 native 추출이 부족한 항목만 Vision으로 보강한다. |
| `extract_paper_dossiers` | 개요·범위·한계를 독립 structured output으로 병렬 추출하고 namespace된 ID로 병합한다. |
| `audit_paper_dossiers` | claim·observation 근거, 수치와 inventory 완전성을 검사하고 실패 facet만 보강한다. |
| `collect_documents` | 모든 논문이 성공한 경우만 dossier, evidence, audit와 trace를 상위 그래프에 전달한다. |

자유형 ReAct Agent가 아니라 고정 `StateGraph`를 사용한다. 검색, 출처 권한, 품질 판정과
retry 한도는 코드가 통제하며 LLM은 질의 계획·구조화 추출·감사·비교만 담당한다.

## 4. 문서 처리

지원 입력은 로컬 PDF, UTF-8 TXT/Markdown, arXiv ID다. 자연어 안의 로컬 문서 경로도
추출할 수 있다. arXiv ID는 `inputs/<id>.pdf`에 내려받는다.

- PyMuPDF: page text block, 좌표, 절 제목과 caption
- pdfplumber: native table의 row, column, cell과 Markdown
- BGE tokenizer 청크: 목표 800 tokens, overlap 120, hard limit 896
- table·caption: 일반 text와 분리된 element로 유지
- 긴 table: header를 반복한 row group으로 분할
- source SHA-256과 content hash: 문서 version과 중복 판정

유효 text가 기본 1,000자 미만이면 `failed_ingestion`으로 종료한다. 스캔 PDF 전체 OCR은
현재 범위가 아니다.

과제의 전체 RAG 문서 200쪽 제한은 입력 자료를 선정할 때 적용해야 한다. 이 브랜치는
참고문헌을 자동 수집하거나 입력 전체의 200쪽 상한을 자동 집행하지 않는다.

## 5. BGE-M3 하이브리드 검색

BGE-M3는 Qwen 계열이 아니라 XLM-RoBERTa 계열 모델이다. 운영 검색 경로는 로컬
`BAAI/bge-m3`의 세 표현을 함께 사용한다.

| 표현 | 저장소 | 역할 |
|---|---|---|
| 1024차원 dense | Chroma cosine collection | 의미적으로 유사한 표현 회수 |
| learned sparse | SQLite postings | 기술명, 모델명, 약어, 수치·단위 회수 |
| ColBERT multi-vector | content-hash 기반 float16 sidecar | query/document token MaxSim 재정렬 |

```text
query
 ├─ dense top-24
 └─ learned sparse top-24
          ↓
 RRF(k=60) → top-32
          ↓
 ColBERT MaxSim reranking
          ↓
 여러 query 결과 RRF
          ↓
 MMR λ=0.7 + numeric/visual 예약 슬롯
          ↓
 paper evidence 8 / common context 4
```

MMR은 유사한 청크가 최종 문맥을 독점하지 않게 한다. 수치 또는 명시적인 Table/Figure
질의에는 관련 locator가 후보 경계에서 탈락하지 않도록 제한된 예약 슬롯을 둔다.

모델은 실행 중 자동 다운로드하지 않는다. 명시적 설치 명령이 고정 commit
`5617a9f61b028005a4858fdac845db406aefb181`을 내려받고 파일 hash manifest를 만든다.
OpenAI embedding provider, 모델명 또는 클래스는 설정 단계에서 거부한다.

### paper와 common 출처 권한

| `source_kind` | 용도 | 허용 참조 |
|---|---|---|
| `paper` | 논문의 방법·실험·범위·한계 | `evidence_ids` |
| `common` | 사용자가 승인한 배경 문맥 | `context_evidence_ids`만 허용 |

공통 코퍼스만으로 특정 논문의 성능이나 결론을 지지할 수 없다. validator가 이 규칙을
강제한다. 기술조사 Agent는 웹 검색을 하지 않는다.

## 6. 선택적 표·그림 Vision

모든 PDF 페이지를 Vision에 보내지 않는다. native text와 pdfplumber cell을 우선 사용하고,
검색된 핵심 visual 중 픽셀 해석이 필요한 항목만 caption과 연결된 bbox로 crop한다.

- paper당 visual 최대 8개
- API request 최대 12개
- 총 32M pixels
- 동시 호출 최대 2개

Vision에는 base64 crop만 전달한다. 결과는 page, bbox, object label, cell과 crop SHA-256에
연결된다. `PRA_VISION_MODEL`을 설정하지 않으면 native 추출만 사용한다.

## 7. 추출, 감사와 품질 gate

### claim 종류

| 값 | 의미 |
|---|---|
| `author_claim` | 저자가 서술한 주장 |
| `observed_result` | 논문이 보고한 실험 또는 관측 결과 |
| `analyst_inference` | 근거에서 Agent가 도출했지만 논문이 직접 검증하지 않은 해석 |

두 기술의 결합 가능성처럼 공동 실험이 없는 내용은 `analyst_inference`로 유지하고 전제와
추가 검증 항목을 함께 기록한다.

`CriticalClaimInventory`의 모든 핵심 항목은 `extracted`, `excluded`, `unverified` 중 하나로
끝나야 한다. `unverified`는 실행한 검색 query와 확인하지 못한 이유를 보존한다.

성공 조건은 다음과 같다.

- evidence reference 해석률 100%
- locator 해석률 100%
- critical inventory 계약 충족률 100%
- unsupported numeric claim 0
- 비교 관계가 양쪽 paper 근거를 모두 소유
- 조건이 다른 실험 수치는 직접 비교하지 않음

감사 실패 시 누락 주제를 보강 검색하고 실패 facet만 최대 2회 재추출한다.

## 8. 출력 파일과 JSON 의미

```text
outputs/<job-id>/technical/
├── run.json
├── dossiers/<paper-id>.json
├── comparison.json
├── evidence_registry.json
├── retrieval_traces.jsonl
└── visuals/visual_crop-<hash>.png
```

실패 실행은 성공 `run.json` 대신 `failure.json`을 게시한다.

| 파일 | 의미 |
|---|---|
| `run.json` | `schema_version`, status, 모델·index·prompt metadata, token/메모리 사용량, artifact hash, dossier와 comparison의 인라인 복사본을 담은 진입점 |
| `dossiers/*.json` | 논문별 개요·범위·한계, claim, critical inventory, 실험 observation, 미확인 항목 |
| `comparison.json` | `substitute/complementary/orthogonal/dependency` 관계, 공통·상이한 가정, 비교 matrix, metric comparability, 결합 가설 |
| `evidence_registry.json` | 원문 hash, page, section, element, bbox, text span, table cell과 visual crop을 가진 실제 인용 근거 |
| `retrieval_traces.jsonl` | dense/sparse/ColBERT 순위와 점수, RRF 후보, 최종 chunk와 filter를 기록한 검색 디버깅 자료 |

`retrieval_traces.jsonl`은 주장 근거가 아니다. 후속 Agent가 인용할 수 있는 근거는
`evidence_registry.json`에 있는 ID뿐이다.

대표 evidence ID는 다음 형식이다.

```text
paper:<paper-id>@<sha12>:p0006:table-01:cell-r03-c04
```

## 9. 다른 팀 Agent와 연결

후속 Agent는 다음 순서로 결과를 소비한다.

1. `validate-technical`로 JSON, artifact hash와 locator를 검증한다.
2. `run.json.status == "succeeded"`와 호환 `schema_version`을 확인한다.
3. dossier의 claim과 observation을 선택한다.
4. comparison의 `not_comparable`과 기술 관계를 유지한다.
5. 선택한 ID를 evidence registry에서 해석한다.
6. 후속 출력에도 사용한 `claim_id`, `observation_id`, `evidence_id`를 보존한다.
7. 회사 조건과 시장 자료는 별도 가정·출처로 관리한다.

어느 Agent도 `analyst_inference`를 논문 저자의 주장이나 실험 결과로 승격하면 안 된다.
상세 계약은
[기술조사 Agent RAG 설계 및 외부 평가 Agent 연계 명세](docs/technical-research-rag-integration.md)를
참고한다.

## 10. 코드 구성

| 경로 | 역할 |
|---|---|
| `cli.py` | research, model pull, 검증, Markdown export CLI |
| `research_api.py` | 공개 Python API, 서비스 조립, job lock, checkpoint 재개와 충돌 검사 |
| `research_graph.py` | 상위·논문별 LangGraph, audit/repair loop와 원자적 게시 |
| `source_paths.py` | 자연어 지시에서 로컬 문서 경로 추출 |
| `documents.py` | source/arXiv 해석, PDF/TXT/MD 파싱, table·caption·chunk 생성 |
| `model_management.py` | 고정 BGE-M3 snapshot 다운로드·hash 검증과 local embedder |
| `bge_retrieval.py` | Chroma dense, SQLite sparse, ColBERT sidecar, RRF·MMR·filter·trace |
| `technical_models.py` | OpenAI structured output, facet 병합, ID와 inventory 정규화 |
| `vision.py` | visual 후보, budget, crop과 OpenAI Vision 구조화 |
| `technical_schemas.py` | 외부 입력·출력과 중간 artifact Pydantic 계약 |
| `technical_validation.py` | 출처 권한, numeric locator, artifact hash와 comparison 검증 |
| `technical_markdown.py` | JSON을 사람이 읽는 Markdown 참고본으로 변환 |
| `tests/` | parser, retrieval, graph, 계약, Vision, Markdown과 E2E artifact 테스트 |

## 11. 설치와 환경 변수

Python 3.12와 `uv`를 사용한다.

```bash
uv sync --frozen --extra dev
cp .env.example .env
uv run paper-review models pull bge-m3
```

```dotenv
OPENAI_API_KEY=...
PRA_OPENAI_MODEL=gpt-5.6-terra
PRA_AUDIT_MODEL=gpt-5.6-terra
PRA_OPENAI_REASONING_EFFORT=high
PRA_BGE_DEVICE=cpu
```

API key는 provider SDK가 환경에서 직접 읽으며 결과나 로그에 기록하지 않는다.
LangSmith/LangChain 외부 tracing은 fail-closed로 비활성화한다. CPU 기본 batch는 1이며
CUDA 환경은 `PRA_BGE_DEVICE=cuda`로 선택할 수 있다.

## 12. 실행 예시

### 파일 입력

```bash
uv run paper-review research \
  --source /path/2605.08317.pdf \
  --source /path/2607.27187.pdf \
  --instruction '장문맥 문서 QA 데이터센터·클라우드 서빙 관점에서 비교해줘' \
  --job-id long-context-datacenter
```

### arXiv ID 입력

```bash
uv run paper-review research \
  --source 2605.08317 \
  --source 2607.27187 \
  --instruction '두 기술의 메커니즘, 실험 조건과 한계를 비교해줘'
```

### 자연어 안의 경로

```bash
uv run paper-review research \
  '/path/paper-a.pdf와 /path/paper-b.pdf를 읽고 클라우드 서빙 관점에서 비교해줘'
```

승인된 배경 문맥은 `--common-source`로만 전달한다. 자동 발견하지 않는다.

## 13. 체크포인트, 캐시와 재실행

- checkpoint: `work/research-checkpoints.sqlite`
- LangGraph `thread_id`: `job_id`
- 같은 job ID와 같은 request: checkpoint 또는 종결 결과 재사용
- source hash 변경 또는 같은 job ID에 다른 request: 충돌로 거부
- 새 분석 조건: 새 job ID 사용
- 같은 job ID의 강제 재실행: `--force-reindex`

논문별 cache key에는 source, request, common corpus, retrieval profile과 Vision 설정이
포함된다. `data/index`, `data/models`, `work`, `outputs`는 재생성 가능한 local runtime
data이며 GitHub에는 올리지 않는다.

## 14. 검증과 Markdown 변환

```bash
uv run paper-review validate-technical outputs/<job-id>/technical/run.json
uv run paper-review export-technical-md outputs/<job-id>/technical/run.json
uv run pytest
```

validator는 단순 JSON Schema 외에도 artifact hash, dossier와 run envelope의 일치, source
hash와 page 범위, evidence ID/locator, 숫자·table cell, comparison 조건을 검사한다.

Markdown은 기본적으로 다음 위치에 만들어지는 읽기 전용 파생본이다.

```text
outputs/<job-id>/technical/markdown/
├── README.md
├── dossiers/<paper-id>.md
├── comparison.md
└── evidence_registry.md
```

## 15. 공개 결과

- [두 논문 기본 기술 비교](examples/results/technical-bge-e2e-two-papers)
- [장문맥 QA 데이터센터 관점 비교](examples/results/technical-long-context-qa-datacenter)

두 디렉터리에는 JSON과 사람이 읽는 Markdown이 함께 있다. 원본 PDF, API key와 model
weight는 포함하지 않는다. `source_manifest.json`의 원본을 `inputs/`에 놓으면 source
SHA-256을 포함한 전체 계약을 검증할 수 있다.

## 16. 실패 상태와 현재 범위

| 상태 | 의미 |
|---|---|
| `succeeded` | 모든 필수 논문, comparison과 최종 품질 gate 통과 |
| `failed_ingestion` | 파일 누락, 손상, 미지원 형식 또는 text 품질 부족 |
| `failed_quality` | 최대 보강 후에도 근거·계약·완전성 기준 미충족 |
| `provider_error` | OpenAI 또는 local model/의존성 실행 경계 실패 |

현재 범위에 포함되지 않는 기능은 다음과 같다.

- 스캔 PDF 전체 OCR
- 참고문헌 자동 수집과 200쪽 한도 자동 편성
- 시장·이해관계자·종합 평가 Agent
- LaTeX 최종 보고서 생성·개선
- 두 기술을 함께 구현한 실제 PoC 성능 검증

`integration_hypotheses`는 도입 권고가 아니라 후속 평가와 PoC가 검증해야 할 기술
가설이다.
