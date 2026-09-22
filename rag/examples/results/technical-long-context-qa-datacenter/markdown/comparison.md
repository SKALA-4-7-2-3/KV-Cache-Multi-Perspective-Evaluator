# 교차 논문 기술 비교

[전체 요약](README.md) · [근거 레지스트리](evidence_registry.md)

## 기술 관계

### `2605.08317-25836a41` ↔ `2607.27187-d6a67efd`

- 관계: **complementary**
- 함께 검증됨: `false`
- 판단 유형: `analyst_inference`
- 근거: [ev-003](evidence_registry.md#ev-003), [ev-001](evidence_registry.md#ev-001), [ev-172](evidence_registry.md#ev-172), [ev-171](evidence_registry.md#ev-171)
- 설명: 두 논문은 모두 장문맥 LLM의 KV cache가 메모리·대역폭 병목이라는 문제를 다루지만, RDKV는 prefill 뒤 토큰/채널별 bit-width를 배정해 cache 자체의 표현량을 줄이는 알고리즘·커널 계층 방법이고, PF Memory Appliance는 CXL 호환 공유 DDR5 풀의 용량·전송 경로를 확장하는 시스템 계층 방법이다. 따라서 동일 병목의 서로 다른 계층을 다루며, 두 방법을 함께 평가한 결과는 없다.

## 공통 가정

- **양 논문은 장문맥 LLM serving에서 KV cache의 메모리 용량 및 데이터 이동 대역폭이 핵심 병목이라는 전제를 둔다.**
  - 논문: `2605.08317-25836a41`, `2607.27187-d6a67efd`
  - 근거: [ev-004](evidence_registry.md#ev-004), [ev-169](evidence_registry.md#ev-169)

## 상이한 가정

### 개입하는 시스템 경계

- `2605.08317-25836a41`: 고정 bit budget 아래 V cache token과 K cache channel에 {0,2,4,8,16} bit-width를 배정하고, zero-bit eviction과 finite-bit quantization을 하나의 rate–distortion allocation으로 공동 최적화한다. ([ev-003](evidence_registry.md#ev-003), [ev-001](evidence_registry.md#ev-001))
- `2607.27187-d6a67efd`: 32 TB shared DDR5를 최대 16 host에 제공하는 switch-free photonic-CXL memory-disaggregation appliance를 제안하며, host당 128 GB/s를 명시한다. ([ev-172](evidence_registry.md#ev-172), [ev-170](evidence_registry.md#ev-170))
- 영향: RDKV의 압축률·decode kernel 효율과 PF의 풀 용량·원격 접근 특성은 서로 다른 경계의 속성이므로, 한 논문의 수치를 다른 논문의 효과로 치환할 수 없다.

### KV 관리가 적용되는 시간 및 재평가 조건

- `2605.08317-25836a41`: RDKV는 prefill 후 한 번 allocation하며 decoding 중에는 attention-pattern shift에 대해 재평가하지 않는다. ([ev-007](evidence_registry.md#ev-007))
- `2607.27187-d6a67efd`: PF 논문의 repeated-request workflow는 초기 prefill에서 complete KV cache를 생성·저장한 뒤, 후속 동일 요청에서 host memory 또는 SSD로부터 KV cache를 load하여 retrieval 시간을 측정한다. ([ev-172](evidence_registry.md#ev-172), [ev-177](evidence_registry.md#ev-177))
- 영향: 전자는 단일 요청 내부의 prefill-to-decode cache 축소를, 후자는 요청 간 재사용·저장 계층 retrieval을 포함하므로 cache hit 및 generation 중 allocation 변화에 대한 가정이 동일하지 않다.

### 보고된 end-to-end 성능의 평가 단계

- `2605.08317-25836a41`: RDKV의 128K latency·peak-memory 평가는 LLaMA-3.1-8B-Instruct와 단일 A100 64 GB에서 8K–256K context를 대상으로 한 decode 측정이며, 128K prefill TTFT도 별도로 보고된다. ([ev-011](evidence_registry.md#ev-011), [ev-012](evidence_registry.md#ev-012))
- `2607.27187-d6a67efd`: PF Memory Appliance의 end-to-end serving 수치는 multi-turn conversation workload를 LLMServingSim으로 simulation한 projection이며, 물리 appliance에서의 end-to-end inference 검증은 pending으로 명시된다. ([ev-223](evidence_registry.md#ev-223), [ev-212](evidence_registry.md#ev-212))
- 영향: 두 논문의 latency·TTFT 숫자는 측정 단계와 evaluation mode가 달라 직접적인 수치 우열 또는 합산 효과를 도출할 수 없다.

## 비교 매트릭스

| 비교 차원 | 논문 | 내용 | 근거 |
|---|---|---|---|
| 핵심 메커니즘 | `2605.08317-25836a41` | attention-derived token/channel weight를 사용해 per-head MCKP/reverse water-filling으로 혼합 bit-width를 배정하고 TriZone packed cache를 생성한다. | [ev-025](evidence_registry.md#ev-025), [ev-001](evidence_registry.md#ev-001) |
| 핵심 메커니즘 | `2607.27187-d6a67efd` | passive fiber shuffle가 electrical switch를 대체하고, CXL host interface 호환성을 유지한 all-to-all shared-memory connectivity를 제안한다. | [ev-172](evidence_registry.md#ev-172), [ev-171](evidence_registry.md#ev-171) |
| 장문맥 문서 QA 관련 직접 평가 범위 | `2605.08317-25836a41` | LongBench에서 single-document QA와 multi-document QA를 포함한 16개 장문맥 이해 태스크를 평가했고, RULER에서는 4K–128K retrieval·reasoning 11개 subtask를 평가했다. | [ev-014](evidence_registry.md#ev-014), [ev-005](evidence_registry.md#ev-005) |
| 장문맥 문서 QA 관련 직접 평가 범위 | `2607.27187-d6a67efd` | 동일 반복 요청의 100% cache-hit KV retrieval과 multi-turn conversation의 TTFT·prefix-cache hit rate를 평가했으며, legal document analysis는 적용 사례로 언급된다. | [ev-177](evidence_registry.md#ev-177), [ev-223](evidence_registry.md#ev-223), [ev-178](evidence_registry.md#ev-178) |
| 평가 성숙도 | `2605.08317-25836a41` | LongBench·RULER·InfiniteBench의 모델 정확도와 단일 A100 64 GB에서의 decode latency·peak memory를 실측으로 보고한다. | [ev-004](evidence_registry.md#ev-004), [ev-011](evidence_registry.md#ev-011) |
| 평가 성숙도 | `2607.27187-d6a67efd` | CXL pod access latency는 emulation characterization으로, serving 결과는 그 bandwidth·latency 파라미터를 사용한 simulation projection으로 보고하며 물리 appliance의 end-to-end inference 검증은 남아 있다. | [ev-176](evidence_registry.md#ev-176), [ev-212](evidence_registry.md#ev-212) |

## 수치 비교 가능성

### TTFT

- 판정: **not_comparable**
- Observation: `2605.08317-25836a41::technical_overview::eo06`, `2607.27187-d6a67efd::technical_overview::eo_ttft_pf`
- 이유: RDKV는 LLaMA-3.1-8B-Instruct·A100 64 GB·128K context에서 FullKV prefill 대비 TTFT를 실측한 반면, PF는 모델·context·hardware가 명시되지 않은 32 TB appliance의 50–300 multi-turn conversation workload TTFT를 simulation으로 제시한다. baseline, workload, hardware, context length, concurrency 및 evaluation stage/mode가 다르다.

## 결합 가설

### `compressed-kv-on-shared-photonic-cxl`

장문맥 문서 QA serving에서 RDKV로 prefill KV를 압축·TriZone packing한 뒤 PF Memory Appliance의 공유 CXL memory tier에 저장·재사용하면, 동일 KV 표현의 저장 용량과 decode 측 HBM read 부담을 줄이면서 여러 host에 걸친 KV 재사용 범위를 넓힐 가능성이 있다. 이는 두 논문이 함께 실증한 결과가 아닌 분석가 추론이다.

- 판단 유형: `analyst_inference`
- 근거: [ev-003](evidence_registry.md#ev-003), [ev-001](evidence_registry.md#ev-001), [ev-173](evidence_registry.md#ev-173), [ev-222](evidence_registry.md#ev-222)
- 가정:
  - PFMA runtime 또는 connector가 RDKV의 TriZone mixed-bit packed layout을 KV block 단위로 저장·인덱싱·load할 수 있다.
  - 원격 CXL memory에서 읽은 packed KV를 decode attention kernel로 공급하는 경로가 RDKV의 dequantization-fused kernel과 호환된다.
  - 문서 QA 요청에서 prefix 또는 KV reuse가 충분히 발생하며, RDKV의 prefill 시점 정적 allocation이 후속 generation과 재사용 요청에서도 허용 가능한 품질을 유지한다.
- 추가 검증:
  - 동일 모델·문서 QA 데이터·prompt/generation 길이·cache budget에서 RDKV 단독, PF 단독, 결합 구성을 비교하는 end-to-end 실측.
  - 단일 및 다중 host, 동시 요청 수, cache-hit/miss 비율별 TTFT, decode ms/token, p99 latency, HBM·pooled-memory 용량 및 QA 정확도 측정.
  - 원격 load, block indexing/coherency, TriZone dequantization-fused attention을 포함한 실제 connector 경로의 정확성 및 처리량 검증.

## 충돌 및 미확인 항목

### 충돌

- 없음

### 미확인

- **RDKV TriZone mixed-bit KV를 PF Memory Appliance에 저장·재사용하는 결합 경로의 end-to-end 성능과 정확도**: 제공된 자료에서 RDKV는 단일 A100 기반 압축·decode 평가를, PF 논문은 conceptual framework integration과 simulation 기반 serving projection을 각각 제시하지만, 두 기술의 결합 실험은 보고하지 않는다.
  - 시도 횟수: 1
  - 질의: `RDKV PF Memory Appliance combined evaluation`, `TriZone CXL KV connector`, `end-to-end physical PF appliance inference`
