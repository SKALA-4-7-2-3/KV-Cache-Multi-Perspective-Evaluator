# 기술조사 Agent RAG 설계 및 외부 평가 Agent 연계 명세

## 1. 문서 목적

이 문서는 현재 구현된 **기술조사 Agent**의 역할, RAG 구현 방식, 출력 JSON 계약과 다른 팀원이 구현하는 후속 Agent의 연결 방법을 설명한다.

현재 보류된 사항은 다음과 같다.

- PyMuPDF4LLM로 전체 PDF를 재변환하는 변경
- 참고논문을 200쪽 한도까지 자동 수집하는 기능
- GPT 분석 결과만을 대상으로 하는 별도 검색 인덱스

따라서 이 문서의 기준은 현재 성공한 BGE-M3 기반 기술조사 파이프라인이다. 대표 성공 실행은 다음 경로에 있다.

```text
outputs/technical-bge-e2e-20260922-v22/technical/
```

이 구현의 책임 범위는 논문에서 기술적 사실을 추출하고 비교 가능한 구조로 만드는 데까지다. 시장성, 이해관계자 영향, 사업성, 종합 점수와 최종 보고서는 이 저장소의 기술조사 결과를 입력으로 사용하되, 다른 팀원이 구현한 별도 Agent가 담당할 수 있다.

---

## 2. 기술조사 Agent가 해결하는 문제

후속 평가 Agent가 PDF를 매번 직접 읽고 해석하도록 두면 다음 문제가 발생한다.

1. 같은 논문에 대해 Agent마다 서로 다른 수치와 한계를 추출할 수 있다.
2. 평가 결과가 어느 페이지, 문장, 표 셀에서 나왔는지 추적하기 어렵다.
3. 측정, 에뮬레이션, 시뮬레이션 결과가 하나의 성능 수치처럼 섞일 수 있다.
4. 모델, 하드웨어, context length, workload가 다른 실험을 직접 비교할 위험이 있다.
5. 시장·사업 판단 과정에서 논문에 없는 내용을 논문의 결론처럼 인용할 수 있다.

기술조사 Agent는 PDF와 후속 평가 사이에 **검증된 기술 사실 계층**을 둔다. 결과적으로 후속 Agent는 PDF 파싱이나 검색 알고리즘을 다시 구현할 필요 없이 다음 질문에 집중할 수 있다.

- 이 기술이 회사 환경에 적합한가?
- 누가 이익을 얻고 누가 추가 부담을 지는가?
- 실제 도입 옵션과 중단 조건은 무엇인가?
- 논문에서 검증된 부분과 아직 가설인 부분은 무엇인가?

---

## 3. 전체 시스템에서의 위치

```text
사용자 지시 + 논문 PDF/arXiv
        │
        ▼
┌─────────────────────────────┐
│ 기술조사 Agent              │
│                             │
│ 문서 파싱                    │
│ → RAG 검색                  │
│ → 개요·범위·한계 추출       │
│ → 수치·조건 정규화          │
│ → 근거 감사                 │
│ → 논문 간 기술 비교         │
└──────────────┬──────────────┘
               │ versioned JSON artifacts
               ▼
┌────────────────────────────────────────────────────┐
│ 다른 팀원이 구현하는 후속 Agent                    │
│                                                    │
│ Domain Agent       Market Agent                    │
│ Stakeholder Agent  Architecture/Option Agent       │
│             └────── Synthesis Agent ──────┐        │
│                                           ▼        │
│                                     Report Agent   │
└────────────────────────────────────────────────────┘
```

Agent끼리 자유 형식 대화를 주고받는 방식은 권장하지 않는다. 팀마다 프롬프트와 런타임이 달라도 연결할 수 있도록 파일 또는 API 경계에서 버전형 JSON을 교환한다.

핵심 연결 원칙은 다음과 같다.

- 기술조사 결과는 **사실과 근거의 공급자**다.
- 후속 Agent는 기술조사 JSON을 수정하지 않고 자신의 평가 아티팩트를 새로 만든다.
- 모든 후속 주장은 입력으로 사용한 `claim_id`, `observation_id`, `evidence_id`를 보존한다.
- 논문에 없는 회사 조건과 시장 정보는 별도 출처 또는 명시적 가정으로 관리한다.
- `analyst_inference`를 논문 저자의 주장이나 실험 결과로 승격하지 않는다.

---

## 4. 현재 LangGraph 실행 흐름

상위 그래프와 논문별 하위 그래프를 분리한다.

### 4.1 상위 그래프

```text
START
  → resolve_sources
  → research_documents
  → compare
  → finalize
  → END
```

- `resolve_sources`: 명시적 source 또는 자연어의 경로/arXiv ID를 해석하고 SHA-256 중복을 제거한다.
- `research_documents`: 아래 논문별 하위 그래프를 실행한다. 여러 논문은 최대 3개까지 병렬 처리한다.
- `compare`: 성공한 dossier들만 이용해 논문 간 관계와 비교 가능성을 생성하고 계약을 검사한다.
- `finalize`: 품질 지표와 아티팩트 해시를 계산하고 성공 시 `run.json`, 실패 시 `failure.json`을 원자적으로 게시한다.

필수 논문 하나라도 실패하면 부분 결과를 정상 성공 결과로 발행하지 않는다.

### 4.2 논문별 하위 그래프

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
       └─ 실패 → 보강 검색·실패 facet 재추출, 최대 2회
```

각 노드의 의미는 다음과 같다.

| 노드 | 책임 |
|---|---|
| `index_common_sources` | 사용자가 명시적으로 허용한 공통 코퍼스만 별도 색인한다. |
| `parse_documents` | PDF/TXT/Markdown을 페이지·절·표·캡션·좌표가 있는 요소로 변환한다. |
| `seed_critical_inventory` | 초록·기여·결론·한계 절을 찾기 위한 검색 seed를 만든다. 이 단계의 텍스트 자체는 검증된 주장이 아니다. |
| `index_paper_sources` | 논문별 BGE-M3 인덱스를 만들거나 동일 fingerprint의 기존 인덱스를 재사용한다. |
| `plan_paper_queries` | 문제, 메커니즘, 실험, 범위, 한계, visual별 검색 질의를 생성한다. |
| `retrieve_paper_evidence` | dense·sparse·ColBERT·MMR로 근거 후보를 선택한다. |
| `enrich_paper_visuals` | 검색된 핵심 표·그림 중 픽셀 해석이 필요한 항목만 Vision으로 보강한다. |
| `extract_paper_dossiers` | 기술 개요, 범위, 한계를 독립 facet으로 병렬 추출하고 하나의 dossier로 조립한다. |
| `audit_paper_dossiers` | 주장별 근거, 수치 조건, inventory 완전성을 감사한다. 실패한 facet만 다시 실행한다. |
| `collect_documents` | 성공한 dossier, evidence, audit, trace를 상위 그래프에 전달한다. |

체크포인트는 SQLite의 `thread_id=job_id`로 관리한다. 네트워크 오류나 프로세스 중단 후에도 같은 job ID로 상태를 이어갈 수 있다.

---

## 5. 왜 RAG를 사용하는가

### 5.1 전체 PDF를 한 번에 LLM에 넣는 것과의 차이

전체 PDF 입력은 요약에는 편리하지만, 기술 평가용 데이터 생성에는 부족하다. 특히 부록의 실험 조건, 표의 특정 셀, 명시적 한계가 긴 입력 안에서 누락되기 쉽고 어떤 문장이 결론의 근거였는지 재현하기 어렵다.

현재 RAG는 다음 역할을 한다.

- 질문별로 관련성이 높은 근거만 추출 모델에 공급한다.
- 표·그림·부록처럼 본문 요약에서 빠지기 쉬운 요소를 별도 후보로 검색한다.
- 주장과 원문 위치 사이에 안정적인 ID를 만든다.
- 감사 실패 시 전체 분석이 아니라 누락 주제만 보강 검색한다.
- 후속 Agent가 필요한 사실만 근거와 함께 선택할 수 있게 한다.

즉 RAG의 목적은 단순한 비용 절감이 아니라 **근거 회수, 추적성, 실패 복구와 후속 Agent 간 사실 일관성**이다.

### 5.2 RAG가 보장하지 않는 것

RAG가 있다고 해서 검색 결과가 자동으로 참이 되는 것은 아니다.

- 파서가 표 구조를 잘못 복원할 수 있다.
- 검색기가 중요한 청크를 놓칠 수 있다.
- LLM이 근거를 과도하게 일반화할 수 있다.
- 서로 다른 실험 조건의 수치가 우연히 같은 metric 이름을 가질 수 있다.
- 두 기술의 결합 가능성은 실제 공동 실험이 아니라 분석자 가설일 수 있다.

이 때문에 검색 결과를 곧바로 보고서 문장으로 사용하지 않고, 구조화 추출·계약 검사·독립 감사·`UnverifiedItem` 처리를 거친다.

---

## 6. 문서 처리와 청크 구성

### 6.1 추출

- PyMuPDF로 페이지, 텍스트 블록, 좌표, 절 제목과 캡션을 추출한다.
- pdfplumber로 native table의 셀과 행·열 구조를 복원한다.
- 표, 캡션, 일반 텍스트는 서로 다른 `content_kind`를 가진다.
- 그림 픽셀 전체를 항상 분석하지 않는다. 검색된 핵심 visual만 crop한 뒤 OpenAI Vision에 base64로 전달한다.
- Vision 결과도 원본 페이지, bbox, 표/그림 번호, crop SHA-256과 연결한다.

### 6.2 분할

- 절 → 단락 → 문장 계층을 가능한 한 유지한다.
- BGE tokenizer 기준 목표 800 tokens, 중첩 120 tokens, hard limit 896 tokens다.
- 절 제목은 해당 청크의 문맥으로 유지한다.
- 표와 캡션은 독립 요소다.
- 긴 표는 header가 유지된 row group으로 나눈다.
- 원문 SHA-256과 content hash로 중복 및 인덱스 세대를 구분한다.

### 6.3 논문 코퍼스와 공통 코퍼스

두 코퍼스의 권한은 다르다.

| 구분 | 용도 | 주장 근거 사용 |
|---|---|---|
| `paper` | 현재 분석 중인 논문의 방법·실험·범위·한계 | `evidence_ids`에 사용 가능 |
| `common` | 사용자가 승인한 배경 설명과 용어 문맥 | `context_evidence_ids`에만 사용 가능 |

공통 코퍼스만으로 특정 논문의 성능이나 결론을 지지할 수 없다. 후속 Agent도 이 출처 규칙을 유지해야 한다.

---

## 7. BGE-M3 검색 구현

### 7.1 저장 구조

현재 기술조사 검색은 로컬 BGE-M3의 세 표현을 함께 사용한다.

| 표현 | 저장소 | 역할 |
|---|---|---|
| 1024차원 dense vector | Chroma cosine collection | 의미적으로 유사한 문장과 표현을 회수한다. |
| learned sparse vector | SQLite postings | 정확한 용어, 모델명, 수치 단위, 약어에 강한 후보를 회수한다. |
| ColBERT multi-vector | content hash 기반 float16 sidecar | query token과 문서 token의 세밀한 대응으로 후보를 재정렬한다. |

논문, 원문 버전, 모델 revision, tokenizer 설정과 청크 설정을 포함한 fingerprint로 인덱스 profile을 구분한다. 다른 embedding profile의 벡터를 혼합하지 않는다.

### 7.2 질의 계획

OpenAI 구조화 출력으로 다음 질의 그룹을 만든다.

- `critical_inventory`: 초록, 기여, 결론, headline result
- `mechanisms`: 알고리즘, 수식, 시스템 구성, 데이터 흐름
- `experiments`: metric, baseline, 모델, 하드웨어, workload, 측정 방법
- `scope`: 적용 task, domain, modality, operating condition
- `limitations`: limitation, assumption, failure case, ablation, future work, 재현성
- `visuals`: 핵심 표와 그림 번호·caption·수치

논문의 제목·초록, 사용자의 분석 목적과 고정된 필수 검색어가 함께 사용된다. PDF나 사용자 텍스트 안의 명령문은 도구 실행 지시가 아닌 검색 대상 데이터로 취급한다.

### 7.3 한 질의의 검색 순서

```text
질의
 ├─ dense top-24
 └─ learned sparse top-24
          ↓
 Reciprocal Rank Fusion
          ↓
       top-32
          ↓
 ColBERT MaxSim 재정렬
```

RRF 점수는 다음과 같다. 현재 `k=60`이다.

```text
RRF(d) = Σ 1 / (60 + rank_i(d))
```

ColBERT는 query token마다 가장 유사한 document token을 찾은 후 그 최댓값들의 평균을 계산한다.

```text
MaxSim(q, d) = mean_i(max_j(q_i · d_j))
```

### 7.4 다중 질의 융합과 MMR

각 질의에서 ColBERT 순서를 얻은 뒤 질의 간 결과를 다시 RRF로 합친다. 마지막으로 dense vector 간 중복도를 이용해 MMR을 적용한다.

```text
MMR(d) = 0.7 × normalized_relevance(d)
       - 0.3 × max_similarity(d, already_selected)
```

각 query group은 논문 근거 최대 8개, 명시적으로 승인된 공통 문맥 최대 4개를 반환하고, 전체 group 결과를 합쳐 중복을 제거한다. 수치 질의 또는 명시적인 `Table/Figure` 질의에는 관련 visual locator가 후보 경계에서 탈락하지 않도록 제한된 예약 슬롯을 둔다.

### 7.5 검색 trace의 역할

검색할 때 다음이 기록된다.

- 원래 query
- dense/sparse 순위와 점수
- RRF 후보
- ColBERT 순위와 점수
- 최종 선택 chunk ID
- 수치·visual 예약 chunk ID
- 적용한 document/page/section/content kind 필터
- index profile fingerprint

이 기록은 재현성과 검색 품질 디버깅용이다. 후속 평가 Agent가 기술 주장의 근거로 직접 인용해서는 안 된다. 실제 근거는 `evidence_registry.json`에서 읽는다.

---

## 8. 추출·감사·보강 방식

### 8.1 세 facet 병렬 추출

논문 하나의 결과를 다음 세 facet으로 나눈다.

1. `technical_overview`: 문제, 핵심 접근법, 구성요소, 알고리즘·수식, 실행 과정, 자원 요구, 실험 결과
2. `scope`: task, domain, modality, 평가 설정, 저자 주장 범위, 분석자 추론 범위, 범위 밖 조건
3. `limitations`: 저자 명시 한계, 추론된 한계, 계산·데이터·일반화·재현성 제약, 미보고 항목

세 facet은 독립 structured output 호출로 생성되며 전체 실행의 LLM 동시 호출은 최대 3개다. facet 내부의 짧은 ID는 조립할 때 `paper_id::facet::local_id`로 namespace한다.

### 8.2 주장 종류

| `claim_type` | 의미 | 후속 Agent의 취급 |
|---|---|---|
| `author_claim` | 논문 저자가 서술한 주장 | 저자 주장으로 표시하고 근거를 연결한다. |
| `observed_result` | 논문이 보고한 실험 또는 관측 결과 | 조건이 일치할 때만 비교한다. |
| `analyst_inference` | 여러 근거에서 분석 Agent가 도출한 해석 | 검증된 사실이 아니라 추론으로 유지한다. |

### 8.3 독립 감사와 repair

추출 후 감사기는 다음을 검사한다.

- 모든 주장 ID가 실제 근거로 해석되는가?
- 수치와 단위가 원문과 일치하는가?
- headline method, result, scope, limitation이 inventory에 포함됐는가?
- 공통 코퍼스가 논문 주장 근거로 잘못 사용됐는가?
- 관측 결과에 model, hardware, context, baseline, workload, 평가 방식이 가능한 만큼 보존됐는가?

감사 실패 시 누락 주제만 보강 검색하고 실패한 facet만 재추출한다. 최초 시도 후 최대 2회 repair한다. 끝내 확인되지 않은 내용은 일반 지식으로 채우지 않고 `UnverifiedItem`으로 남기거나 전체 실행을 `failed_quality`로 종료한다.

---

## 9. 출력 디렉터리와 각 파일의 의미

성공 출력은 다음과 같다.

```text
outputs/<job-id>/technical/
├── run.json
├── dossiers/
│   ├── <paper-a-id>.json
│   └── <paper-b-id>.json
├── comparison.json
├── evidence_registry.json
├── retrieval_traces.jsonl
└── visuals/
    └── visual_crop-<hash>.png
```

실패 실행은 `run.json` 대신 `failure.json`을 생성한다.

### 9.1 `run.json`: 실행 봉투이자 진입점

후속 Agent가 가장 먼저 읽어야 하는 파일이다. 다음을 담는다.

- `schema_version`: 실행 봉투 계약 버전
- `status`: 실행 성공 여부
- `run`: 모델·인덱스·프롬프트·토큰·메모리·시간 metadata
- `artifacts`: 개별 출력 파일의 경로·SHA-256·producer
- `dossiers`: 논문별 dossier의 인라인 복사본
- `comparison`: 교차 논문 비교의 인라인 복사본
- `evidence_registry_path`: 근거 레지스트리 경로
- `quality`: 성공 품질 지표
- `diagnostics`: 실패 또는 경고 진단

현재 `v22`의 주요 값은 다음과 같다.

```json
{
  "schema_version": "1.0.0",
  "status": "succeeded",
  "run": {
    "job_id": "technical-bge-e2e-20260922-v22",
    "openai_model": "gpt-5.6-terra",
    "embedding_model": "BAAI/bge-m3",
    "embedding_revision": "5617a9f61b028005a4858fdac845db406aefb181",
    "evidence_id_version": "2.0.0",
    "index_version": "1.2.0"
  },
  "quality": {
    "evidence_resolution_rate": 1.0,
    "critical_inventory_coverage": 1.0,
    "unsupported_numeric_claims": 0,
    "locator_resolution_rate": 1.0,
    "warnings": []
  }
}
```

`run.json` 안의 dossier와 comparison은 편의상 포함한 것이다. 외부 시스템이 개별 파일을 사용할 때는 `artifacts[].sha256`을 검증해야 한다.

### 9.2 `dossiers/<paper-id>.json`: 논문별 기술 사실 묶음

주요 필드는 다음과 같다.

| 필드 | 의미 |
|---|---|
| `dossier_version` | dossier 계약 버전 |
| `paper` | 논문 ID, 제목, 저자, 초록, arXiv ID, source hash, page count |
| `analysis` | `technical_overview`, `scope`, `limitations` 구조화 설명 |
| `claims` | 후속 Agent가 재사용할 원자적 기술 주장 |
| `critical_inventory` | 핵심 항목을 빠짐없이 처리했는지 나타내는 목록 |
| `experiment_observations` | 수치와 실험 조건을 함께 보존한 관측 레코드 |
| `unverified_items` | 검색했지만 확인하지 못한 내용과 검색 이력 |
| `evidence_ids` | dossier 전체가 참조하는 근거 ID의 합집합 |

#### `TechnicalClaim`

```json
{
  "claim_id": "2605.08317-25836a41::technical_overview::to-c01",
  "text": "장문맥 LLM 추론에서 KV cache의 선형적 증가와 HBM 재읽기는 memory-bound inference를 유발한다.",
  "claim_type": "author_claim",
  "evidence_ids": ["paper:...:p0001:...:span-00000-01494"],
  "context_evidence_ids": [],
  "confidence": 0.99,
  "critical": true
}
```

- `claim_id`는 후속 평가의 provenance 연결 키다.
- `critical=true`는 의사결정에 중요한 핵심 주장을 의미한다.
- `confidence`는 모델의 확신이지 논문 결과의 통계적 신뢰구간이 아니다.

#### `CriticalClaimItem`

모든 핵심 후보는 다음 중 하나로 소진된다.

- `extracted`: 주장과 근거가 추출됨
- `excluded`: 논문 분석 대상이 아니며 이유가 있음
- `unverified`: 검색했지만 확인하지 못했고 질의와 이유가 있음

후속 Agent는 inventory의 개수 자체를 점수로 사용하면 안 된다. 중요한 것은 특정 의사결정 주제가 `extracted`인지 `unverified`인지다.

#### `ExperimentObservation`

```json
{
  "observation_id": "2605.08317-25836a41::technical_overview::to-o01",
  "metric": "decode latency",
  "value": "~18",
  "unit": "ms/token",
  "baseline": "FullKV FA2: 82 ms/token; reported RDKV speedup: 4.5×",
  "model": "LLaMA-3.1-8B-Instruct",
  "hardware": "single A100 64 GB",
  "context_length": "128K",
  "evaluation_mode": "measured",
  "evidence_ids": ["paper:..."],
  "confidence": 0.99
}
```

수치 비교의 기본 단위는 `metric`만이 아니라 이 레코드 전체다. model, hardware, context, concurrency, dataset, workload, baseline 또는 evaluation mode가 다르면 직접 우열 비교를 피해야 한다.

#### `UnverifiedItem`

- 확인하지 못한 `topic`
- 확인 실패 `reason`
- 실제 `searched_queries`
- 적용한 `filters`
- 전체 시도 횟수 `attempts`

이는 빈 값이 아니라 중요한 음성 결과다. 후속 Agent는 이를 위험, 추가 검증 과제 또는 PoC 항목으로 전달해야 한다.

### 9.3 `comparison.json`: 논문 간 기술 관계

| 필드 | 의미 |
|---|---|
| `relationships` | `substitute`, `complementary`, `orthogonal`, `dependency` 중 기술 관계 |
| `common_assumptions` | 두 논문이 공유하는 가정과 각 논문의 근거 |
| `differing_assumptions` | 같은 차원에서 논문별 조건이 다른 경우와 그 영향 |
| `matrix` | 메커니즘·실험·제약 등 비교 차원별 논문 요약 |
| `metric_comparisons` | observation ID 간 직접 비교 가능 여부 |
| `integration_hypotheses` | 두 기술의 결합 가설, 전제, 추가 검증 항목 |
| `contradictions` | 논문 간 명시적 충돌 |
| `unverified_items` | 교차 비교 단계에서 확인되지 않은 내용 |

예를 들어 현재 결과는 RDKV와 Photonic-CXL을 `complementary`로 분류하지만 `tested_together=false`로 기록한다. 이는 “결합 효과가 검증됐다”는 뜻이 아니라 서로 다른 계층에서 작동하므로 조합 가능성이 있다는 분석자 추론이다.

`MetricComparison.comparability`가 `not_comparable`이면 후속 Agent는 원 수치로 순위를 만들지 않아야 한다. 현재 TTFT 예시는 단일 GPU 측정과 대규모 serving simulation이므로 직접 비교 불가로 처리되어 있다.

### 9.4 `evidence_registry.json`: 주장과 원문을 연결하는 레지스트리

각 항목은 다음을 포함한다.

| 필드 | 의미 |
|---|---|
| `evidence_id` | 모든 JSON이 공통으로 참조하는 고유 근거 키 |
| `source_kind` | `paper` 또는 `common` |
| `document_id` | 근거가 속한 문서 |
| `content_kind` | text, table, caption, figure, chart, diagram |
| `extraction_method` | native_text, pdfplumber, vision |
| `snippet` | 모델이 실제로 본 원문 근거 |
| `content_hash` | snippet 내용의 무결성 확인 값 |
| `locator` | 원문에서 근거를 다시 찾기 위한 위치 정보 |

`locator`에는 다음 정보가 있다.

- 원문 전체 SHA-256
- 물리 페이지와 인쇄 페이지 라벨
- 절 경로
- public element ID와 parser source element ID
- PDF top-left point 좌표의 bbox와 page size
- 정확한 text span
- 표의 row/column index와 row/column header
- visual crop artifact와 crop SHA-256

근거 ID 예시는 다음과 같다.

```text
paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r07-c03
```

의미는 `document_id@source_sha12`, 물리 3페이지, `table-01`, 7행 3열 셀이다. 후속 Agent가 사람에게 근거를 표시할 때는 ID 문자열을 해석해 새 정보를 만들지 말고 registry의 locator를 읽어야 한다.

### 9.5 `retrieval_traces.jsonl`: 검색 재현 및 진단 로그

한 줄이 하나의 retrieval trace다. JSON 배열이 아니라 JSONL이므로 줄 단위로 읽는다.

용도는 다음과 같다.

- 어떤 질의가 어떤 청크를 회수했는지 확인
- dense, sparse, ColBERT 중 어디에서 후보가 탈락했는지 분석
- index profile과 filter 재현
- golden retrieval benchmark 및 회귀 테스트

이 파일은 후속 평가 Agent의 정상 입력에 포함하지 않는 것이 좋다. 검색 실패를 조사하거나 새 질의를 계획하는 보조 Agent만 제한적으로 사용한다.

### 9.6 `failure.json`: 소비해서는 안 되는 실행 결과

가능한 실패 상태는 다음과 같다.

- `failed_ingestion`: 파일 손상, 텍스트 부족, 미지원 입력 등
- `failed_quality`: 근거·locator·inventory·수치 감사 실패
- `provider_error`: OpenAI 등 공급자 호출 실패

`failure.json`에는 diagnostics와 실행 metadata가 남지만, 후속 평가를 위한 정상 dossier로 사용해서는 안 된다. 일부 dossier가 들어 있더라도 전체 작업이 성공했다는 뜻이 아니다.

---

## 10. 다른 팀의 Agent와 연결하는 표준 방식

### 10.1 권장 데이터 전달 경계

```text
Technical Research output directory
        │
        ▼
팀 공통 Intake Adapter
  1. run.json 로드
  2. schema/status 검사
  3. artifact SHA-256 검사
  4. evidence registry를 evidence_id로 색인
  5. Agent별 최소 입력 DTO 생성
        │
        ├─ DomainAssessmentInput
        ├─ MarketAssessmentInput
        ├─ StakeholderAssessmentInput
        └─ ArchitectureOptionInput
```

후속 Agent마다 이 저장소의 내부 Python 클래스를 직접 import하도록 강제하지 않는다. 팀 공통 Intake Adapter가 JSON 1.0.0을 각 팀의 내부 타입으로 변환하면 구현 언어와 프레임워크가 달라도 연동할 수 있다.

### 10.2 소비 전 필수 검사

```python
from pathlib import Path

from paper_review_agent import validate_technical_research

report = validate_technical_research(Path("outputs/<job-id>/technical/run.json"))
if not report.valid:
    raise RuntimeError(report.errors)
```

외부 팀이 이 Python 패키지를 사용할 수 없다면 동일하게 다음을 검사한다.

1. `schema_version == "1.0.0"`
2. `status == "succeeded"`
3. `quality.evidence_resolution_rate == 1.0`
4. `quality.locator_resolution_rate == 1.0`
5. `quality.unsupported_numeric_claims == 0`
6. 각 artifact 파일의 SHA-256이 `artifacts`와 일치
7. 참조된 모든 `evidence_id`가 registry에 존재
8. paper claim의 `evidence_ids`가 해당 paper 소유 근거를 포함

### 10.3 Agent별 권장 입력

#### Domain Assessment Agent

읽어야 할 값:

- dossier의 `technical_overview`, `scope`, `limitations`
- 조건이 완전한 `experiment_observations`
- comparison의 relationship, assumption, matrix, metric comparability
- 관련 evidence registry 항목

작성해야 할 결과:

- 기술 적합성, 인프라 호환성, 병목, 재현성, TRL
- 각 평가의 `source_claim_ids`, `source_observation_ids`, `evidence_ids`
- 논문에서 확인되지 않은 조건과 자체 가정

#### Market Assessment Agent

읽어야 할 값:

- 기술의 대상 범위와 필요한 하드웨어·소프트웨어 조건
- 논문이 명시한 제약과 integration hypothesis

시장 가격, 공급자, 제품 출시 상태는 이 JSON에 없다. Market Agent가 별도 조사 근거를 생성해야 하며 웹 근거 ID와 paper evidence ID를 구분해야 한다. 논문 근거로 시장 가격이나 공급 가능성을 주장하면 안 된다.

#### Stakeholder Assessment Agent

읽어야 할 값:

- 구현 복잡도와 운영 제약
- 하드웨어 의존성
- 품질·성능 trade-off
- unverified item과 validation-needed 항목

경영진, 플랫폼팀, ML 엔지니어, SRE, 보안, 재무 관점의 영향은 후속 Agent의 평가다. 이를 `author_claim`으로 표시하지 않는다.

#### Architecture/Option Agent

읽어야 할 값:

- `relationships`
- `integration_hypotheses`
- `differing_assumptions`
- `metric_comparisons`

현재 예시에서는 최소한 다음 옵션을 독립적으로 구성할 수 있다.

- KV-cache 압축만 적용
- 외부/CXL 메모리 계층만 적용
- 압축과 메모리 계층을 함께 적용
- 현행 구조 유지

결합 옵션은 `integration_hypotheses.validation_needed`를 PoC 검증 항목으로 그대로 전달해야 한다.

#### Synthesis와 Report Agent

Synthesis Agent는 기술조사 JSON을 직접 재해석하기보다 각 평가 Agent의 결과와 provenance를 결합한다. 최종 보고서의 기술 문장은 다음 연결을 유지해야 한다.

```text
보고서 문장
  → 평가 claim ID
  → 기술조사 claim/observation ID
  → evidence ID
  → 문서 hash + 페이지 + span/table cell
```

### 10.4 권장 후속 평가 레코드

다른 팀의 스키마를 강제하지는 않지만 최소한 다음 의미는 보존하는 것이 좋다.

```json
{
  "assessment_id": "domain-rdkv-memory-fit-01",
  "text": "현재 A100 기반 장문맥 서비스에서는 메모리 절감 가능성이 있으나 동일 workload PoC가 필요하다.",
  "assessment_type": "analyst_inference",
  "source_claim_ids": [
    "2605.08317-25836a41::technical_overview::to-c01"
  ],
  "source_observation_ids": [
    "2605.08317-25836a41::technical_overview::to-o01"
  ],
  "evidence_ids": ["paper:..."],
  "assumptions": ["회사의 모델과 kernel 경로가 논문의 평가 조건과 충분히 유사함"],
  "uncertainty": "medium",
  "validation_needed": ["사내 모델·실제 concurrency에서 TTFT와 TPOT 측정"]
}
```

이 형태라면 후속 구현이 LangGraph, 다른 Agent 프레임워크 또는 일반 배치 프로그램이어도 기술 근거 연결이 유지된다.

---

## 11. ID와 버전 관리 규칙

### 11.1 ID별 역할

| ID | 역할 | 안정성 기대 |
|---|---|---|
| `job_id` | 한 번의 기술조사 실행 | 실행 단위 |
| `paper_id` | 문서 논리 ID | source hash가 바뀌면 suffix가 달라질 수 있음 |
| `claim_id` | 원자 기술 주장 | 같은 dossier 버전 안에서 안정적 |
| `observation_id` | 조건을 가진 실험 수치 | 같은 dossier 버전 안에서 안정적 |
| `inventory_id` | 핵심 항목 처리 상태 | 같은 dossier 버전 안에서 안정적 |
| `evidence_id` | 원문 locator | evidence ID 버전과 source hash에 종속 |
| `artifact_id` | 파일 내용 해시 기반 아티팩트 ID | 동일 내용이면 동일 |
| `index_profile` | 임베딩·청크·모델 설정 fingerprint | 설정 변경 시 달라짐 |

### 11.2 현재 버전 조합

현재 대표 성공본은 다음을 사용한다.

- envelope/dossier/comparison contract: `1.0.0`
- evidence ID: `2.0.0`
- index: `1.2.0`
- BGE-M3 revision: `5617a9f61b028005a4858fdac845db406aefb181`

후속 Agent는 버전 문자열을 무시하지 말고 지원 범위를 명시해야 한다. 지원하지 않는 major schema version은 즉시 거부한다.

---

## 12. 성공 조건과 운영 규칙

`status="succeeded"`가 되려면 다음을 만족해야 한다.

- dossier가 하나 이상 존재한다.
- comparison과 evidence registry가 존재한다.
- 모든 evidence ID 해석률이 100%다.
- locator 해석률이 100%다.
- 모든 critical inventory 항목이 extracted/excluded/unverified 중 하나다.
- 근거 없는 수치 주장이 0개다.
- visual artifact를 참조한다면 crop 파일과 해시가 실제로 존재한다.

운영 시 지켜야 할 규칙은 다음과 같다.

- `run.json`을 검증하기 전에는 dossier를 평가 입력으로 사용하지 않는다.
- 결과 경로보다 `artifact_id`와 SHA-256을 신뢰한다.
- `retrieval_traces.jsonl`을 사실 근거로 사용하지 않는다.
- `confidence`를 실험의 통계적 유의성으로 해석하지 않는다.
- `not_comparable` 수치를 공통 표에서 같은 축의 순위로 만들지 않는다.
- `tested_together=false`인 결합 가설을 검증 완료 기술로 표현하지 않는다.
- `unverified`는 삭제하지 않고 위험 및 추가 조사 항목으로 전달한다.
- 후속 Agent의 가정과 웹 근거는 paper evidence와 별도 namespace로 관리한다.

---

## 13. 현재 성공본 요약

`technical-bge-e2e-20260922-v22`는 다음 상태다.

- 분석 논문: 2편
- RDKV dossier: claims 33개, inventory 31개, experiment observations 9개
- Photonic-CXL dossier: claims 66개, inventory 48개, experiment observations 16개
- evidence registry: paper evidence 191개
- comparison: relationship 1개, 공통 가정 2개, 상이한 가정 3개, matrix cell 16개, metric comparison 1개, integration hypothesis 1개
- evidence 및 locator 해석률: 100%
- unsupported numeric claim: 0
- OpenAI 사용량: input 122,043 tokens, output 6,697 tokens
- 측정 peak RSS: 약 1.75 GiB

현재 `validate-technical` 결과는 `valid=true`지만 다음 미확인 주제 경고가 남아 있다.

- Roman-numeral `Table I` 및 multi-GPU/multi-node·concurrency·production traffic의 일부 system 조건
- 학습 또는 fine-tuning 절차

성공 상태는 확인된 주장들의 근거 계약이 통과했다는 뜻이지, 논문에 존재할 수 있는 모든
질문에 답했다는 뜻은 아니다. 이 경고는 후속 평가에서 정보 부재 또는 추가 검증 과제로
유지해야 한다.

이 성공본은 후속 팀이 intake adapter와 평가 스키마를 개발할 때 사용할 수 있는 기준 fixture다. 다만 결과 내용은 두 논문과 해당 실행의 프롬프트·모델·인덱스 버전에 종속되며, 일반적인 기술 사실 DB 전체를 의미하지는 않는다.

---

## 14. 연동 체크리스트

다른 팀이 자신의 Agent를 연결할 때 다음 순서로 확인한다.

- [ ] `run.json` schema와 `status`를 검사했다.
- [ ] artifact SHA-256을 검사했다.
- [ ] dossier를 `paper_id`로 분리했다.
- [ ] evidence registry를 `evidence_id`로 색인했다.
- [ ] `claim_type` 세 종류를 보존했다.
- [ ] observation 조건과 `evaluation_mode`를 보존했다.
- [ ] `not_comparable`을 강제로 비교하지 않는다.
- [ ] `unverified_items`를 평가 위험에 반영한다.
- [ ] 외부 시장 근거와 paper evidence를 분리한다.
- [ ] 후속 평가 결과에 source claim/observation/evidence ID를 기록한다.
- [ ] 최종 보고서까지 provenance chain이 끊기지 않는다.

이 계약을 지키면 하위 Agent의 구현 주체, 프레임워크, 모델이 달라도 기술조사 결과를 동일한 의미로 소비할 수 있다.
