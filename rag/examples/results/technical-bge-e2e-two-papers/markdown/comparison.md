# 교차 논문 기술 비교

[전체 요약](README.md) · [근거 레지스트리](evidence_registry.md)

## 기술 관계

### `2605.08317-25836a41` ↔ `2607.27187-d6a67efd`

- 관계: **complementary**
- 함께 검증됨: `false`
- 판단 유형: `analyst_inference`
- 근거: [ev-002](evidence_registry.md#ev-002), [ev-001](evidence_registry.md#ev-001), [ev-148](evidence_registry.md#ev-148), [ev-142](evidence_registry.md#ev-142)
- 설명: RDKV는 prefill 후 KV를 토큰·채널 단위로 압축·패킹하여 GPU 내 decode의 메모리와 대역폭 부담을 낮추는 소프트웨어/커널 경로이고, PF Memory Appliance는 반복 요청·분리형 prefill/decode에서 KV를 공유 메모리 계층에 보관·전달하는 photonic-CXL 경로이다. 따라서 전자는 저장·전송할 KV의 크기를 줄이고 후자는 그 KV를 host 간 공유·검색하는 시스템 경계를 다루므로, 동일한 KV 계층화 설계에서 조합 가능한 보완 관계로 분류한다. 두 논문은 이 조합을 함께 평가하지 않았다.

## 공통 가정

- **두 논문은 장문맥 LLM 추론에서 KV cache의 메모리 용량·데이터 이동 또는 검색 대역폭이 핵심 병목이라는 전제에서 출발한다. RDKV는 decode마다 HBM에서 KV를 재읽는 memory-bound 추론을, PF Memory Appliance는 TB급 용량과 100 GB/s 초과 대역폭을 동시에 요구하는 KV retrieval을 각각 문제로 둔다.**
  - 논문: `2605.08317-25836a41`, `2607.27187-d6a67efd`
  - 근거: [ev-005](evidence_registry.md#ev-005), [ev-148](evidence_registry.md#ev-148)
- **두 논문은 prefill이 KV를 생성한 뒤 이를 후속 단계에서 다룬다는 실행 경계를 사용한다. RDKV는 prefill 뒤 한 번 allocation·packing을 수행하고, PF Memory Appliance의 반복 요청 절차는 초기 prefill이 complete KV cache를 생성·저장한 뒤 retrieval을 측정한다.**
  - 논문: `2605.08317-25836a41`, `2607.27187-d6a67efd`
  - 근거: [ev-017](evidence_registry.md#ev-017), [ev-143](evidence_registry.md#ev-143)

## 상이한 가정

### 최적화의 시스템 경계와 직접 조작 대상

- `2605.08317-25836a41`: RDKV는 layer-head별 prefill KV cache를 입력으로 하며, V token과 K channel에 {0,2,4,8,16} bit를 할당하고 TriZone packed cache를 출력한다. ([ev-001](evidence_registry.md#ev-001))
- `2607.27187-d6a67efd`: PF Memory Appliance는 CXL load/store semantics를 보존하는 shared-memory interconnect를 대상으로 하며, prefill GPU와 decode GPU의 shared-memory DMA 및 CPU control을 데이터 경로로 제시한다. ([ev-142](evidence_registry.md#ev-142), [ev-186](evidence_registry.md#ev-186))
- 영향: RDKV의 bit allocation 결과를 PFMA가 그대로 저장·검색할 수 있는지, packed layout의 주소 지정·DMA·coherency·dequantization 위치를 별도로 설계·측정해야 하며, 한쪽의 결과를 다른 쪽의 성능 결과로 대체할 수 없다.

### 평가 단계·워크로드·동시성

- `2605.08317-25836a41`: 시스템 측정은 LLaMA-3.1-8B-Instruct, 단일 A100 64 GB, 8K–256K context의 decode latency·peak memory이며, prefill/TTFT는 같은 모델·GPU의 128K context 조건이다. 제공 근거에는 concurrency가 명시되지 않았다. ([ev-012](evidence_registry.md#ev-012), [ev-011](evidence_registry.md#ev-011))
- `2607.27187-d6a67efd`: PFMA의 serving 수치는 emulation-characterized parameter를 사용한 simulation의 50–300 multi-turn conversations 조건이며, physical appliance의 end-to-end inference validation은 pending이다. ([ev-191](evidence_registry.md#ev-191), [ev-144](evidence_registry.md#ev-144))
- 영향: 단일 GPU의 compression/decode 측정과 다중 대화 serving simulation은 평가 단계와 concurrency가 달라 TTFT·throughput·메모리 효과를 직접 수치 비교하거나 합산할 수 없다.

### KV 재사용·갱신 정책

- `2605.08317-25836a41`: RDKV는 prefill 직후 한 번 압축하며 decode 중 allocation을 재평가하지 않아 generation 중 attention-pattern shift에 대해 allocation이 고정된다. ([ev-003](evidence_registry.md#ev-003))
- `2607.27187-d6a67efd`: PFMA는 repeated request에서 initial prefill이 생성·저장한 complete KV cache를 host DRAM 또는 SSD에서 load하는 절차와, CXL의 write-once-read-many KV reuse를 제시한다. ([ev-143](evidence_registry.md#ev-143), [ev-186](evidence_registry.md#ev-186))
- 영향: 공유 KV reuse에서는 RDKV의 prefill 시점 고정 allocation이 반복 요청과 동일한 입력·모델·압축 파라미터에 대해 재사용 가능한지, 그리고 새 decode token을 포함하는 cache의 갱신 정책을 검증해야 한다.

## 비교 매트릭스

| 비교 차원 | 논문 | 내용 | 근거 |
|---|---|---|---|
| 기술 계층·핵심 기법 | `2605.08317-25836a41` | GPU 추론 내부의 KV compression: attention distortion weight와 MCKP reverse water-filling으로 token/channel bit-width를 할당하고, TriZone packed-decode layout에서 dequantization을 attention kernel에 fuse한다. | [ev-002](evidence_registry.md#ev-002), [ev-001](evidence_registry.md#ev-001) |
| 기술 계층·핵심 기법 | `2607.27187-d6a67efd` | 서버/메모리 fabric의 KV pooling: electrical switch 대신 16×16 passive fiber shuffle을 사용해 최대 16 host에 full-mesh CXL shared memory를 제안한다. | [ev-143](evidence_registry.md#ev-143), [ev-187](evidence_registry.md#ev-187) |
| 직접 시스템 근거와 평가 단계 | `2605.08317-25836a41` | LLaMA-3.1-8B-Instruct·단일 A100 64 GB에서 8K–256K decode/peak-memory를 측정했고, 128K prefill/TTFT는 FullKV FA2 baseline 대비 측정했다. | [ev-012](evidence_registry.md#ev-012), [ev-011](evidence_registry.md#ev-011) |
| 직접 시스템 근거와 평가 단계 | `2607.27187-d6a67efd` | KV tier retrieval은 local A100 및 H100/H200 환경에서 측정하고, PF appliance access는 hardware emulation, 32 TB serving 결과는 LLMServingSim simulation으로 제시한다. physical appliance의 end-to-end inference validation은 pending이다. | [ev-143](evidence_registry.md#ev-143), [ev-144](evidence_registry.md#ev-144) |
| RDKV 단일-GPU 정량 결과 | `2605.08317-25836a41` | 128K에서 FullKV FA2 82 ms/token 대비 RDKV는 약 18 ms/token(4.5×)이고, peak memory는 FullKV 58.1 GB 대비 30.5 GB(1.9× reduction)이다. 256K에서 RDKV는 44.5 GB이고 FullKV는 OOM이다. | [ev-006](evidence_registry.md#ev-006), [ev-007](evidence_registry.md#ev-007) |
| RDKV 단일-GPU 정량 결과 | `2607.27187-d6a67efd` | 해당 논문은 RDKV식 GPU 내 mixed-bit compression의 decode latency 또는 peak-memory 측정을 보고하지 않고, KV retrieval tier와 photonic-CXL pool을 다룬다. | [ev-148](evidence_registry.md#ev-148), [ev-187](evidence_registry.md#ev-187) |
| Table I 공통 조건 | `2605.08317-25836a41` | 제공된 근거에는 Roman-numeral Table I의 caption·header·행·cell이 없으므로, 이 논문에 대해 Table I 조건을 복원할 수 없다. 단, 별도 LongBench 평가는 Btotal 64L–1024L이고 Qwen2.5-72B-Instruct는 2-GPU tensor parallelism으로 평가했다. | [ev-137](evidence_registry.md#ev-137) |
| Table I 공통 조건 | `2607.27187-d6a67efd` | Repeated Request Benchmark의 모든 configuration은 batch sizes {1, 2, 8, 16, 32}; standard context는 1K–100K tokens, Maverick은 최대 1M, Scout은 최대 4M tokens이다. 100% cache-hit identical repeated request에서 full KV re-computation 대비 host-memory 또는 SSD retrieval speedup을 측정한다. | [ev-184](evidence_registry.md#ev-184), [ev-148](evidence_registry.md#ev-148) |
| Table I 조건별 범위 — LLaMA-8B·1×A100 | `2607.27187-d6a67efd` | Host Memory speedup은 3.3×–27.5×, Disk Storage speedup은 0.53×–1.72×이다. | [ev-154](evidence_registry.md#ev-154), [ev-155](evidence_registry.md#ev-155), [ev-156](evidence_registry.md#ev-156), [ev-157](evidence_registry.md#ev-157) |
| Table I 조건별 범위 — LLaMA-8B·1×H100 | `2607.27187-d6a67efd` | Host Memory speedup은 1.9×–11.8×이고 Disk Storage는 —이다. | [ev-158](evidence_registry.md#ev-158), [ev-159](evidence_registry.md#ev-159), [ev-160](evidence_registry.md#ev-160), [ev-161](evidence_registry.md#ev-161) |
| Table I 조건별 범위 — LLaMA-8B·1×H200 | `2607.27187-d6a67efd` | Host Memory speedup은 1.5×–17.2×, Disk Storage speedup은 0.38×–1.27×이다. | [ev-162](evidence_registry.md#ev-162), [ev-163](evidence_registry.md#ev-163), [ev-164](evidence_registry.md#ev-164), [ev-165](evidence_registry.md#ev-165) |
| Table I 조건별 범위 — LLaMA-70B·2×H200 | `2607.27187-d6a67efd` | Host Memory speedup은 2.7×–51.4×이고 Disk Storage는 —이다. | [ev-166](evidence_registry.md#ev-166), [ev-167](evidence_registry.md#ev-167), [ev-168](evidence_registry.md#ev-168), [ev-169](evidence_registry.md#ev-169) |
| Table I 조건별 범위 — LLaMA-405B·8×H200 | `2607.27187-d6a67efd` | Host Memory speedup은 2.7×–100.0×, Disk Storage speedup은 2.1×–9.7×이다. | [ev-170](evidence_registry.md#ev-170), [ev-171](evidence_registry.md#ev-171), [ev-172](evidence_registry.md#ev-172), [ev-173](evidence_registry.md#ev-173) |
| Table I 조건별 범위 — Maverick·8×H200 | `2607.27187-d6a67efd` | Host Memory speedup은 2.7×–23.1×이고 Disk Storage는 —이다. 이 행의 context 범위는 최대 1M tokens이다. | [ev-174](evidence_registry.md#ev-174), [ev-175](evidence_registry.md#ev-175), [ev-176](evidence_registry.md#ev-176), [ev-177](evidence_registry.md#ev-177), [ev-184](evidence_registry.md#ev-184) |
| Table I 조건별 범위 — Scout·8×H200 | `2607.27187-d6a67efd` | Host Memory speedup은 2.6×–54.6×이고 Disk Storage는 —이다. 이 행의 context 범위는 최대 4M tokens이다. | [ev-178](evidence_registry.md#ev-178), [ev-179](evidence_registry.md#ev-179), [ev-180](evidence_registry.md#ev-180), [ev-181](evidence_registry.md#ev-181), [ev-184](evidence_registry.md#ev-184) |
| PFMA latency·serving 수치 | `2607.27187-d6a67efd` | Emulation에서 average 64-byte memory-pool-to-host access는 350 ns이다. Simulation의 32 TB appliance는 50–300 multi-turn conversations에서 mean TTFT 2,690 ms와 prefix-cache hit rate 82%를, 300 conversations에서 2 TB baseline 대비 6.6× TTFT gap을 제시한다. | [ev-146](evidence_registry.md#ev-146), [ev-191](evidence_registry.md#ev-191) |

## 수치 비교 가능성

### TTFT

- 판정: **not_comparable**
- Observation: `2605.08317-25836a41::technical_overview::to-o04`, `2607.27187-d6a67efd::technical_overview::to-o12`
- 이유: RDKV는 LLaMA-3.1-8B-Instruct·A100 64 GB·128K prefill의 단일-GPU 측정 TTFT(30,583 ms)이고 concurrency가 명시되지 않았다. PFMA는 모델·하드웨어·context가 명시되지 않은 32 TB appliance의 50–300 multi-turn conversations serving simulation TTFT(2,690 ms)이다. 모델, 하드웨어, workload, context, concurrency, 시스템 경계, evaluation stage가 모두 다르다.

## 결합 가설

### `compressed-kv-over-photonic-cxl-pool`

분석자 추론: RDKV로 prefill 직후 생성한 TriZone packed KV를 PFMA의 CXL shared-memory pool에 저장하고 decode host가 이를 DMA로 읽는 구성은, PFMA가 운반·보존해야 하는 KV 용량을 줄이면서 RDKV의 GPU-side packed decode를 유지할 가능성이 있다. 이는 두 논문에서 별도로 제시된 구성의 결합 가설이며 공동 실험 결과가 아니다.

- 판단 유형: `analyst_inference`
- 근거: [ev-001](evidence_registry.md#ev-001), [ev-002](evidence_registry.md#ev-002), [ev-186](evidence_registry.md#ev-186), [ev-187](evidence_registry.md#ev-187)
- 가정:
  - TriZone packed KV의 block layout과 metadata가 PFMA runtime의 KV block indexing·allocator 및 CXL DMA addressability와 양립한다.
  - RDKV의 bit allocation·packing 비용을 포함해도 repeated-request 또는 disaggregated prefill/decode 경로에서 end-to-end TTFT 또는 decode latency 목표가 유지된다.
  - 압축된 KV를 여러 host가 reuse할 때 allocator, index, rendezvous coherency, eviction manager가 packed representation의 lifecycle을 정확히 관리한다.
- 추가 검증:
  - 동일 모델·동일 context·동일 batch/concurrency에서 FullKV+PFMA, RDKV+local memory, RDKV+PFMA를 비교하는 physical end-to-end 실험
  - prefill compression 시간, CXL DMA/retrieval 시간, dequantization-fused attention 시간, TTFT, per-token decode latency, peak memory, prefix-hit rate를 분리 계측
  - single-host 및 multi-host prefill/decode, repeated-request hit/miss, generation 중 cache growth와 RDKV allocation 고정 조건에서 correctness·coherency·tail-latency를 검증

## 충돌 및 미확인 항목

### 충돌

- 없음

### 미확인

- **RDKV 논문의 Roman-numeral Table I 조건별 범위**: 제공된 RDKV 근거에는 Roman-numeral Table I의 caption, header, model/platform 행 또는 cell이 없어 PFMA 논문의 Table I과 대응시키거나 조건별 수치를 보존할 수 없다.
  - 시도 횟수: 1
  - 질의: `Table I`, `Roman-numeral Table I`, `system testing matrix`
- **RDKV와 PF Memory Appliance의 결합 성능**: 제공된 근거에서 RDKV TriZone packed cache를 PFMA shared memory에 저장하고 multi-host decode로 검색한 공동 end-to-end 측정을 확인할 수 없다. PFMA 논문도 physical appliance의 end-to-end inference validation이 pending이라고 명시한다.
  - 시도 횟수: 1
  - 질의: `RDKV PF Memory Appliance`, `TriZone CXL shared memory`, `physical end-to-end inference`
