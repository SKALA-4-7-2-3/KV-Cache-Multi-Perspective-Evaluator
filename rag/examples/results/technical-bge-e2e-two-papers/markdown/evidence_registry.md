# 근거 레지스트리

[전체 요약](README.md) · [교차 비교](comparison.md)

> 각 근거는 논문 페이지·절·요소·표 셀 또는 Vision crop으로 역추적할 수 있습니다.

## 문서별 근거 수

| 문서 | 근거 수 |
|---|---:|
| `2605.08317-25836a41` | 139 |
| `2607.27187-d6a67efd` | 52 |

## 근거 목록

<a id="ev-001"></a>
### ev-001 — `2605.08317-25836a41` p.17

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0017:elem-2605.08317-25836a41-p0017-text-group-048-a30ce8c83abc:span-00000-01474` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `17` / `17` |
| 절 | Conclusion |
| Object | `elem-2605.08317-25836a41-p0017-text-group-048-a30ce8c83abc` |
| 원본 element | `elem-2605.08317-25836a41-p0017-text-group-048-a30ce8c83abc` |
| Text span | `0:1474` |
| Table cell | - |
| BBox | `107.64, 74.01, 505.65, 552.48` |
| Content SHA-256 | `3db1b04acb748730e5c42f07438fdcafc092cb99a6ed7c6737d8f9cc9d268baa` |

<details>
<summary>원문 스니펫 보기</summary>

> Algorithm 1 RDKV: Rate-Distortion KV Cache Compression
>
> Require: Prefill KV cache K(ℓ), V (ℓ) for each layer ℓ; per-head budget Bhead; observation win-
>
> dow size Sw; pooling kernel w; bit-width set B = {0, 2, 4, 8, 16}; empirical distortion tables
> εK(b), εV (b)
> Ensure: TriZone packed cache for each (ℓ, h)
>
> 1: for each layer ℓ= 1, . . . , L do
> 2:
> // Stage 1: Weight computation
>
> √
>
> Q(ℓ)
>
> [τ−Sw:τ] K(ℓ)⊤/
>
> 
>
> 3:
> A ←Softmax
>
> d
>
> 4:
> for each KV head h = 1, . . . , Hkv do
>
> 5:
> w(h)
>
> τ,g a(h)
>
> t
> ←P
>
> τ,g,t for all t
> ▷token weight in V cache
>
> 6:
> w(h)
>
> t
> ←AvgPool1d(w(h)
>
> t
> , w)
>
> 7:
> w(h)
>
> d ∥Q(h)
>
> :,c ∥2 · ∥K(h)
>
> c
> ←
> 1
> √
>
> :,c ∥2 for all c
> ▷channel weight in K cache
>
> 8:
> end for
>
> 9:
> // Stage 2: V-side token allocation (per head)
> 10:
> BV ←1
>
> 2Bhead;
> ¯BV ←BV /d
> 11:
> for each KV head h do
> 12:
> {bV
>
> t
> , εV , ¯BV /T)
>
> t }h ←MCKP(w(h)
>
> 13:
> T (h)
>
> kept ←{t : bV
>
> t > 0}
>
> 14:
> end for
>
> 15:
> // Stage 3: K-side channel allocation (per head)
> 16:
> BK ←1
>
> 2Bhead
> 17:
> for each KV head h do
> 18:
> k(h)
>
> avg ←BK /
>
> |T (h)
>
> 
>
> kept | · d
>
> c }h ←MCKP(w(h)
>
> c
> , εK, k(h)
>
> 19:
> {bK
>
> avg )
> 20:
> end for
>
> 21:
> // Stage 4: TriZone packing
> 22:
> for each KV head h do
> 23:
> Sort T (h)
>
> kept by bV
>
> t into sub-segments S2, S4, S8
>
> 24:
> Sort channels by bK
>
> c into segments; permute q to match
> 25:
> Quantize and byte-pack V sub-segments →Zone A (V)
>
> 26:
> Quantize and byte-pack K rows of T (h)
>
> kept →Zone A (K)
>
> 27:
> Store {t : bV
>
> t = 16} V rows in FP16 →Zone B
> 28:
> end for
> 29: end for
>
> E
> Additional Experiments on RULER

</details>

<a id="ev-002"></a>
### ev-002 — `2605.08317-25836a41` p.2

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0002:elem-2605.08317-25836a41-p0002-text-group-004-eec11153f56c:span-00000-02241` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `2` / `2` |
| 절 | Introduction |
| Object | `elem-2605.08317-25836a41-p0002-text-group-004-eec11153f56c` |
| 원본 element | `elem-2605.08317-25836a41-p0002-text-group-004-eec11153f56c` |
| Text span | `0:2241` |
| Table cell | - |
| BBox | `107.53, 201.69, 505.75, 540.39` |
| Content SHA-256 | `65db5418130c405737d49ca0fef7dafe90cf425de3278b19e6d086d8e9136af0` |

<details>
<summary>원문 스니펫 보기</summary>

> u wu εu(bu) ( Eq. (6)) versus average
> bit-width ¯b. Lines: median across sequences; shaded: IQR. Lower bound: continuous relaxation
> (Prop. A.3). Right: LongBench score by task category at a per-layer cache budget of 128 FP16-
> equivalent tokens (Btotal = 128L), normalized by FullKV; per-task scores in Tab. 1. Eviction refers
> to Ada-SnapKV [26] in the right panel. Model: LLaMA-3.1-8B-Instruct [42].
>
> and evicted states [16, 17]. But their routing scores remain heuristic and the budget ratios are preset or
> searched before the final assignment. A natural question is whether both the score and the allocation
> can be derived from a single objective function.
>
> In this paper, we present RDKV, a rate–distortion framework for KV cache compression. RDKV
> poses a bit-allocation problem: given a fixed bit budget, assign each token in the V cache and each
> channel in the K cache a bit-width to minimize a weighted distortion. The weight of each token
> or channel is defined as the deviation in the attention distribution or the attention logit when it is
> evicted. Reverse water-filling converts these weights into bit-widths, from full precision for critical
> units down to zero bits (eviction) for negligible ones. Eviction and quantization are thus at the two
> ends of one allocation curve, and are explored jointly rather than in a staged fashion.
>
> We make three contributions. (1) We formulate KV cache compression as a rate–distortion problem.
> The continuous optimum inherently mixes zero-rate (eviction) and finite-rate (quantization) units.
> Therefore, approximating this bound requires both actions in the same solver, while restricting
> to either alone leaves a clear gap, as Fig. 1 (left) shows on calibration data. (2) We instantiate
> the allocation as a discrete knapsack over hardware-supported bit-widths and solve it via reverse
> water-filling with Lagrangian relaxation. (3) We realize the resulting mixed-bit cache with TriZone,
> a packed-decode layout that fuses dequantization into the attention kernel, turning the mixed-bit
> allocation into actual memory savings. Taken together, Fig. 1 (right) shows the empirical picture:
> RDKV approaches FullKV’s performance across all six categories while the strong baseline lags
> consistently.
>
> 2

</details>

<a id="ev-003"></a>
### ev-003 — `2605.08317-25836a41` p.28

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0028:elem-2605.08317-25836a41-p0028-text-group-098-16f3c2fdb454:span-00000-02393` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `28` / `28` |
| 절 | RB-P |
| Object | `elem-2605.08317-25836a41-p0028-text-group-098-16f3c2fdb454` |
| 원본 element | `elem-2605.08317-25836a41-p0028-text-group-098-16f3c2fdb454` |
| Text span | `0:2393` |
| Table cell | - |
| BBox | `108.00, 241.52, 505.65, 752.30` |
| Content SHA-256 | `114a6a8de99f1fd63752e9e079f062907637b4592f1018ed844eab9c808302ed` |

<details>
<summary>원문 스니펫 보기</summary>

> εK(b) (per-channel)
> εV (b) (per-token)
>
> Model
> b=2
> b=4
> b=8
> b=2
> b=4
> b=8
>
> LLaMA-3.1-8B
> 0.149
> 0.0062
> 2.2×10−5
> 0.313
> 0.0140
> 4.9×10−5
>
> LLaMA-2-13B
> 0.288
> 0.0124
> 5.5×10−5
> 0.272
> 0.0122
> 4.4×10−5
>
> Mistral-7B
> 0.280
> 0.0116
> 6.9×10−5
> 0.296
> 0.0130
> 4.5×10−5
>
> Qwen2.5-72B
> 0.296
> 0.0164
> 4.4×10−3
> 0.281
> 0.0126
> 4.4×10−5
>
> Qwen3-4B
> 0.347
> 0.0147
> 1.5×10−4
> 0.313
> 0.0139
> 4.8×10−5
>
> K
> Limitations and Future Work
>
> Limitations. Like SnapKV, AdaKV, and PyramidKV, RDKV compresses the KV cache once after
> prefill and does not re-evaluate during decoding. This is a common design choice in the prefill-
> dominated regime (long prompt, short generation) targeted by these methods. The allocation is
> therefore frozen with respect to attention-pattern shifts that may occur during generation.
>
> Future work. The rate-distortion framework can be extended to the decode phase. A natural approach
> accumulates attention weights over a small buffer of recent decode tokens and periodically applies the
> same MCKP allocation to compress them, keeping decode-phase memory sub-linear in the number
> of generated tokens relative to the uncompressed baseline.
>
> L
> Impact Statement
>
> RDKV reduces the memory footprint and decoding latency of long-context LLM inference without
> modifying model weights or training procedures. On the positive side, lower hardware requirements
> enable longer context windows on smaller GPUs, reducing both the financial cost and the energy
> consumption of serving long-context applications such as document summarization, multi-document
> QA, and retrieval-augmented generation. This may broaden access to long-context LLM capabilities
> for resource-constrained practitioners and organizations. More broadly, by reducing the number of
> GPU hours required per query, RDKV lowers the energy consumption and carbon footprint of LLM
> serving, contributing to more environmentally sustainable deployment of long-context inference. On
> the negative side, as with any inference acceleration technique, reduced serving cost could lower the
> barrier to deploying LLMs at scale, potentially amplifying existing concerns associated with large-
> scale LLM deployment such as misinformation generation. However, RDKV does not introduce new
> model capabilities—it preserves the output distribution of the original model within the compression
> budget—and therefore does not create risks beyond those already present in the underlying LLM.
>
> 28

</details>

<a id="ev-004"></a>
### ev-004 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:elem-2605.08317-25836a41-p0023-text-group-083-eb14d2d10f23:span-00000-01125` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV TTFT |
| Object | `elem-2605.08317-25836a41-p0023-text-group-083-eb14d2d10f23` |
| 원본 element | `elem-2605.08317-25836a41-p0023-text-group-083-eb14d2d10f23` |
| Text span | `0:1125` |
| Table cell | - |
| BBox | `107.67, 512.73, 505.65, 752.30` |
| Content SHA-256 | `de2451a5414e9a6a6e5134479af2892caedddea9010b74c70bd4c2584a99b9a7` |

<details>
<summary>원문 스니펫 보기</summary>

> 30 583
> 106.0%
>
> I
> Visualization of Bit Allocation
>
> To illustrate how the RDKV allocator distributes bit-widths across tokens and channels, we visualize
> the per-unit distortion weight wt (V cache, Prop. 3.1) and wc (K cache, Prop. 3.2) together with the
> resulting bit-width assignment b ∈{0, 2, 4, 8, 16} on a representative LongBench sample (LLaMA-
> 3.1-8B-Instruct, Btotal = 128L). Each dot is coloured by its assigned bit-width: • 16-bit, • 8-bit,
> • 4-bit, • 2-bit; tokens assigned 0 bits (evicted) are omitted. We show layers 15 (middle) and 31
> (final) with two KV heads each.
>
> Token-level V allocation (Fig. 7–Fig. 13).
> The score distribution spans roughly six orders of
> magnitude. Sink tokens (position 0) and recent tokens near the sequence tail consistently receive the
> highest scores and correspondingly 16-bit or 8-bit retention—the former carry accumulated attention
> mass, and the latter fall within the observation window. The bulk of mid-sequence tokens reside at
> 2–4 bits. Head 0 and head 1 share the global profile but differ in which mid-sequence positions spike,
> reflecting head-specific attention patterns.
>
> 23

</details>

<a id="ev-005"></a>
### ev-005 — `2605.08317-25836a41` p.1

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0001:elem-2605.08317-25836a41-p0001-text-group-001-0aed8c4b9eb2:span-00000-01494` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `1` / `1` |
| 절 | Abstract |
| Object | `elem-2605.08317-25836a41-p0001-text-group-001-0aed8c4b9eb2` |
| 원본 element | `elem-2605.08317-25836a41-p0001-text-group-001-0aed8c4b9eb2` |
| Text span | `0:1494` |
| Table cell | - |
| BBox | `108.00, 261.63, 469.88, 501.60` |
| Content SHA-256 | `5887e822c951db7b496bc082a75cf94ce77dfc519998b10e32cfda36ac37cd1f` |

<details>
<summary>원문 스니펫 보기</summary>

> Large language models (LLMs) have shown strong performance across diverse
> tasks, but their inference with long input contexts is bottlenecked by memory size
> and bandwidth. The Key-Value (KV) cache size grows linearly with sequence
> length and needs to be re-read from off-chip high-bandwidth memory (HBM) to
> on-chip memory at every decoding step, resulting in memory-bound inference.
> Existing methods reduce the cache by either eviction or quantization, but typically
> treat the two in isolation. In this paper, we cast KV cache compression as a rate-
> distortion problem, under which eviction and quantization are two end-points of
> the same bit allocation scheme. This exposes the need to optimize them jointly,
> motivating our method, RDKV (Rate-Distortion KV cache compression). RDKV
> derives the weight of each token or channel from the distortion that compression
> induces on the attention computation. Based on these weights, it assigns each token
> or channel a bit-width ranging from full precision down to zero bits guided by
> reverse water-filling, applied once after the prefilling stage. Experiments on Long-
> Bench, RULER, and InfiniteBench show that RDKV outperforms the best evaluated
> baseline by 9.1% on average. On LongBench it recovers 97.81% of full-cache accu-
> racy with only 2.48% cache retention. Compared with full-cache FlashAttention-2
> decoding, it achieves 4.5× decode speedup and 1.9× peak memory reduction with
> 128K context length, while maintaining comparable performance.
>
> 1

</details>

<a id="ev-006"></a>
### ev-006 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:elem-2605.08317-25836a41-p0008-text-group-029-cd466779016b:span-00000-02127` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0008-text-group-029-cd466779016b` |
| 원본 element | `elem-2605.08317-25836a41-p0008-text-group-029-cd466779016b` |
| Text span | `0:2127` |
| Table cell | - |
| BBox | `108.00, 374.35, 505.74, 752.30` |
| Content SHA-256 | `6b8bb226ff51c057940c77d087f951be29e6817718dd686fb82cbf9347db27df` |

<details>
<summary>원문 스니펫 보기</summary>

> SnapKV[11]
> 37.91
> AdaKV[26]
> 38.06
> ThinK[12]
> 36.73
> Snap+Zip
> 37.76
>
> 98.62 98.61 95.65 88.28 80.07 66.95
>
> 39.46
>
> and AdaKV [26] develop failure bands at intermediate depths where the needle falls below the top-k
> threshold and is evicted entirely. RDKV assigns the same token a low bit-width instead of discarding
> it. A 2- or 4-bit copy suffices to recover the answer. RDKV (avg. 0.99) thus maintains near-uniform
> retrieval close to FullKV (1.00). Further results are in Sec. F.
>
> RULER. RULER [49] evaluates retrieval and reasoning at extreme context lengths, averaging 11
> subtasks at sequence lengths from 4k to 128k. Table 2 reports results on LLaMA-3.1-8B-Instruct
> under Btotal = 1024L. Eviction-only baselines degrade substantially as context grows, falling over 6
> points below FullKV even at 4k and 17 points at 128k. RDKV stays within 1 point of FullKV up to
> 8k and leads the strongest baseline by 4.1–14.2 points across all lengths, because tokens that a top-k
> policy would discard are instead retained at low bit-width. Per-task breakdowns are in Sec. E.
>
> InfiniteBench. InfiniteBench [50] spans 10 tasks with sequences exceeding 100k tokens (average
> ∼200k; the longest task, Zh.QA, reaches ∼2M tokens). Table 3 reports results on LLaMA-3.1-8B-
> Instruct under Btotal = 1024L. RDKV ranks first among compression methods, ahead of AdaKV
> by 1.40 and SnapKV by 1.55 points, confirming that the allocation advantage persists at ultra-long
> contexts well beyond the lengths covered by LongBench and RULER. Per-task results are in Sec. G.
>
> 4.2
> Memory and Latency
>
> Latency. Fig. 5 reports decode latency, peak memory, and the latency-accuracy trade-off on LLaMA-
> 3.1-8B-Instruct from 8K to 256K on a single A100 64 GB. Both FullKV and AdaKV [26] use
> FA2 [51]; reporting FullKV under SDPA would inflate RDKV’s relative speedup to roughly 13×.
> FullKV per-token decode latency grows from 26 ms at 8K to 82 ms at 128K, while RDKV stays flat
> at ∼18 ms, a 4.5× speedup at 128K (Fig. 5a), since TriZone’s packed cache size is fixed by Btotal
> rather than by T. AdaKV is also at ∼25 ms under the same token budget, but RDKV is 1.4× faster.
>
> 8

</details>

<a id="ev-007"></a>
### ev-007 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:elem-2605.08317-25836a41-p0009-text-group-031-baa0e3a046d9:span-00000-01154` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0009-text-group-031-baa0e3a046d9` |
| 원본 element | `elem-2605.08317-25836a41-p0009-text-group-031-baa0e3a046d9` |
| Text span | `0:1154` |
| Table cell | - |
| BBox | `107.67, 234.26, 505.75, 446.81` |
| Content SHA-256 | `b8195dec3ff64cf5fffb3f2f2d457d05d2f8a73a42b7984a6301ea26d4ea405c` |

<details>
<summary>원문 스니펫 보기</summary>

> Memory. FullKV peak memory grows linearly to 58.1 GB at 128K (Fig. 5b) and OOMs at 256K.
> RDKV uses 30.5 GB at 128K (1.9× reduction vs. FullKV) and 44.5 GB at 256K, running on the
> same device where FullKV cannot.
>
> Latency-Accuracy Trade-off. Fig. 5c plots latency against RULER accuracy at each context length.
> RDKV and AdaKV operate at comparable latency, but RDKV is more accurate at every context
> length: at 128K the gap is 8.5 points (67.0 vs. 58.4). RDKV thus sits strictly above AdaKV on the
> latency–accuracy Pareto front.
>
> 4.3
> Ablation Studies
>
> Action Space.
> We compare four bit-width sets under the same
> distortion weights and water-filling allocator (Tab. 4, LLaMA-3.1-
> 8B-Instruct, Btotal = 128L and 512L). Removing eviction (Quant-
> only) costs 8.4 / 8.6 points: the allocator must spend bits on every
> token, diluting precision for the critical few. Removing quantization
> (Evict-only) costs 4.9 / 2 points: moderate-importance tokens are
> discarded entirely when a 2- or 4-bit copy would suffice. Tri-state
> ({0, 4, 16}) closes most of the gap (0.5 / 0.2), confirming that mixing
> eviction with quantization matters more than bit-width granularity.

</details>

<a id="ev-008"></a>
### ev-008 — `2605.08317-25836a41` p.7

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0007:elem-2605.08317-25836a41-p0007-text-group-026-3eb0ccfc8644:span-00000-02344` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `7` / `7` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0007-text-group-026-3eb0ccfc8644` |
| 원본 element | `elem-2605.08317-25836a41-p0007-text-group-026-3eb0ccfc8644` |
| Text span | `0:2344` |
| Table cell | - |
| BBox | `107.64, 405.80, 505.66, 752.30` |
| Content SHA-256 | `300f235d311a2ab807321e162ca644cb8e4af5199b5055b4a863eeee10694c21` |

<details>
<summary>원문 스니펫 보기</summary>

> LLaMA-3.1-8B-Instruct, Btotal = 1024L
>
> SnapKV[11] 29.51
> 43.17 56.26
> 57.43
> 49.18
> 32.07
> 27.21
> 24.63
> 25.26
> 69.50
> 91.70
> 42.28
> 8.15 100.00 64.71 58.52 48.72
> AdaKV[26]
> 29.76
> 43.39 55.82
> 57.62
> 48.31
> 32.35
> 27.22
> 24.75
> 25.18
> 72.00
> 91.78
> 42.12
> 8.15 100.00 64.56 58.37 48.84
> ThinK[12]
> 27.34
> 42.48 55.59
> 57.78
> 49.17
> 32.36
> 28.23
> 24.82
> 25.85
> 71.50
> 92.50
> 42.25
> 8.27 100.00 64.44 58.52 48.82
> Snap+Zip
> 30.23
> 40.65 54.13
> 56.06
> 46.23
> 31.45
> 22.84
> 24.50
> 24.28
> 69.00
> 91.76
> 44.15
> 8.61
> 99.00 60.90 56.38 47.51
>
> 30.41
> 44.54 55.82
> 57.14
> 49.25
> 31.77
> 33.14
> 25.19
> 26.92
> 72.00
> 91.84
> 43.90
> 9.08 100.00 63.56 57.01 49.47
>
> Evaluation Protocol. All methods are evaluated under matched per-layer cache budgets Btotal = nL
> with n ∈{64, 128, 256, 512, 1024}. For RDKV, n is the FP16-equivalent token count reallocated
> across tokens (V) and channels (K) at bit-widths B = {0, 2, 4, 8, 16}. All score-based methods share
> the same size of observation window and pooling kernel. Further details in Sec. B.
>
> 4.1
> Main Results
>
> LongBench. LongBench [47] evaluates long-context understanding across 16 tasks spanning
> single/multi-document QA, summarization, few-shot learning, synthetic, and code. Table 1 re-
> ports per-task scores for LLaMA-3.1-8B-Instruct [42] across five cache budgets. RDKV achieves the
> highest average at every budget: at Btotal = 1024L it reaches 49.47, within 0.35 points of FullKV;
> at 64L the lead over the strongest baseline widens to 2.7 points. This reflects a structural advan-
> tage of joint allocation. Binary baselines discard every token below the top-k threshold. RDKV
> instead chooses from a larger action space via reverse water-filling, assigning borderline tokens a low
> bit-width rather than evicting them. SnapKV+ZipCache [11, 14] also quantizes, but treats eviction
> and quantization as separate stages rather than two ends of one allocation curve. The advantage
> spans all six categories; the largest per-task gain appears on GovRep (3–5 points), where attention
> dispersed across lengthy documents favors mixed-precision over binary eviction. Cross-model results
> (Mistral-7B [43], Qwen3-4B [44], LLaMA-2-13B [45], Qwen2.5-72B [46]) are in Sec. D.
>
> Needle-In-A-Haystack. Needle-in-a-Haystack [48] tests single-fact retrieval by inserting a target fact
> at varying depths. Figure 4 compares methods under Btotal = 64L at 32k context length. SnapKV [11]
>
> 7

</details>

<a id="ev-009"></a>
### ev-009 — `2605.08317-25836a41` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0005:figure-02:span-00000-00120` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | MCKP |
| Object | `Figure 2` |
| 원본 element | `elem-2605.08317-25836a41-p0005-caption-033-c0510a4c9d05` |
| Text span | `0:120` |
| Table cell | - |
| BBox | `107.25, 272.14, 504.00, 300.11` |
| Content SHA-256 | `5984f430022ca2a6a5b3e4108362c58c173380ace9284abaa6f445db4f495c81` |

<details>
<summary>원문 스니펫 보기</summary>

> Figure 2: RDKV per-head bit-allocation pipeline (illustrated for 8 tokens and 8 channels). Stage
> 1. Token weights wt = P

</details>

<a id="ev-010"></a>
### ev-010 — `2605.08317-25836a41` p.18

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0018:elem-2605.08317-25836a41-p0018-text-group-050-db7f410d23e8:span-00000-02231` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `18` / `18` |
| 절 | Conclusion |
| Object | `elem-2605.08317-25836a41-p0018-text-group-050-db7f410d23e8` |
| 원본 element | `elem-2605.08317-25836a41-p0018-text-group-050-db7f410d23e8` |
| Text span | `0:2231` |
| Table cell | - |
| BBox | `106.07, 74.01, 505.99, 570.73` |
| Content SHA-256 | `201e1477bd6b72b450947f8d00bd55403c14535e2adf27c69547fa38b6fa5887` |

<details>
<summary>원문 스니펫 보기</summary>

> Algorithm 2 MCKP: Lagrangian Bisection Knapsack Solver
>
> Require: Weights {wu}; distortion table ε(b); target average bits ¯b; bit-width set B; tolerance δ;
>
> max iterations I
> Ensure: Bit-width assignment {b⋆
>
> u}
> 1: λlo ←0;
> λhi ←maxu wu
> 2: for i = 1, . . . , I do
> 3:
> λ ←(λlo + λhi)/2
> 4:
> for each unit u do
> 5:
> b⋆
>
> u ←arg minb∈B wu ε(b) + λ b
> 6:
> end for
> 7:
> ¯bcur ←mean({b⋆
>
> u})
> 8:
> if |¯bcur −¯b|/¯b < δ then
> 9:
> return {b⋆
>
> u}
> 10:
> else if ¯bcur > ¯b then
> 11:
> λlo ←λ
> 12:
> else
> 13:
> λhi ←λ
> 14:
> end if
> 15: end for
> 16: return {b⋆
> u}
>
> As reported in Tab. 9, RDKV consistently achieves the highest average accuracy across all context
> lengths. At 4k tokens, RDKV matches FullKV (98.59 vs. 98.58), while the best eviction baseline
> (ThinK) reaches 98.11. As context length increases, the gap widens: at 64k, RDKV leads with 83.20
> vs. 78.73 for the next best method (AdaKV), a 4.5-point margin. A breakdown by task category
> clarifies the source of the advantage. On S-NIAH-3—the hardest single-needle retrieval variant—
> RDKV is the only method that stays above 99% from 4k through 64k; SnapKV and AdaKV drop
> to 89.80/92.60 at 64k and to 50.80/47.80 at 128k, whereas RDKV still reaches 99.80 and 93.80,
> respectively. The CWE aggregation task at 16k illustrates a complementary advantage: eviction
> discards low-attention tokens that carry the frequency signal, yielding 46–55 for the baselines; RDKV
> retains these tokens at low bit-width and scores 77.26, a 22-point improvement over the next best
> method.
>
> Comparison with HqeKV.
> HqeKV [17] is a concurrent method that also combines eviction and
> quantization, but fixes the tier ratios rather than deriving them from a single allocation curve. Table 10
> compares RDKV and HqeKV on the 11 RULER tasks at Btotal = 1024L across three context lengths
> (16k, 32k, 64k) on LLaMA-3.1-8B-Instruct. RDKV leads at every context length, with the gap
> widening from +1.8 points at 32k to +5.3 at 16k and +5.0 at 64k. The advantage is concentrated
> on tasks where the allocation granularity matters most: on CWE, RDKV leads by +49.9 / +22.0
> / +6.5 points across the three lengths; on MV-NIAH, by +3.4 / +7.4 / +12.1; on MQ-NIAH, by
> +2.7 / +5.3 / +12.2. HqeKV outperforms RDKV on FWE at 32k and 64k and on MK-NIAH-3 at

</details>

<a id="ev-011"></a>
### ev-011 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:span-00000-00164` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-2605.08317-25836a41-p0023-caption-017-17052be1176e` |
| Text span | `0:164` |
| Table cell | - |
| BBox | `107.67, 390.12, 504.00, 411.22` |
| Content SHA-256 | `28484a9e372d7d56359ee4464cfcd502b4de87de15fe172d71c9605d2c5130de` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12: Prefill overhead breakdown for RDKV on LLaMA-3.1-8B-Instruct at 128K context length
> (A100 64 GB). Percentages are relative to the FullKV prefill baseline.

</details>

<a id="ev-012"></a>
### ev-012 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:figure-05:span-00000-00181` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Figure 5` |
| 원본 element | `elem-2605.08317-25836a41-p0009-caption-033-b9ce61eea96a` |
| Text span | `0:181` |
| Table cell | - |
| BBox | `108.00, 191.73, 504.00, 212.58` |
| Content SHA-256 | `718dc2ba3489bccef5b29a06b455c7032c9cb71d960ce95dccabdfa4908ac1c7` |

<details>
<summary>원문 스니펫 보기</summary>

> Figure 5: Decode latency, peak memory, and latency-accuracy trade-off for LLaMA-3.1-8B-Instruct
> from 8K to 256K context length on a single A100 64 GB. Both FullKV and AdaKV use FA2.

</details>

<a id="ev-013"></a>
### ev-013 — `2605.08317-25836a41` p.20

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0020:elem-2605.08317-25836a41-p0020-text-group-067-46bda3a60ffc:span-00000-02323` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `20` / `20` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0020-text-group-067-46bda3a60ffc` |
| 원본 element | `elem-2605.08317-25836a41-p0020-text-group-067-46bda3a60ffc` |
| Text span | `0:2323` |
| Table cell | - |
| BBox | `107.53, 418.64, 506.00, 752.30` |
| Content SHA-256 | `062cdf4c1e1645a0bc87812ac5bf0ed47c102f92f94c75e01bfe4e8a09c43f0b` |

<details>
<summary>원문 스니펫 보기</summary>

> SnapKV
> 27.80
> 42.45 48.56
> 59.01
> 43.04
> 25.83
> 26.55
> 23.26
> 22.91
> 72.50
> 87.44
> 42.80
> 1.83 100.00 64.83 56.65 46.59
> AdaKV
> 27.64
> 42.54 48.65
> 59.57
> 43.31
> 26.35
> 26.75
> 23.02
> 23.16
> 74.00
> 88.08
> 43.49
> 1.60 100.00 64.86 57.44 46.90
> ThinK
> 26.73
> 42.98 47.88
> 58.62
> 43.18
> 24.97
> 27.90
> 23.55
> 23.43
> 75.00
> 87.85
> 42.95
> 1.97 100.00 65.48 57.04 46.85
> Snap+Zip 26.60
> 43.46 47.80
> 59.57
> 43.76
> 22.11
> 29.78
> 22.67
> 23.84
> 73.50
> 87.36
> 44.65
> 2.16
> 99.50 64.09 56.08 46.68
>
> 27.35
> 44.36 50.40
> 59.35
> 43.63
> 24.87
> 30.91
> 23.29
> 24.45
> 74.50
> 87.26
> 45.24
> 0.75 100.00 62.86 54.61 47.12
>
> G
> Additional Experiments on InfiniteBench
>
> In this section, we present a detailed evaluation of RDKV on the InfiniteBench benchmark [50],
> which extends long-context evaluation to sequences exceeding 100k tokens. The 10 tasks span
> three categories: (i) retrieval—Passkey Retrieval (Retr.Pass), Number Retrieval (Retr.Num), and KV
> Retrieval (Retr.KV)— which test the ability to locate and extract specific information embedded
> in long contexts; (ii) language understanding—English Dialogue (En.Dia), English Summarization
> (En.Sum), English Multiple-Choice (En.MC), English QA (En.QA), and Chinese QA (Zh.QA)—
> which evaluate comprehension and reasoning over novel-length inputs; and (iii) structured reasoning—
> Math Find (Math.Find) and Code Debugging (Debug)—which require precise numerical or logical
> retrieval. These tasks collectively pose challenges for both context retention and fine-grained
> information extraction at extreme sequence lengths.
>
> We evaluate RDKV on LLaMA-3.1-8B-Instruct with Btotal = 1024L. The evaluation compares
> RDKV with SnapKV, AdaKV, ThinK, SnapKV+ZipCache, and FullKV (oracle).
>
> As reported in Tab. 11, RDKV achieves the highest average (39.46) among all compression methods,
> leading AdaKV (38.06) by 1.40 points. A breakdown by task category reveals where the advantage
> concentrates. On the retrieval tasks, RDKV scores 7.20 on KV Retrieval vs. ≤2.20 for all baselines—
> a 3.3× improvement—because the needle-style retrieval pattern aligns directly with the rate-distortion
> allocation: high-attention tokens are preserved at high precision while low-attention tokens are
> aggressively quantized or removed. On language understanding tasks, RDKV leads on En.Dia (13.00
> vs. ≤11.50), En.Sum (25.13 vs. ≤23.66), and En.QA (14.49 vs. ≤13.43), matching FullKV
>
> 20

</details>

<a id="ev-014"></a>
### ev-014 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:figure-04:span-00000-00177` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Figure 4` |
| 원본 element | `elem-2605.08317-25836a41-p0008-caption-032-1404e3e912e7` |
| Text span | `0:177` |
| Table cell | - |
| BBox | `108.00, 277.08, 504.00, 298.18` |
| Content SHA-256 | `4d04743462f5d3cf828237fbaa4844959bbab49649f59f84c2d1d4e4f68f1346` |

<details>
<summary>원문 스니펫 보기</summary>

> Figure 4: Needle-in-a-Haystack [48] on LLaMA-3.1-8B-Instruct at Btotal = 64L. RDKV preserves a
> near-uniform retrieval pattern; SnapKV and AdaKV drop accuracy in mid-depth bands.

</details>

<a id="ev-015"></a>
### ev-015 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:span-00000-00305` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-2605.08317-25836a41-p0022-caption-000-abb20aaad857` |
| Text span | `0:305` |
| Table cell | - |
| BBox | `107.69, 78.69, 504.01, 121.74` |
| Content SHA-256 | `e600f8b57c72d4fe26235ad9c2b4fa1c33f5741b9904bc10bdbe11073a8fa962` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9: Performance on the 11 RULER tasks across context lengths {4k, 8k, 16k, 32k, 64k, 128k}
> for LLaMA-3.1-8B-Instruct at Btotal = 2048L. The best result in each row is in bold; the second-best
> is underlined. FullKV (no compression) is reported as a reference upper bound and excluded from
> the ranking.

</details>

<a id="ev-016"></a>
### ev-016 — `2605.08317-25836a41` p.21

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0021:elem-2605.08317-25836a41-p0021-text-group-075-01b322618666:span-00000-01558` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `21` / `21` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0021-text-group-075-01b322618666` |
| 원본 element | `elem-2605.08317-25836a41-p0021-text-group-075-01b322618666` |
| Text span | `0:1558` |
| Table cell | - |
| BBox | `107.67, 418.64, 505.25, 752.30` |
| Content SHA-256 | `a814e2953180704dc97fbc7048fccb79950c839a742ac7399059306ff6246ecf` |

<details>
<summary>원문 스니펫 보기</summary>

> 32.65
> 49.51 51.68
> 64.77
> 64.95
> 40.41
> 31.78
> 24.21
> 23.94
> 78.00
> 92.06
> 47.91
> 21.50 99.50 66.34 71.90 53.82
>
> accuracy on En.MC (68.56). On structured reasoning tasks (Math.Find, Debug), all compression
> methods cluster near each other, indicating that cache compression is not the bottleneck once the
> relevant information is preserved.
>
> H
> Additional Experiments on Ablation Study
>
> H.1
> Prefill Overhead
>
> Tab. 12 breaks down the time-to-first-token (TTFT) for RDKV on LLaMA-3.1-8B-Instruct with
> a 128K-token prefill on a single A100 64 GB. The baseline is a standard FullKV prefill with
> FlashAttention-2. RDKV bypasses the HuggingFace generate wrapper and calls transformer
> layers directly, saving 593 ms of framework overhead. The four RDKV-specific stages—weight
> computation (wt, wc), MCKP bisection, and TriZone packing—add a combined 2,331 ms. The net
> overhead is 1,740 ms, or 6.0% of the FullKV prefill, yielding a measured TTFT of 30,583 ms. This
> one-time cost is amortised over the entire decode sequence; with 128K context and the 4.5× decode
> speedup reported in Sec. 4, RDKV breaks even within the first ∼50 generated tokens.
>
> H.2
> K/V Budget Split Ratio
>
> The main experiments fix an equal K/V split (BV = BK =
> 1
> 2Bhead) as a design convention
> (Sec. B). To validate this choice, we sweep the K budget ratio rK ∈{0.4, 0.5, 0.6} (so BK =
> rKBhead and BV = (1 −rK)Bhead) on LLaMA-3.1-8B-Instruct at three cache budgets Btotal ∈
> {128L, 256L, 512L}. All other settings (observation window Sw = 32, pooling kernel w = 5,
> B = {0, 2, 4, 8, 16}) are kept identical.
>
> 21

</details>

<a id="ev-017"></a>
### ev-017 — `2605.08317-25836a41` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0005:elem-2605.08317-25836a41-p0005-text-group-014-8894d362d5e6:span-00000-02432` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | MCKP |
| Object | `elem-2605.08317-25836a41-p0005-text-group-014-8894d362d5e6` |
| 원본 element | `elem-2605.08317-25836a41-p0005-text-group-014-8894d362d5e6` |
| Text span | `0:2432` |
| Table cell | - |
| BBox | `107.53, 282.99, 505.75, 673.29` |
| Content SHA-256 | `4601d20739d20fd9bd553636ed94745fe99839fc6cb9da45fddfcdb05a816fac` |

<details>
<summary>원문 스니펫 보기</summary>

> τ aτ,t are derived from the attention matrix, and channel weights wc from
> Q/K column norms. Stage 2. Reverse water-filling on wt: four thresholds partition scores into five
> bit-width zones {16, 8, 4, 2, 0}. In this example tokens 3 and 6 fall below the lowest threshold and
> are evicted (hatched rows in V cache). Stage 3. The same allocation on wc assigns per-channel
> bit-widths to the K cache, which retains only the six kept tokens (Tkept = {1, 2, 4, 5, 7, 8}).
>
> 3.2
> Per-Head Allocation Pipeline
>
> We instantiate the weights and allocation of Sec. 3.1 as a three-stage pipeline (Fig. 2) that runs
> once after prefill, separately for each layer-head pair (ℓ, h). Under FP16 reference, a per-head
> budget of Btok tokens corresponds to Bhead = 2 Btok d · 16 total bits, split equally between V and K:
> BV = BK = 1
>
> 2Bhead.
>
> Stage 1: Distortion Weight Computation. From the prefill forward pass we compute the token
> weights wt (Prop. 3.1) and channel weights wc (Prop. 3.2), as illustrated in Fig. 2 (a). Both are
> computed once from the full uncompressed cache: wt requires only the attention matrix; wc requires
> only Q and K column norms, with no value vectors or output residuals needed.
>
> Stage 2: Token Allocation in V Cache. Since each token contains d scalars, the total V budget
> BV translates to ¯BV := BV /d in units of summed bit-widths. Given the token weights wt and a
> calibrated distortion table εV (b) (Sec. B), Stage 2 solves the MCKP of Eq. (6), as shown in Fig. 2 (b):
>
> t ≤¯BV .
>
> X
>
> X
>
> bV
>
> wt εV (bV
>
> {bV
>
> t } = arg min
>
> t )
> s.t.
>
> bV
>
> t ∈B
>
> t
>
> t
>
> The output determines Tkept := {t : bV
>
> t > 0} and its complement Tevict. Retained tokens receive
> bit-widths in {2, 4, 8, 16}. Evicted tokens are removed entirely.
>
> Stage 3: Channel Allocation in K Cache. As shown in Fig. 2 (c), Stage 3 distributes the K budget
> BK across only the retained tokens Tkept. Each channel contains |Tkept| scalars, so the budget translates
> to ¯BK := BK/|Tkept|:
>
> c ≤¯BK.
>
> X
>
> X
>
> {bK
>
> wc εK(bK
>
> bK
>
> c } = arg min
>
> c )
> s.t.
>
> bK
>
> c ∈B
>
> c
>
> c
>
> A channel assigned bK
>
> c = 0 is removed under the same zero-rate interpretation as token eviction.
> Across retained tokens, K bit-widths are assigned per-channel independently of the per-token bV
>
> t . A
> single token’s K and V can therefore carry different bit-widths, the prerequisite for the TriZone layout
> of Sec. 3.3. Visualization of the resulting bit-width allocations of tokens and channels is in Sec. I .

</details>

<a id="ev-018"></a>
### ev-018 — `2605.08317-25836a41` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0005:elem-2605.08317-25836a41-p0005-text-group-013-c2ed652f60de:span-00000-00216` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | MCKP |
| Object | `elem-2605.08317-25836a41-p0005-text-group-013-c2ed652f60de` |
| 원본 element | `elem-2605.08317-25836a41-p0005-text-group-013-c2ed652f60de` |
| Text span | `0:216` |
| Table cell | - |
| BBox | `109.85, 116.91, 500.26, 262.34` |
| Content SHA-256 | `6f895f4a04182db2a77a14a9f0f11d82c66b16b6e348cc27e8777d8bca4e45a1` |

<details>
<summary>원문 스니펫 보기</summary>

> query
>
> 4
> 2
> 0
> 1
> 2
> 3
> 4
> 5
> 6
> 7
> 8
>
> ×
>
> wt =P
>
> τ aτ,t
>
> Tkept
>
> Stage 3: Channel Allocation
>
> K cache
>
> 1
> 2
> 4
> 5
> 7
> 8
>
> 16
>
> Q
>
> K
>
> 8
>
> wc
>
> 4
> 2
> 0
> 1
> 2
> 3
> 4
> 5
> 6
> 7
> 8
>
> c
>
> c
>
> ∥Q:,c∥∥K:,c∥
>
> wc =
>
> √
>
> d
>
> on Tkept only
>
> bit:
> 16
> 8
> 4
> 2
> 0 (evict)

</details>

<a id="ev-019"></a>
### ev-019 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:elem-2605.08317-25836a41-p0023-text-group-082-82131257f4ec:span-00000-00250` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0023-text-group-082-82131257f4ec` |
| 원본 element | `elem-2605.08317-25836a41-p0023-text-group-082-82131257f4ec` |
| Text span | `0:250` |
| Table cell | - |
| BBox | `212.40, 416.38, 399.60, 506.21` |
| Content SHA-256 | `8988b35dba7ab2ef8525d6b7d16df96e4daadd2dd635d8a35416ac93a65fc4e4` |

<details>
<summary>원문 스니펫 보기</summary>

> Component
> Time (ms)
> % of FullKV Prefill
>
> FullKV prefill (FA2)
> 28 843
> — (baseline)
>
> Forward path saving
> −593
> −2.1%
> wt computation
> +308
> +1.1%
> wc computation
> +550
> +1.9%
> MCKP bisection
> +609
> +2.1%
> TriZone packing
> +863
> +3.0%
>
> Net RDKV overhead
> +1,740
> +6.0%

</details>

<a id="ev-020"></a>
### ev-020 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:elem-2605.08317-25836a41-p0023-text-016-938684a7f5b2:span-00000-00065` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0023-text-016-938684a7f5b2` |
| 원본 element | `elem-2605.08317-25836a41-p0023-text-016-938684a7f5b2` |
| Text span | `0:65` |
| Table cell | - |
| BBox | `156.52, 354.36, 499.29, 363.91` |
| Content SHA-256 | `52a6cce070fa64c9b32befa3e5b8a3db908a03c1dc72c08cf526e36189fc55a1` |

<details>
<summary>원문 스니펫 보기</summary>

> 100.00
> 96.95
> 7.20
> 13.00
> 25.13
> 68.56
> 14.49 12.65
> 34.00
> 22.59 39.46

</details>

<a id="ev-021"></a>
### ev-021 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:elem-2605.08317-25836a41-p0009-text-group-030-987e8da38d69:span-00000-00432` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0009-text-group-030-987e8da38d69` |
| 원본 element | `elem-2605.08317-25836a41-p0009-text-group-030-987e8da38d69` |
| Text span | `0:432` |
| Table cell | - |
| BBox | `109.28, 70.95, 495.97, 183.83` |
| Content SHA-256 | `140b1fd48549091dd3c24e4fd9f6b9ddf8e1074b994a7a390b224528e86a209e` |

<details>
<summary>원문 스니펫 보기</summary>

> 100
>
> 8k
>
> 100
>
> 8k
>
> Full KV (FA2)
> AdaKV
> RDKV (ours)
>
> OOM
> Full KV (FA2)
> AdaKV
> RDKV (ours)
>
> 80
>
> 80
>
> Peak Memory (GB)
>
> Latency (ms/tok)
>
> 90
>
> RULER Average
>
> 8k
>
> 60
>
> 60
>
> 80
>
> 128k
>
> 40
>
> 40
>
> 70
>
> 128k
> Full KV (FA2)
> AdaKV
> RDKV (ours)
>
> 20
>
> 20
>
> 60
>
> 128k
>
> 0
>
> 0
>
> 8k
> 16k
> 32k
> 64k
> 128k
> 256k
> Context Length
>
> 8k
> 16k
> 32k
> 64k
> 128k
> 256k
> Context Length
>
> 20
> 40
> 60
> 80
> Decoding Latency (ms/tok)
>
> (a) Decode latency.
>
> (b) Peak memory.
>
> (c) Latency vs. Accuracy.

</details>

<a id="ev-022"></a>
### ev-022 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:span-00000-00052` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-2605.08317-25836a41-p0009-caption-037-6ccf15f5a4d2` |
| Text span | `0:52` |
| Table cell | - |
| BBox | `384.89, 351.01, 504.00, 371.80` |
| Content SHA-256 | `539e49964df86c8db174aadafce89782808ccb05d3b0ad2f14f2237ae914ff49` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4: Action-space ablation
> on LongBench average.

</details>

<a id="ev-023"></a>
### ev-023 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:elem-2605.08317-25836a41-p0008-text-group-027-5f6d66adf8f5:span-00000-00517` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0008-text-group-027-5f6d66adf8f5` |
| 원본 element | `elem-2605.08317-25836a41-p0008-text-group-027-5f6d66adf8f5` |
| Text span | `0:517` |
| Table cell | - |
| BBox | `109.09, 72.10, 499.51, 269.44` |
| Content SHA-256 | `201c658bb0ee17858ed5be41516664c1d7c3fc003959282cdd01c01a00e558fc` |

<details>
<summary>원문 스니펫 보기</summary>

> 0.0
>
> 0.0
>
> Depth Percent
>
> Depth Percent
>
> 22.0
>
> 22.0
>
> 44.0
>
> 44.0
>
> 67.0
>
> 67.0
>
> 89.0
>
> 89.0
>
> 4000
> 8000
> 12000
> 16000
> 20000
> 24000
> 28000
> 32000
> Token Limit
>
> 4000
> 8000
> 12000
> 16000
> 20000
> 24000
> 28000
> 32000
> Token Limit
>
> (a) FullKV (avg. 1.00).
>
> (b) SnapKV [11] (avg. 0.64).
>
> 0.0
>
> 0.0
>
> Depth Percent
>
> Depth Percent
>
> 22.0
>
> 22.0
>
> 44.0
>
> 44.0
>
> 67.0
>
> 67.0
>
> 89.0
>
> 89.0
>
> 4000
> 8000
> 12000
> 16000
> 20000
> 24000
> 28000
> 32000
> Token Limit
>
> 4000
> 8000
> 12000
> 16000
> 20000
> 24000
> 28000
> 32000
> Token Limit
>
> (c) AdaKV [26] (avg. 0.68).
>
> (d) RDKV (avg. 0.99).

</details>

<a id="ev-024"></a>
### ev-024 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:span-00000-00070` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-2605.08317-25836a41-p0008-caption-034-6741a8d4df63` |
| Text span | `0:70` |
| Table cell | - |
| BBox | `337.37, 318.32, 505.65, 339.27` |
| Content SHA-256 | `ed275f87150a3e6baf3e8ae2ce9460b0083af97b122b46e7d92a91076954b71b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3: InfiniteBench [50] 10-task aver-
> age (LLaMA-3.1-8B-Instruct).

</details>

<a id="ev-025"></a>
### ev-025 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:elem-2605.08317-25836a41-p0022-text-001-200c77641151:span-00000-00075` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | Method |
| Object | `elem-2605.08317-25836a41-p0022-text-001-200c77641151` |
| 원본 element | `elem-2605.08317-25836a41-p0022-text-001-200c77641151` |
| Text span | `0:75` |
| Table cell | - |
| BBox | `144.94, 126.77, 436.89, 133.35` |
| Content SHA-256 | `057275f0e8f4ce60a7d891ab63b07f69c60c43484ec23a5e6d9db2582f991f64` |

<details>
<summary>원문 스니펫 보기</summary>

> S-NIAH-1 S-NIAH-2 S-NIAH-3 MK-NIAH-1 MK-NIAH-2 MK-NIAH-3 MQ-NIAH MV-NIAH
> VT

</details>

<a id="ev-026"></a>
### ev-026 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:elem-2605.08317-25836a41-p0022-text-group-076-330ac28769c7:span-00000-00439` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | CWE FWE |
| Object | `elem-2605.08317-25836a41-p0022-text-group-076-330ac28769c7` |
| 원본 element | `elem-2605.08317-25836a41-p0022-text-group-076-330ac28769c7` |
| Text span | `0:439` |
| Table cell | - |
| BBox | `114.56, 126.77, 497.44, 195.59` |
| Content SHA-256 | `c6b08f3af4f84a607f7d85585bc86f2a9d04aed478758ee71758c5ecea686745` |

<details>
<summary>원문 스니펫 보기</summary>

> Avg.
>
> Sequence length = 4k
>
> FullKV
> 100.00
> 100.00
> 100.00
> 100.00
> 100.00
> 99.80
> 99.80
> 99.70
> 99.96 98.92 86.20 98.58
>
> SnapKV
> 100.00
> 100.00
> 100.00
> 100.00
> 99.60
> 95.80
> 99.70
> 99.70
> 99.92 97.42 76.40 97.14
> AdaKV
> 100.00
> 100.00
> 100.00
> 100.00
> 99.80
> 99.00
> 99.75
> 99.75
> 99.96 98.20 81.40 97.99
> ThinK
> 100.00
> 100.00
> 100.00
> 100.00
> 99.80
> 96.80
> 99.70
> 99.50
> 99.80 99.12 84.47 98.11
> Snap+Zip
> 46.60
> 98.60
> 92.80
> 99.80
> 63.00
> 0.00
> 99.20
> 94.65
> 88.40 83.72 74.60 76.49

</details>

<a id="ev-027"></a>
### ev-027 — `2605.08317-25836a41` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0005:figure-02:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | MCKP |
| Object | `Figure 2` |
| 원본 element | `elem-vision-90c0de8cbba7b483ab9a` |
| Text span | `0:1866` |
| Table cell | - |
| BBox | `24.00, 24.00, 588.00, 312.11` |
| Content SHA-256 | `dacb7e2f19f2e552fe89dd404bc6c7370c5554e7dfca5aeff242bdeb6b0f1421` |

<details>
<summary>원문 스니펫 보기</summary>

> Figure 2: RDKV per-head bit-allocation pipeline (illustrated for 8 tokens and 8 channels). Stage
> 1. Token weights wt = P
> Stage 1: Weighting
> query
> a_{\tau,t}
> w_t = \sum_\tau a_{\tau,t}
> Q
> K
> c c
> w_c = \frac{\lVert Q_{:,c}\rVert\ \lVert K_{:,c}\rVert}{\sqrt{d}}
>
> Stage 2: Token Allocation
> w_t
> 1 2 3 4 5 6 7 8
> 16 8 4 2 0
> MCKP
> V cache
> 1 2 3 4 5 6 7 8
> T_kept / T_evict
> T_kept
>
> Stage 3: Channel Allocation
> w_c
> 1 2 3 4 5 6 7 8
> 16 8 4 2 0
> MCKP
> K cache
> 1 2 4 5 7 8
> on T_kept only
>
> bit: 16 8 4 2 0 (evict)
>
> Figure 2: RDKV per-head bit-allocation pipeline (illustrated for 8 tokens and 8 channels). Stage
> 1. Token weights w_t = \sum_\tau a_{\tau,t} are derived from the attention matrix, and channel weights w_c from
> Q/K column norms. Stage 2. Reverse water-filling on w_t: four thresholds partition scores into five
> bit-width zones {16, 8, 4, 2, 0}. In this example tokens 3 and 6 fall below the lowest threshold and
> attention matrix a_{\tau,t} -> token weights w_t: w_t = \sum_\tau a_{\tau,t}
> Q and K column norms -> channel weights w_c: w_c = \lVert Q_{:,c}\rVert \lVert K_{:,c}\rVert / \sqrt{d}
> token weights w_t -> Stage 2 token-allocation bar chart: input
> Stage 2 token-allocation bar chart -> V cache: MCKP allocation
> V cache rows 3 and 6 -> T_evict: hatched; marked with red ×
> V cache rows 1, 2, 4, 5, 7, and 8 -> T_kept: retained
> channel weights w_c -> Stage 3 channel-allocation bar chart: input
> Stage 3 channel-allocation bar chart -> K cache: MCKP allocation
> T_kept -> K cache: K cache is shown only for retained token rows
> The legend maps dark blue to 16 bits, blue to 8 bits, medium blue to 4 bits, light blue to 2 bits, and hatched gray to 0 (evict).
> In Stage 2, token bars 3 and 6 are hatched at 0, while the V-cache rows 3 and 6 are hatched and marked with red × symbols.
> The K-cache row labels are 1, 2, 4, 5, 7, and 8, and it is labeled “on T_kept only.”

</details>

<a id="ev-028"></a>
### ev-028 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:figure-04:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Figure 4` |
| 원본 element | `elem-vision-f6733ab38b89df5234ab` |
| Text span | `0:1205` |
| Table cell | - |
| BBox | `24.00, 24.00, 588.00, 310.18` |
| Content SHA-256 | `3441c68ae576ac19efdff20f6c9eae1cb57ad7a8fb34a1b86c2476b6bd53ed5e` |

<details>
<summary>원문 스니펫 보기</summary>

> Figure 4: Needle-in-a-Haystack [48] on LLaMA-3.1-8B-Instruct at Btotal = 64L. RDKV preserves a
> near-uniform retrieval pattern; SnapKV and AdaKV drop accuracy in mid-depth bands.
> Axes in all four heatmaps: y-axis “Depth Percent” with ticks 0.0, 22.0, 44.0, 67.0, 89.0; x-axis “Token Limit” with ticks 4000, 8000, 12000, 16000, 20000, 24000, 28000, 32000.
>
> (a) FullKV (avg. 1.00).
> (b) SnapKV [11] (avg. 0.64).
> (c) AdaKV [26] (avg. 0.68).
> (d) RDKV (avg. 0.99).
>
> Figure 4: Needle-in-a-Haystack [48] on LLaMA-3.1-8B-Instruct at B_total = 64L. RDKV preserves a near-uniform retrieval pattern; SnapKV and AdaKV drop accuracy in mid-depth bands.
> series=FullKV; x=; y=1.00; unit=avg.
> series=SnapKV [11]; x=; y=0.64; unit=avg.
> series=AdaKV [26]; x=; y=0.68; unit=avg.
> series=RDKV; x=; y=0.99; unit=avg.
> FullKV heatmap is visually near-uniform teal across token limits and depth percentages.
> SnapKV heatmap has a broad differently colored mid-depth band across much of the token-limit range.
> AdaKV heatmap has a broad differently colored mid-depth band, with teal regions near the top and bottom depths.
> RDKV heatmap is visually near-uniform teal with a few isolated differently colored cells at higher token limits.

</details>

<a id="ev-029"></a>
### ev-029 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | - |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `1cd78b90a6ab2fc22ce4df041bc49431873638db214853b0f460ad9970087a28` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3: InfiniteBench [50] 10-task aver-
> age (LLaMA-3.1-8B-Instruct).
> Table 3: InfiniteBench [50] 10-task aver-
> age (LLaMA-3.1-8B-Instruct).
>
> Method | Avg.
> FullKV | 45.38
> SnapKV[11] | 37.91
> AdaKV[26] | 38.06
> ThinK[12] | 36.73
> Snap+Zip | 37.76
> RDKV | 39.46
> cell[0,0] Method
> cell[0,1] Avg.
> cell[1,0] FullKV
> cell[1,1] 45.38
> cell[2,0] SnapKV[11]
> cell[2,1] 37.91
> cell[3,0] AdaKV[26]
> cell[3,1] 38.06
> cell[4,0] ThinK[12]
> cell[4,1] 36.73
> cell[5,0] Snap+Zip
> cell[5,1] 37.76
> cell[6,0] RDKV
> cell[6,1] 39.46
> The RDKV row and its Avg. value 39.46 are bolded.

</details>

<a id="ev-030"></a>
### ev-030 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r00-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r0c0=Method |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `9bba986520ad56a04f77eeb667b7b1c8830db89e5059b2ae53a64e7d1bc38476` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=0; column=0; column_header=Method; value=Method

</details>

<a id="ev-031"></a>
### ev-031 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r00-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r0c1=Avg. |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `2dcffad9afdacdb32339d3ef057f3f3b2777ab9d227542dfbbed9af4b44c3d0c` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=0; column=1; column_header=Avg.; value=Avg.

</details>

<a id="ev-032"></a>
### ev-032 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r01-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r1c0=FullKV |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `016aa8b170a34f7a05a8dbdfbbdd1a072bc06a96954cdf7f2dc04cc96e2886ff` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=1; column=0; row_header=FullKV; column_header=Method; value=FullKV

</details>

<a id="ev-033"></a>
### ev-033 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r01-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r1c1=45.38 |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `7aaa69e8208bb1b0701370bc882f8312108a88592b67a825533d044678f3c9ee` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=1; column=1; row_header=FullKV; column_header=Avg.; value=45.38

</details>

<a id="ev-034"></a>
### ev-034 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r02-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r2c0=SnapKV[11] |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `bcf524012460d507dadf5e5bb275671ad43d9cdbba816f8c86dacb38f9486aca` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=2; column=0; row_header=SnapKV[11]; column_header=Method; value=SnapKV[11]

</details>

<a id="ev-035"></a>
### ev-035 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r02-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r2c1=37.91 |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `7e1216da4a7ee4122ae9234235226d0745b94a7aee930e63816cfe091decab2b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=2; column=1; row_header=SnapKV[11]; column_header=Avg.; value=37.91

</details>

<a id="ev-036"></a>
### ev-036 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r03-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r3c0=AdaKV[26] |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `9a6d908dca601bb2b36343acd0413db621a7600c9152e709594d31c2c641bdc3` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=3; column=0; row_header=AdaKV[26]; column_header=Method; value=AdaKV[26]

</details>

<a id="ev-037"></a>
### ev-037 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r03-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r3c1=38.06 |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `5647f9cf74a701056b1fabfd64a68ce1979da889b50e66a71eb747ccc37ab51d` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=3; column=1; row_header=AdaKV[26]; column_header=Avg.; value=38.06

</details>

<a id="ev-038"></a>
### ev-038 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r04-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r4c0=ThinK[12] |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `ae50f63f98769782b1c6ec4dd03c54180c97aeebe4f9ccadfdee70018220a241` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=4; column=0; row_header=ThinK[12]; column_header=Method; value=ThinK[12]

</details>

<a id="ev-039"></a>
### ev-039 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r04-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r4c1=36.73 |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `ef7b4a565b0d25539adee9868bbe2eedec6e95fa495766c6de73521a1c21d535` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=4; column=1; row_header=ThinK[12]; column_header=Avg.; value=36.73

</details>

<a id="ev-040"></a>
### ev-040 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r05-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r5c0=Snap+Zip |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `a3aeeb40044e27a08adbefb20735111d5e24b012d24c4befeb28154704403f76` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=5; column=0; row_header=Snap+Zip; column_header=Method; value=Snap+Zip

</details>

<a id="ev-041"></a>
### ev-041 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r05-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r5c1=37.76 |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `9afdde510938e1c39bd4a90b9ea4eb70908ab87a352f7ccc9bf9ed6ec59030fb` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=5; column=1; row_header=Snap+Zip; column_header=Avg.; value=37.76

</details>

<a id="ev-042"></a>
### ev-042 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r06-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r6c0=RDKV |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `baa2d22064604429e340699f82d7b718db6f0325bee44cc6dd456085d5b44add` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=6; column=0; row_header=RDKV; column_header=Method; value=RDKV

</details>

<a id="ev-043"></a>
### ev-043 — `2605.08317-25836a41` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0008:table-03:cell-r06-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | RDKV |
| Object | `Table 3` |
| 원본 element | `elem-vision-79073d52baff3841fa09` |
| Text span | `0:546` |
| Table cell | r6c1=39.46 |
| BBox | `312.00, 306.32, 588.00, 780.00` |
| Content SHA-256 | `fd1216173f290187b0825be250b228734815698976d355afc79bb7ccb46d2369` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 3; row=6; column=1; row_header=RDKV; column_header=Avg.; value=39.46

</details>

<a id="ev-044"></a>
### ev-044 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:figure-05:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Figure 5` |
| 원본 element | `elem-vision-57120400b38896160ced` |
| Text span | `0:1356` |
| Table cell | - |
| BBox | `24.00, 24.00, 588.00, 224.58` |
| Content SHA-256 | `81fdfc1d75851c3b7345f497c3c98d8be2d2904fc899f3c99f1865530b82a6f6` |

<details>
<summary>원문 스니펫 보기</summary>

> Figure 5: Decode latency, peak memory, and latency-accuracy trade-off for LLaMA-3.1-8B-Instruct
> from 8K to 256K context length on a single A100 64 GB. Both FullKV and AdaKV use FA2.
> (a) Decode latency.
> Legend: Full KV (FA2); AdaKV; RDKV (ours)
> Y-axis: Latency (ms/tok)
> X-axis: Context Length
> X ticks: 8k, 16k, 32k, 64k, 128k, 256k
>
> (b) Peak memory.
> Legend: Full KV (FA2); AdaKV; RDKV (ours)
> Y-axis: Peak Memory (GB)
> X-axis: Context Length
> X ticks: 8k, 16k, 32k, 64k, 128k, 256k
> Text: OOM
>
> (c) Latency vs. Accuracy.
> Legend: Full KV (FA2); AdaKV; RDKV (ours)
> Y-axis: RULER Average
> X-axis: Decoding Latency (ms/tok)
> Visible annotations: 8k; 128k
>
> Figure 5: Decode latency, peak memory, and latency-accuracy trade-off for LLaMA-3.1-8B-Instruct from 8K to 256K context length on a single A100 64 GB. Both FullKV and AdaKV use FA2.
> Panel (a) shows three series: Full KV (FA2), AdaKV, and RDKV (ours), over context lengths from 8k through 256k.
> In panel (a), the Full KV (FA2) line rises with context length, while the AdaKV and RDKV (ours) lines are nearly horizontal.
> Panel (b) marks the Full KV (FA2) point at 256k as "OOM".
> In panel (b), all visible memory series increase as context length increases.
> Panel (c) plots RULER Average against Decoding Latency (ms/tok) for Full KV (FA2), AdaKV, and RDKV (ours), with visible endpoint annotations "8k" and "128k".

</details>

<a id="ev-045"></a>
### ev-045 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | - |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `082178235df98a3df86ac21f77496139d4f6449b202464c8366b6bd0aa1aefdb` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5: TriZone ablation: de-
> code latency (ms/tok).
> Table 5: TriZone ablation: decode latency (ms/tok).
>
> Config. | 16K | 64K
> RDKV w/ TriZone | 17.99 | 18.02
> RDKV w/o TriZone | 36.05 | 36.47
> cell[0,0] Config.
> cell[0,1] 16K
> cell[0,2] 64K
> cell[1,0] RDKV w/ TriZone
> cell[1,1] 17.99
> cell[1,2] 18.02
> cell[2,0] RDKV w/o TriZone
> cell[2,1] 36.05
> cell[2,2] 36.47
> The values 17.99 and 18.02 in the “RDKV w/ TriZone” row are bolded.

</details>

<a id="ev-046"></a>
### ev-046 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r00-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r0c0=Config. |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `f0c6349e49470df01d5a634608ceda8fb26193a3c9b25b61b696773cc18fe2f2` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=0; column=0; column_header=Config.; value=Config.

</details>

<a id="ev-047"></a>
### ev-047 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r00-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r0c1=16K |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `6aeb55357db0cec2f1d9092fd011f5c96d486e46593ad6902021c569f428a087` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=0; column=1; column_header=16K; value=16K

</details>

<a id="ev-048"></a>
### ev-048 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r00-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r0c2=64K |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `d54f96025b0dba870c48ee2a54a42b4c37749f95cd2137de3abca15e498dc674` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=0; column=2; column_header=64K; value=64K

</details>

<a id="ev-049"></a>
### ev-049 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r01-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r1c0=RDKV w/ TriZone |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `1b57eff76a51a7a0f95a8a35984515274caee4d6af76782e05546b3cddd2eab7` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=1; column=0; row_header=RDKV w/ TriZone; column_header=Config.; value=RDKV w/ TriZone

</details>

<a id="ev-050"></a>
### ev-050 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r01-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r1c1=17.99 |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `7d5c54669d1ba1a1819a86dfb597060d1b76c52eea544ca7bf8c04d3089374fc` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=1; column=1; row_header=RDKV w/ TriZone; column_header=16K; value=17.99

</details>

<a id="ev-051"></a>
### ev-051 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r01-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r1c2=18.02 |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `fac092962c3b4f24e4bf8e502dafaea839ff6f5d1ab7501c95cdc7dd9a4e4a4c` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=1; column=2; row_header=RDKV w/ TriZone; column_header=64K; value=18.02

</details>

<a id="ev-052"></a>
### ev-052 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r02-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r2c0=RDKV w/o TriZone |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `a858bf7173828ab2a3f4ae6c36729abdaade406998df2bd195cb228d7513a08a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=2; column=0; row_header=RDKV w/o TriZone; column_header=Config.; value=RDKV w/o TriZone

</details>

<a id="ev-053"></a>
### ev-053 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r02-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r2c1=36.05 |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `c124e7c8ad513b38185796bae628f5a52a46920615dd0cb046e45e9538298aa1` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=2; column=1; row_header=RDKV w/o TriZone; column_header=16K; value=36.05

</details>

<a id="ev-054"></a>
### ev-054 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-05:cell-r02-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 5` |
| 원본 element | `elem-vision-a406f521f098cb18909e` |
| Text span | `0:422` |
| Table cell | r2c2=36.47 |
| BBox | `312.00, 448.96, 588.00, 780.00` |
| Content SHA-256 | `e57336e99f80cca37e02422211f501e5ec17ddf647f668cd12a3e3dbe6f64e2a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 5; row=2; column=2; row_header=RDKV w/o TriZone; column_header=64K; value=36.47

</details>

<a id="ev-055"></a>
### ev-055 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | - |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `91d58a07a880f7d12a84328593d5145d7dc34bfa24ecea1ad66ca1fef602c423` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4: Action-space ablation
> on LongBench average.
> Table 4: Action-space ablation
> on LongBench average.
>
> Config. | 128L | 512L
> Quant-only | 39.06 | 40.59
> Evict-only | 42.53 | 47.18
> Tri-state | 46.91 | 49.05
> Joint (RDKV) | 47.43 | 49.22
> cell[0,0] Config.
> cell[0,1] 128L
> cell[0,2] 512L
> cell[1,0] Quant-only
> cell[1,1] 39.06
> cell[1,2] 40.59
> cell[2,0] Evict-only
> cell[2,1] 42.53
> cell[2,2] 47.18
> cell[3,0] Tri-state
> cell[3,1] 46.91
> cell[3,2] 49.05
> cell[4,0] Joint (RDKV)
> cell[4,1] 47.43
> cell[4,2] 49.22
> The values 46.91 and 49.05 in the Tri-state row are underlined.
> The values 47.43 and 49.22 in the Joint (RDKV) row are bolded.

</details>

<a id="ev-056"></a>
### ev-056 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r00-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r0c0=Config. |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `3bc36d3d9da34a60dbe750b403bbe41b10675c5b510cb977b9bc56cba8a7799e` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=0; column=0; column_header=Config.; value=Config.

</details>

<a id="ev-057"></a>
### ev-057 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r00-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r0c1=128L |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `51028f9ee133e3c8717e24e9d47d0d9e4e9351c8a9f3e6cadeb35333c7500bc9` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=0; column=1; column_header=128L; value=128L

</details>

<a id="ev-058"></a>
### ev-058 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r00-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r0c2=512L |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `fb951548a4797a4f64773c8f2387b785e61d4b867bafc697c9b9340087d0d2db` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=0; column=2; column_header=512L; value=512L

</details>

<a id="ev-059"></a>
### ev-059 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r01-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r1c0=Quant-only |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `14fe27b18f6f437f61f2b8c42e0b33bc83d7f604d3e530109fda06f18f622143` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=1; column=0; row_header=Quant-only; column_header=Config.; value=Quant-only

</details>

<a id="ev-060"></a>
### ev-060 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r01-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r1c1=39.06 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `04d56131c172074286c3b11d69298c0415fcf612ca53132b07ff179f448ee6ed` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=1; column=1; row_header=Quant-only; column_header=128L; value=39.06

</details>

<a id="ev-061"></a>
### ev-061 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r01-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r1c2=40.59 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `9c23383f0bf00189209037c30abdb503988e26897c80d8f2bbc473beb2f1bd24` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=1; column=2; row_header=Quant-only; column_header=512L; value=40.59

</details>

<a id="ev-062"></a>
### ev-062 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r02-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r2c0=Evict-only |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `ff6e23b269327ffd8a1add34eb8ad9c758a204927454f2388819583e56b62cfa` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=2; column=0; row_header=Evict-only; column_header=Config.; value=Evict-only

</details>

<a id="ev-063"></a>
### ev-063 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r02-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r2c1=42.53 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `abd09c16b3bd6f45b3f465698fcf47e597d2ee8d560bee1523fc817f6b87794b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=2; column=1; row_header=Evict-only; column_header=128L; value=42.53

</details>

<a id="ev-064"></a>
### ev-064 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r02-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r2c2=47.18 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `cf923139e9d86ff6e07f4cc96dc44b5583014bcbd0315bee59309a2519b87a16` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=2; column=2; row_header=Evict-only; column_header=512L; value=47.18

</details>

<a id="ev-065"></a>
### ev-065 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r03-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r3c0=Tri-state |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `972d00c6879f1e2804cf9a5041105f0e1e9aa3377e25ea216b3cc6cd9b5f00d0` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=3; column=0; row_header=Tri-state; column_header=Config.; value=Tri-state

</details>

<a id="ev-066"></a>
### ev-066 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r03-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r3c1=46.91 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `30dda7acfd232c36c5834003b4a31de7c11dbdd3dd0dec868c26049b9bdef8a0` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=3; column=1; row_header=Tri-state; column_header=128L; value=46.91

</details>

<a id="ev-067"></a>
### ev-067 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r03-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r3c2=49.05 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `a08504208a5a82739a95caa0d2e9a29df4a3754060df378c53b3b2696b02160f` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=3; column=2; row_header=Tri-state; column_header=512L; value=49.05

</details>

<a id="ev-068"></a>
### ev-068 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r04-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r4c0=Joint (RDKV) |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `e7728749366d15fbc7868f058d1081dde1da1b65dbc11687cdcd932c06a36620` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=4; column=0; row_header=Joint (RDKV); column_header=Config.; value=Joint (RDKV)

</details>

<a id="ev-069"></a>
### ev-069 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r04-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r4c1=47.43 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `a2681245189713145bc56fb791ff4bfc9c5f4bfa4fb36b51a75c970276f986ac` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=4; column=1; row_header=Joint (RDKV); column_header=128L; value=47.43

</details>

<a id="ev-070"></a>
### ev-070 — `2605.08317-25836a41` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0009:table-04:cell-r04-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | RDKV |
| Object | `Table 4` |
| 원본 element | `elem-vision-ab9ec2f51ec243f01b3d` |
| Text span | `0:625` |
| Table cell | r4c2=49.22 |
| BBox | `312.00, 339.01, 588.00, 454.96` |
| Content SHA-256 | `6ad1a2fda718a1de1da779121c342252ce26f44a85fcf1510db9bf3db248cd44` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 4; row=4; column=2; row_header=Joint (RDKV); column_header=512L; value=49.22

</details>

<a id="ev-071"></a>
### ev-071 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | - |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `7078aa199eccd94456c3d573b41d4274b74fd155244594b3876401223bdb31c9` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9: Performance on the 11 RULER tasks across context lengths {4k, 8k, 16k, 32k, 64k, 128k}
> for LLaMA-3.1-8B-Instruct at Btotal = 2048L. The best result in each row is in bold; the second-best
> is underlined. FullKV (no compression) is reported as a reference upper bound and excluded from
> the ranking.
> Table 9: Performance on the 11 RULER tasks across context lengths {4k, 8k, 16k, 32k, 64k, 128k} for LLaMA-3.1-8B-Instruct at B_total = 2048L. The best result in each row is in bold; the second-best is underlined. FullKV (no compression) is reported as a reference upper bound and excluded from the ranking.
>
> Columns: Method | S-NIAH-1 | S-NIAH-2 | S-NIAH-3 | MK-NIAH-1 | MK-NIAH-2 | MK-NIAH-3 | MQ-NIAH | MV-NIAH | VT | CWE | FWE | Avg.
> cell[0,11] 98.58
> cell[1,11] 97.14
> cell[2,11] 97.99
> cell[3,11] 98.11
> cell[4,11] 76.49
> cell[5,11] 98.59
> cell[6,11] 98.88
> cell[7,11] 93.65
> cell[8,11] 95.50
> cell[9,11] 94.32
> cell[10,11] 75.85
> cell[11,11] 98.84
> cell[12,11] 96.98
> cell[13,11] 89.70
> cell[14,11] 90.94
> cell[15,11] 87.33
> cell[16,11] 68.82
> cell[17,11] 97.17
> cell[18,11] 90.33
> cell[19,11] 82.96
> cell[20,11] 84.22
> cell[21,11] 79.41
> cell[22,11] 73.52
> cell[23,11] 89.93
> cell[24,11] 88.49
> cell[25,11] 77.92
> cell[26,11] 78.73
> cell[27,11] 73.46
> cell[28,11] 72.82
> cell[29,11] 83.20
> cell[30,11] 79.91
> cell[31,11] 67.17
> cell[32,11] 64.42
> cell[33,11] 67.14
> cell[34,11] 66.55
> cell[35,11] 70.28
> The table is organized into six sequence-length sections: 4k, 8k, 16k, 32k, 64k, and 128k.
> In every displayed sequence-length section, the RDKV value in the Avg. column is bold.

</details>

<a id="ev-072"></a>
### ev-072 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r00-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r0c11=98.58 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `88d6fc4dcc4e1edbe982a930d46a08d6fdf2753dbadf571e44883fbd0a8f14a1` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=0; column=11; row_header=Sequence length = 4k | FullKV; column_header=Avg.; value=98.58

</details>

<a id="ev-073"></a>
### ev-073 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r01-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r1c11=97.14 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `c2af22221246e6a4f22f70b55ab92bb5474c9366fbe7b12339ae7c3144f3d23f` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=1; column=11; row_header=Sequence length = 4k | SnapKV; column_header=Avg.; value=97.14

</details>

<a id="ev-074"></a>
### ev-074 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r02-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r2c11=97.99 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `da1f4ea484b15cc3be34ce2a8325ddbccb81e570304376a6ae75bfd300ceb142` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=2; column=11; row_header=Sequence length = 4k | AdaKV; column_header=Avg.; value=97.99

</details>

<a id="ev-075"></a>
### ev-075 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r03-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r3c11=98.11 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `2ef3569d988873e4fdf9de9b311f3f8799ccec2906972e882f4fc9d82d47f877` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=3; column=11; row_header=Sequence length = 4k | ThinK; column_header=Avg.; value=98.11

</details>

<a id="ev-076"></a>
### ev-076 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r04-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r4c11=76.49 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `93879ba312b96636dd5f4b682ff4541830467bfb0373bfa6228eb565d76aa0b2` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=4; column=11; row_header=Sequence length = 4k | Snap+Zip; column_header=Avg.; value=76.49

</details>

<a id="ev-077"></a>
### ev-077 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r05-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r5c11=98.59 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `f80561900430488ebf3304f8245232938a6dde40acd700619e49ce9bcbba97ea` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=5; column=11; row_header=Sequence length = 4k | RDKV; column_header=Avg.; value=98.59

</details>

<a id="ev-078"></a>
### ev-078 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r06-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r6c11=98.88 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `c0670fca2c426fe6f5ed1bc455160fdfe212b1398e32539f4d955a76a774e08a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=6; column=11; row_header=Sequence length = 8k | FullKV; column_header=Avg.; value=98.88

</details>

<a id="ev-079"></a>
### ev-079 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r07-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r7c11=93.65 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `a83b890c8a3ae08bd4151b2cf465404404e30feb1b264daf6854d36843be678f` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=7; column=11; row_header=Sequence length = 8k | SnapKV; column_header=Avg.; value=93.65

</details>

<a id="ev-080"></a>
### ev-080 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r08-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r8c11=95.50 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `9c6d121fcdfb893b9a2be70d09ee4d110daf153e041bc3ac894fed160efb75d9` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=8; column=11; row_header=Sequence length = 8k | AdaKV; column_header=Avg.; value=95.50

</details>

<a id="ev-081"></a>
### ev-081 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r09-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r9c11=94.32 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `488216518f6bc1954cf6c8d3781e5a180c2009ec807e4614aba2cd32a94091e7` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=9; column=11; row_header=Sequence length = 8k | ThinK; column_header=Avg.; value=94.32

</details>

<a id="ev-082"></a>
### ev-082 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r10-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r10c11=75.85 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `60164d9d6a7066bd67e24af4584193f9b7bfd1931808b32cd83d4a7a9708d1b3` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=10; column=11; row_header=Sequence length = 8k | Snap+Zip; column_header=Avg.; value=75.85

</details>

<a id="ev-083"></a>
### ev-083 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r11-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r11c11=98.84 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `219fa30c7b05c6d9e85829d37c91484993d9dd481b4db534dcd9b54b7d447f0f` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=11; column=11; row_header=Sequence length = 8k | RDKV; column_header=Avg.; value=98.84

</details>

<a id="ev-084"></a>
### ev-084 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r12-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r12c11=96.98 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `31763f6b1a400e9b9f5dff20a416b14d08f5e25c6b62e077e869128b2735899b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=12; column=11; row_header=Sequence length = 16k | FullKV; column_header=Avg.; value=96.98

</details>

<a id="ev-085"></a>
### ev-085 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r13-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r13c11=89.70 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `2ad182595e8a440ac1011d1441174857fbfe9fcda2ddcd31f2831b38805d7ec6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=13; column=11; row_header=Sequence length = 16k | SnapKV; column_header=Avg.; value=89.70

</details>

<a id="ev-086"></a>
### ev-086 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r14-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r14c11=90.94 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `8a66ac385ab8959e2de53288fce8b86c06a24c018fae07f744fafce57b5465c8` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=14; column=11; row_header=Sequence length = 16k | AdaKV; column_header=Avg.; value=90.94

</details>

<a id="ev-087"></a>
### ev-087 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r15-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r15c11=87.33 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `0a335ec8dfea4328c220ea307ffb6baa04613351566b6c6d96f75ff854f096a8` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=15; column=11; row_header=Sequence length = 16k | ThinK; column_header=Avg.; value=87.33

</details>

<a id="ev-088"></a>
### ev-088 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r16-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r16c11=68.82 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `ac84b13d478e9dd6d691052225d64e584d11fb113829e73608806a690997e97d` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=16; column=11; row_header=Sequence length = 16k | Snap+Zip; column_header=Avg.; value=68.82

</details>

<a id="ev-089"></a>
### ev-089 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r17-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r17c11=97.17 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `f6c6e85d73bdd492bb499ffc8bab9828944c62782410b1c94408ec3ff8c00713` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=17; column=11; row_header=Sequence length = 16k | RDKV; column_header=Avg.; value=97.17

</details>

<a id="ev-090"></a>
### ev-090 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r18-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r18c11=90.33 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `4085d9f5f5dbfff83b515723b740bf06401e892c24f3cd6374ab71842cc89721` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=18; column=11; row_header=Sequence length = 32k | FullKV; column_header=Avg.; value=90.33

</details>

<a id="ev-091"></a>
### ev-091 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r19-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r19c11=82.96 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `6d41e7378d882b49479809d7583b3d14563a592b53626823e3180581ed6c4ed6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=19; column=11; row_header=Sequence length = 32k | SnapKV; column_header=Avg.; value=82.96

</details>

<a id="ev-092"></a>
### ev-092 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r20-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r20c11=84.22 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `6ecf6de9922f6d1f2302b991e457c2a93ff4cb87f6697149839fdea9523b429a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=20; column=11; row_header=Sequence length = 32k | AdaKV; column_header=Avg.; value=84.22

</details>

<a id="ev-093"></a>
### ev-093 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r21-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r21c11=79.41 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `db707116ecefec8d643af8d536dff6fe92b7039bd59fac992738dd16467ef2e3` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=21; column=11; row_header=Sequence length = 32k | ThinK; column_header=Avg.; value=79.41

</details>

<a id="ev-094"></a>
### ev-094 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r22-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r22c11=73.52 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `0fe4873994f3c0f99252ed62c528ea7da86e06c5d4c4b9575aabb052d151cdb9` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=22; column=11; row_header=Sequence length = 32k | Snap+Zip; column_header=Avg.; value=73.52

</details>

<a id="ev-095"></a>
### ev-095 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r23-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r23c11=89.93 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `9e84391f21dc2e7a82e4a708a536c635556a2c84c8bf369632af52022e7af177` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=23; column=11; row_header=Sequence length = 32k | RDKV; column_header=Avg.; value=89.93

</details>

<a id="ev-096"></a>
### ev-096 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r24-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r24c11=88.49 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `88d9b29e3a70f72e2e376d77994b7cab61316f70fee2d407903000e4a50f1114` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=24; column=11; row_header=Sequence length = 64k | FullKV; column_header=Avg.; value=88.49

</details>

<a id="ev-097"></a>
### ev-097 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r25-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r25c11=77.92 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `baa400acacef8adec0405f646ff7ca3ad72402ab7680129cad9d933076adef89` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=25; column=11; row_header=Sequence length = 64k | SnapKV; column_header=Avg.; value=77.92

</details>

<a id="ev-098"></a>
### ev-098 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r26-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r26c11=78.73 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `b4e71b677467d8a214e10218993d70a3192ecc723648677ccfe8a83a289c2bb0` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=26; column=11; row_header=Sequence length = 64k | AdaKV; column_header=Avg.; value=78.73

</details>

<a id="ev-099"></a>
### ev-099 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r27-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r27c11=73.46 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `248411a343fe1c08555da9dcf565223d191766c7d5d92d231c5e1ba1b2e6499d` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=27; column=11; row_header=Sequence length = 64k | ThinK; column_header=Avg.; value=73.46

</details>

<a id="ev-100"></a>
### ev-100 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r28-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r28c11=72.82 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `d99afa3ec6ba23fc9ba02d1507a110509ab0de5d03b5084afc4cceb9cda6100a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=28; column=11; row_header=Sequence length = 64k | Snap+Zip; column_header=Avg.; value=72.82

</details>

<a id="ev-101"></a>
### ev-101 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r29-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r29c11=83.20 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `cf09baf88d2f2d48c3413fb1c83851d67f93e41c44431d0502da8cec4e93adfc` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=29; column=11; row_header=Sequence length = 64k | RDKV; column_header=Avg.; value=83.20

</details>

<a id="ev-102"></a>
### ev-102 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r30-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r30c11=79.91 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `b4eb998636c6035810b6d9fd97dd0b193dc8f54db5d875477da68bb95d5effcc` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=30; column=11; row_header=Sequence length = 128k | FullKV; column_header=Avg.; value=79.91

</details>

<a id="ev-103"></a>
### ev-103 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r31-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r31c11=67.17 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `47e1785503cbe631a7f32f98c59b468594dfa22020955b48972f606e6d7f7a98` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=31; column=11; row_header=Sequence length = 128k | SnapKV; column_header=Avg.; value=67.17

</details>

<a id="ev-104"></a>
### ev-104 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r32-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r32c11=64.42 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `3c19ccae07e25e7fe8395e02aa39744892d4efba2a13fabef99813e263e3750a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=32; column=11; row_header=Sequence length = 128k | AdaKV; column_header=Avg.; value=64.42

</details>

<a id="ev-105"></a>
### ev-105 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r33-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r33c11=67.14 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `c3059308f34cfc43c98731f74071396ce23c38db69fc5a087c3db2b37f3b2640` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=33; column=11; row_header=Sequence length = 128k | ThinK; column_header=Avg.; value=67.14

</details>

<a id="ev-106"></a>
### ev-106 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r34-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r34c11=66.55 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `83827e545c394618f37c9468e969ef1b43c9df9ca53f31cb6c93069ae96142c8` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=34; column=11; row_header=Sequence length = 128k | Snap+Zip; column_header=Avg.; value=66.55

</details>

<a id="ev-107"></a>
### ev-107 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:table-09:cell-r35-c11` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `Table 9` |
| 원본 element | `elem-vision-9acae5c4940f1eaeeadb` |
| Text span | `0:1558` |
| Table cell | r35c11=70.28 |
| BBox | `24.00, 66.69, 588.00, 661.74` |
| Content SHA-256 | `3119c93d5cca0857e32c9f52cf9cd862fdf2be77f713b35fdc019cc987225ad9` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 9; row=35; column=11; row_header=Sequence length = 128k | RDKV; column_header=Avg.; value=70.28

</details>

<a id="ev-108"></a>
### ev-108 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | - |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `434871bd3b1a75151473542458e14e1bc869be69f653076a6209c946d3ad346a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12: Prefill overhead breakdown for RDKV on LLaMA-3.1-8B-Instruct at 128K context length
> (A100 64 GB). Percentages are relative to the FullKV prefill baseline.
> Table 12: Prefill overhead breakdown for RDKV on LLaMA-3.1-8B-Instruct at 128K context length
> (A100 64 GB). Percentages are relative to the FullKV prefill baseline.
>
> Component | Time (ms) | % of FullKV Prefill
> FullKV prefill (FA2) | 28 843 | — (baseline)
> Forward path saving | −593 | −2.1%
> wₜ computation | +308 | +1.1%
> w_c computation | +550 | +1.9%
> MCKP bisection | +609 | +2.1%
> TriZone packing | +863 | +3.0%
> Net RDKV overhead | +1,740 | +6.0%
> RDKV TTFT | 30 583 | 106.0%
> cell[0,0] Component
> cell[0,1] Time (ms)
> cell[0,2] % of FullKV Prefill
> cell[1,0] FullKV prefill (FA2)
> cell[1,1] 28 843
> cell[1,2] — (baseline)
> cell[2,0] Forward path saving
> cell[2,1] −593
> cell[2,2] −2.1%
> cell[3,0] wₜ computation
> cell[3,1] +308
> cell[3,2] +1.1%
> cell[4,0] w_c computation
> cell[4,1] +550
> cell[4,2] +1.9%
> cell[5,0] MCKP bisection
> cell[5,1] +609
> cell[5,2] +2.1%
> cell[6,0] TriZone packing
> cell[6,1] +863
> cell[6,2] +3.0%
> cell[7,0] Net RDKV overhead
> cell[7,1] +1,740
> cell[7,2] +6.0%
> cell[8,0] RDKV TTFT
> cell[8,1] 30 583
> cell[8,2] 106.0%
> The table has three columns: Component, Time (ms), and % of FullKV Prefill.
> Net RDKV overhead is explicitly listed as +1,740 ms and +6.0%.
> RDKV TTFT is explicitly listed as 30 583 ms and 106.0%.

</details>

<a id="ev-109"></a>
### ev-109 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r00-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r0c0=Component |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `529f79962bdf1fb2c39e76f49d012083a0dc9cfffc8fba02e767338c2d12970a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=0; column=0; column_header=Component; value=Component

</details>

<a id="ev-110"></a>
### ev-110 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r00-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r0c1=Time (ms) |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `57fcaa4d8483b0c7351246d8d911c5df03bcd2336e11bb78fab651a939dd39c6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=0; column=1; column_header=Time (ms); value=Time (ms)

</details>

<a id="ev-111"></a>
### ev-111 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r00-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r0c2=% of FullKV Prefill |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `24cddda2508424cc3b7cf1573fe9e2bb86ad9a013a8c3e04a0b8a00a704e02bf` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=0; column=2; column_header=% of FullKV Prefill; value=% of FullKV Prefill

</details>

<a id="ev-112"></a>
### ev-112 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r01-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r1c0=FullKV prefill (FA2) |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `2fa653a1fc2097cda897946baeb3f72b9d37b0402636a9524f425138debee315` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=1; column=0; row_header=FullKV prefill (FA2); column_header=Component; value=FullKV prefill (FA2)

</details>

<a id="ev-113"></a>
### ev-113 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r01-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r1c1=28 843 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `1fd8bb4d924c6a0c8e0e949046b17a9d6773b710ebb45faa4a9f021a0c0b32fa` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=1; column=1; row_header=FullKV prefill (FA2); column_header=Time (ms); value=28 843

</details>

<a id="ev-114"></a>
### ev-114 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r01-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r1c2=— (baseline) |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `e6afbd966cdf3d5f9b9b8fd98c83c6731251a207f485f8080de1215aab9deac4` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=1; column=2; row_header=FullKV prefill (FA2); column_header=% of FullKV Prefill; value=— (baseline)

</details>

<a id="ev-115"></a>
### ev-115 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r02-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r2c0=Forward path saving |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `60ce1cd66597f06eab2f62a6fd5551b370da88e8e0cbe20da3bfea90c33a9ba1` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=2; column=0; row_header=Forward path saving; column_header=Component; value=Forward path saving

</details>

<a id="ev-116"></a>
### ev-116 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r02-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r2c1=−593 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `f44cddc5301e08be368306734b3181d700047a7b06a393455592d41230f84cfb` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=2; column=1; row_header=Forward path saving; column_header=Time (ms); value=−593

</details>

<a id="ev-117"></a>
### ev-117 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r02-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r2c2=−2.1% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `a59ebfea4807c35a10cba4d4d898008188a98ec671330d6b121bdfb47e7b928e` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=2; column=2; row_header=Forward path saving; column_header=% of FullKV Prefill; value=−2.1%

</details>

<a id="ev-118"></a>
### ev-118 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r03-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r3c0=wₜ computation |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `a3e9a194f2c690a43b6d6df74d82022df49346677c639fd138047a1c50301749` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=3; column=0; row_header=wₜ computation; column_header=Component; value=wₜ computation

</details>

<a id="ev-119"></a>
### ev-119 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r03-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r3c1=+308 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `665b121f03845f50e4c145324e9d3fc66caa784535b7d67e69fdd215935062b6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=3; column=1; row_header=wₜ computation; column_header=Time (ms); value=+308

</details>

<a id="ev-120"></a>
### ev-120 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r03-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r3c2=+1.1% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `44720911fef67f93ee9fa9fe5dc686eebedeee293becdf09072586b5d4abcf02` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=3; column=2; row_header=wₜ computation; column_header=% of FullKV Prefill; value=+1.1%

</details>

<a id="ev-121"></a>
### ev-121 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r04-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r4c0=w_c computation |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `ba550d9fe7b2a93c804d667a887f8206c2aec1bf1c1edf849e8bc8e6dbfa6009` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=4; column=0; row_header=w_c computation; column_header=Component; value=w_c computation

</details>

<a id="ev-122"></a>
### ev-122 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r04-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r4c1=+550 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `a2a547e1920fa1f84655e2f2a868120e908c7856c5fdc0529479ccef8a753495` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=4; column=1; row_header=w_c computation; column_header=Time (ms); value=+550

</details>

<a id="ev-123"></a>
### ev-123 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r04-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r4c2=+1.9% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `a9010f38b723882ed3919c08e2c2ccddb9f14cc158047ee25d9020ea466f996a` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=4; column=2; row_header=w_c computation; column_header=% of FullKV Prefill; value=+1.9%

</details>

<a id="ev-124"></a>
### ev-124 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r05-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r5c0=MCKP bisection |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `5c398485125ee43be19c83e326044f1233604a9c4d1ded701dac758ae548dbc4` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=5; column=0; row_header=MCKP bisection; column_header=Component; value=MCKP bisection

</details>

<a id="ev-125"></a>
### ev-125 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r05-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r5c1=+609 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `cef1c1c3acd712cd2b1a14670e42d1cac3aba4c69be63431bd56b80493523fc3` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=5; column=1; row_header=MCKP bisection; column_header=Time (ms); value=+609

</details>

<a id="ev-126"></a>
### ev-126 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r05-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r5c2=+2.1% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `dfb30a4c1738ef4263bcdc1686eba41122c3e95c9d3f85d44e72399bcbeb5b02` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=5; column=2; row_header=MCKP bisection; column_header=% of FullKV Prefill; value=+2.1%

</details>

<a id="ev-127"></a>
### ev-127 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r06-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r6c0=TriZone packing |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `79588dd2bae0ee8bf97d4ef6cbcc47c8ae672999454be4be06fafa655d9ccf39` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=6; column=0; row_header=TriZone packing; column_header=Component; value=TriZone packing

</details>

<a id="ev-128"></a>
### ev-128 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r06-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r6c1=+863 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `0d069288c72c7f77bcb3c908896f50f3fb708201a165c31e759d2903fc419dd1` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=6; column=1; row_header=TriZone packing; column_header=Time (ms); value=+863

</details>

<a id="ev-129"></a>
### ev-129 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r06-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r6c2=+3.0% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `b69b602734274352bce16ec5e7e661c060b2fe8817116ed1588b7a1d52aa77b6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=6; column=2; row_header=TriZone packing; column_header=% of FullKV Prefill; value=+3.0%

</details>

<a id="ev-130"></a>
### ev-130 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r07-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r7c0=Net RDKV overhead |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `ce6226914622263ccb12f66ea39402851f260c26499e758d31cd4202ea21740b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=7; column=0; row_header=Net RDKV overhead; column_header=Component; value=Net RDKV overhead

</details>

<a id="ev-131"></a>
### ev-131 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r07-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r7c1=+1,740 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `e0ec15f072da1dadd340fa920fa8eafd070276eefc71c209301eab0bedbc3f5f` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=7; column=1; row_header=Net RDKV overhead; column_header=Time (ms); value=+1,740

</details>

<a id="ev-132"></a>
### ev-132 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r07-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r7c2=+6.0% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `404179ae577ff0aa93e8f09fc849c94b947559527bfedc920d5265106f07044b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=7; column=2; row_header=Net RDKV overhead; column_header=% of FullKV Prefill; value=+6.0%

</details>

<a id="ev-133"></a>
### ev-133 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r08-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r8c0=RDKV TTFT |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `2e6a1d2ee4aa6ca6e062b734e0b08ad7e88e1d391df315ff28585d7e415d5d3e` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=8; column=0; row_header=RDKV TTFT; column_header=Component; value=RDKV TTFT

</details>

<a id="ev-134"></a>
### ev-134 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r08-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r8c1=30 583 |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `d11697d3c250d2e09f6f2b734f510cda73b5c11d9878695020d820fb2818f935` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=8; column=1; row_header=RDKV TTFT; column_header=Time (ms); value=30 583

</details>

<a id="ev-135"></a>
### ev-135 — `2605.08317-25836a41` p.23

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0023:table-12:cell-r08-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `vision` |
| 물리·인쇄 페이지 | `23` / `23` |
| 절 | RDKV |
| Object | `Table 12` |
| 원본 element | `elem-vision-c369fd103745ea533661` |
| Text span | `0:1377` |
| Table cell | r8c2=106.0% |
| BBox | `24.00, 378.12, 588.00, 780.00` |
| Content SHA-256 | `bef48fbd89676d9587d2b75f5a48bd6e04d1d16a380a7396b054eca62ee5b3d2` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 12; row=8; column=2; row_header=RDKV TTFT; column_header=% of FullKV Prefill; value=106.0%

</details>

<a id="ev-136"></a>
### ev-136 — `2605.08317-25836a41` p.7

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0007:table-01:span-00000-00252` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `7` / `7` |
| 절 | Experiments |
| Object | `Table 1` |
| 원본 element | `elem-2605.08317-25836a41-p0007-caption-000-b65939678a8d` |
| Text span | `0:252` |
| Table cell | - |
| BBox | `107.69, 78.98, 505.74, 110.84` |
| Content SHA-256 | `11ad156415f30706f372f9d966adcc3c77ca5118a0eb3df1c04245cd98112536` |

<details>
<summary>원문 스니펫 보기</summary>

> Table 1: Performance on 16 LongBench [47] datasets for LLaMA-3.1-8B-Instruct across cache
> budgets Btotal ∈{64L, 128L, 256L, 512L, 1024L}. Snap+Zip denotes SnapKV [11]+ZipCache [14].
> The best result in each row is in bold; the second-best is underlined.

</details>

<a id="ev-137"></a>
### ev-137 — `2605.08317-25836a41` p.16

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0016:elem-2605.08317-25836a41-p0016-text-group-047-5ce58404e337:span-00000-01621` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `16` / `16` |
| 절 | Conclusion |
| Object | `elem-2605.08317-25836a41-p0016-text-group-047-5ce58404e337` |
| 원본 element | `elem-2605.08317-25836a41-p0016-text-group-047-5ce58404e337` |
| Text span | `0:1621` |
| Table cell | - |
| BBox | `107.69, 521.44, 505.65, 752.30` |
| Content SHA-256 | `e8ea815a6047811fd9a3d3ad69f1ea9758ebf9100fd4b8da41c8eeffdd5f6378` |

<details>
<summary>원문 스니펫 보기</summary>

> In this section, we provide comprehensive experimental results on LongBench [47], a benchmark
> focused on long-context understanding with 16 tasks spanning single-document QA, multi-document
> QA, summarization, few-shot learning, synthetic retrieval, and code completion. We perform
> detailed evaluations with cache budgets ranging from 64L to 1024L on four additional models
> beyond the primary LLaMA-3.1-8B-Instruct reported in Sec. 4.1: Mistral-7B-Instruct-v0.3 [43] and
> Qwen3-4B [44] to test cross-architecture generality, and LLaMA-2-13B-Chat [45] and Qwen2.5-
> 72B-Instruct [46] (2-GPU tensor parallelism) to test cross-scale generality. All methods share the
> same probe configuration (Sw = 32, w = 5) so that any performance difference is attributable to the
> indicator and allocation, not the probe geometry.
>
> Tables 6 to 8 present the detailed per-task scores. Overall, RDKV achieves the highest average at
> every (model, budget) combination—without architecture-specific tuning. The advantage is largest
> under aggressive compression: at Btotal = 64L, RDKV leads the strongest baseline by 1.5/5.5/2.7
> points on Mistral-7B/Qwen3-4B/LLaMA-3.1-8B, because water-filling retains moderate-importance
> tokens at low bit-width rather than evicting them entirely. At Btotal = 1024L it recovers 98.6–99.4%
> of FullKV across models; on the two larger models (LLaMA-2-13B, Qwen2.5-72B) the recovery
> reaches 99.5–99.6% already at Btotal = 512L. The consistency across architectures and scales
> suggests that the distortion weights (Sec. 3) capture a model-agnostic signal, enabling the allocation
> to transfer without modification.
>
> 16

</details>

<a id="ev-138"></a>
### ev-138 — `2605.08317-25836a41` p.22

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0022:elem-2605.08317-25836a41-p0022-text-group-078-817ae200738c:span-00000-01724` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `22` / `22` |
| 절 | RDKV |
| Object | `elem-2605.08317-25836a41-p0022-text-group-078-817ae200738c` |
| 원본 element | `elem-2605.08317-25836a41-p0022-text-group-078-817ae200738c` |
| Text span | `0:1724` |
| Table cell | - |
| BBox | `107.64, 445.69, 505.25, 752.30` |
| Content SHA-256 | `7e513e0458f30f894ecfcad7c24d5ce9f137cfe1a9792dc6edd0d867ef47380d` |

<details>
<summary>원문 스니펫 보기</summary>

> SnapKV
> 100.00
> 94.80
> 89.80
> 98.60
> 96.20
> 13.00
> 98.15
> 94.15
> 89.80
> 2.64
> 80.00 77.92
> AdaKV
> 100.00
> 95.40
> 92.60
> 98.60
> 94.40
> 21.80
> 98.50
> 93.85
> 91.84
> 2.28
> 76.73 78.73
> ThinK
> 100.00
> 97.00
> 70.40
> 99.00
> 83.40
> 5.20
> 98.45
> 94.00
> 90.80
> 2.14
> 67.67 73.46
> Snap+Zip
> 99.60
> 100.00
> 94.60
> 99.00
> 42.60
> 0.80
> 98.30
> 92.10
> 84.00
> 4.66
> 85.33 72.82
>
> 100.00
> 99.20
> 99.80
> 99.40
> 95.40
> 56.40
> 99.45
> 94.45
> 94.44
> 3.58
> 73.13 83.20
>
> Sequence length = 128k
>
> FullKV
> 100.00
> 99.40
> 99.80
> 97.60
> 88.60
> 66.20
> 98.45
> 90.65
> 66.56
> 0.00
> 71.80 79.91
>
> SnapKV
> 100.00
> 99.20
> 50.80
> 97.20
> 82.20
> 3.20
> 97.10
> 90.25
> 66.60
> 0.12
> 52.20 67.17
> AdaKV
> 100.00
> 99.20
> 47.80
> 97.20
> 74.40
> 5.40
> 97.15
> 89.15
> 63.16
> 0.10
> 35.00 64.42
> ThinK
> 100.00
> 99.20
> 61.80
> 97.00
> 81.60
> 2.00
> 96.10
> 88.70
> 62.96
> 0.18
> 49.00 67.14
> Snap+Zip
> 100.00
> 96.20
> 85.40
> 95.00
> 49.00
> 1.80
> 92.05
> 81.30
> 67.32
> 0.06
> 63.87 66.55
>
> 100.00
> 99.00
> 93.80
> 96.80
> 81.60
> 9.00
> 96.45
> 88.50
> 63.12
> 0.06
> 44.73 70.28
>
> Tab. 13 reports the 16-task LongBench average. At every budget level the equal split rK = 0.5
> achieves the highest score. The margins are small (≤0.63 points), indicating that the allocation is
> robust to moderate shifts in the K/V ratio. Shifting more budget toward K (rK = 0.6) consistently
> hurts: the V cache carries per-token information that directly scales the attention output (Prop. 3.1),
> so starving it degrades quality faster than under-provisioning per-channel K precision. Conversely,
> a mild reduction of K budget (rK = 0.4) is largely absorbed because the per-channel distortion
> weight wc (Prop. 3.2) concentrates on a small subset of outlier channels; most channels tolerate
> lower bit-widths with negligible error. The symmetric optimum rK = 0.5 balances these two effects,
> justifying the equal split adopted throughout the paper.
>
> 22

</details>

<a id="ev-139"></a>
### ev-139 — `2605.08317-25836a41` p.6

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2605.08317-25836a41@25836a419005:p0006:elem-2605.08317-25836a41-p0006-text-group-018-49c317014893:span-00000-00998` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `6` / `6` |
| 절 | Experiments |
| Object | `elem-2605.08317-25836a41-p0006-text-group-018-49c317014893` |
| 원본 element | `elem-2605.08317-25836a41-p0006-text-group-018-49c317014893` |
| Text span | `0:998` |
| Table cell | - |
| BBox | `107.25, 592.33, 505.66, 752.30` |
| Content SHA-256 | `1e74fc93852a5278fafcc93c3d8e2c70b64dfa48e5ab8f2ab145b2c04c98e89d` |

<details>
<summary>원문 스니펫 보기</summary>

> Models. We primarily evaluate on LLaMA-3.1-8B-Instruct [42]. Cross-architecture results (Mistral-
> 7B-Instruct-v0.3 [43], Qwen3-4B [44]) and cross-scale results (LLaMA2-13B-Chat [45], Qwen2.5-
> 72B-Instruct [46]) are listed in Sec. D.
>
> Baselines. We compare against four budget-driven methods. SnapKV [11] scores tokens by attention
> within a recent observation window and retains the top-k per head. Ada-SnapKV [26] (hereafter
> AdaKV) extends this with adaptive per-head budget allocation. ThinK [12] applies pruning at the
> channel level of the K cache rather than the token level (paired with SnapKV). SnapKV+ZipCache [11,
> 14] combines token eviction with post-hoc quantization of the retained cache.
>
> Benchmarks. We evaluate on LongBench [47] (16 tasks covering 6 different task categories), Needle-
> in-a-Haystack [48] (single-fact retrieval at varying depths), RULER [49] (11 retrieval and reasoning
> tasks from 4K to 128K), and InfiniteBench [50] (10 tasks with context lengths up to 2M tokens).
>
> 6

</details>

<a id="ev-140"></a>
### ev-140 — `2607.27187-d6a67efd` p.1

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0001:elem-2607.27187-d6a67efd-p0001-text-group-000-af33cc9e8fbe:span-00000-01462` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `1` / `1` |
| 절 | - |
| Object | `elem-2607.27187-d6a67efd-p0001-text-group-000-af33cc9e8fbe` |
| 원본 element | `elem-2607.27187-d6a67efd-p0001-text-group-000-af33cc9e8fbe` |
| Text span | `0:1462` |
| Table cell | - |
| BBox | `45.28, 54.90, 571.78, 395.81` |
| Content SHA-256 | `a28c16e4d06877eb9e9438d9b0852ca8dfb6f8b4841de878fd8d02ee24d271f9` |

<details>
<summary>원문 스니펫 보기</summary>

> A Photonic-CXL Memory Appliance for Scalable KV
>
> Cache Management in LLM Inference
>
> Jing Ding
> Machine Learning
> Marvell Technology
>
> Yash Nishant
> Machine Learning
> Marvell Technology
>
> Chandrish Ambati
> Machine Learning
> Marvell Technology
>
> Jyothsna Kamati
> Design Verification
> Marvell Technology
>
> Santa Clara, USA
> jingd@marvell.com
>
> Santa Clara, USA
> ynishant@marvell.com
>
> Santa Clara, USA
> cambati@marvell.com
>
> Santa Clara, USA
> jkamati@marvell.com
>
> Trung Diep
> Machine Learning
> Marvell Technology
>
> Santa Clara, USA
> trungd@marvell.com
>
> easily exceeds 10,000 tokens, with storage of ~3.3 GB per user.
> With 3.5 billion daily active users at Meta and 1.3 million GPUs
> in datacenter infrastructures, each GPU would require 8.9 TB
> for serving all users.
>
> Abstract— LLM inference at scale faces a memory wall: the
> KV cache demands tens of terabytes at hundreds of gigabytes per
> second, yet no current memory tier delivers both at once.
> Characterization across multi-generation GPU systems with
> various LLaMA models shows host memory retrieval achieves up
> to 100x speedup over re-computation but supports only tens of
> concurrent
> long-context
> users.
> Electrical
> CXL
> pooling
> theoretically bridges this gap, but switch latency, cable reach
> limits, and power-scaling issues prevent practical TB-scale
> deployments. We present the Marvell® Photonic Fabric™ (PF™)
> Memory Appliance, a photonic-CXL hybrid architecture
> replacing electrical switches with a passive fiber shuffle to deliver

</details>

<a id="ev-141"></a>
### ev-141 — `2607.27187-d6a67efd` p.10

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0010:elem-2607.27187-d6a67efd-p0010-text-group-026-37aaf9c29c0e:span-00000-02701` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `10` / `10` |
| 절 | 2.0 switched memory pool (Beluga), measured via Intel MLC. |
| Object | `elem-2607.27187-d6a67efd-p0010-text-group-026-37aaf9c29c0e` |
| 원본 element | `elem-2607.27187-d6a67efd-p0010-text-group-026-37aaf9c29c0e` |
| Text span | `0:2701` |
| Table cell | - |
| BBox | `45.28, 348.71, 569.47, 673.63` |
| Content SHA-256 | `7621138696661c5aed9003c612bddcd16711ce549cb690cf3fd62b53aa4dd74d` |

<details>
<summary>원문 스니펫 보기</summary>

> The fundamental electrical CXL constraints are well-
> documented: copper cables limited to ≤2 m, 50–70 ns per switch
> hop, and power-hungry retimers for distance extension. Hybrid
> approaches like Rcmp [39] (CXL intra-rack + RDMA inter-
> rack) and DFabric [40] work around but do not solve these
> constraints. The PF Memory Appliance's passive fiber shuffle
> directly addresses all three: extending reach to 100+ m,
> eliminating switch-hop latency, and reducing interconnect
> power.
>
> IX. CONCLUSION
>
> We presented a comprehensive characterization of KV cache
> retrieval across the memory hierarchy to reveal a fundamental
> capacity-bandwidth gap in current systems. Host memory
> achieves up to 100× speedup over re-computation but supports
> only tens of concurrent long-context users, while SSD storage
> scales in capacity but delivers at most 9.7× speedup. Electrical
> CXL memory pooling can theoretically bridge this gap but faces
> switch latency, reach, and power constraints that prevent
> practical TB-scale deployments.
>
> C. Photonic Interconnects in Datacenter
>
> Co-packaged optics has reached production maturity, driven
> by the need to eliminate DSP latency (~100–150 ns) and power
> (~15–20 pJ/bit) from pluggable transceivers. Broadcom's
> Tomahawk 6 ships with integrated optical engines at ~5 pJ/bit
> [41]. Intel's OCI achieves 4 Tbps at 5 pJ/bit with 100 m reach
> [43], explicitly targeting memory disaggregation.
>
> The Photonic Fabric Memory Appliance addresses these
> limitations through a passive optical fiber shuffle that replaces
> electrical CXL switches, delivering 32 TB of shared DDR5
> memory across 16 hosts at 128 GB/s per host with a switch-free
> full-mesh topology. Emulation results demonstrate over 50%
> latency reduction compared to electrical CXL switched pools,
> with full-link bandwidth utilization across diverse access
> patterns. Serving simulations demonstrate that PF Memory
> Appliance
> eliminates
> capacity-induced
> eviction
> cliffs,
> sustaining flat TTFT as workload scales while baseline
> configurations degrade rapidly once their memory capacity is
> exceeded. At 300 concurrent multi-turn conversations, the PF
> Memory Appliance achieves 6.6× lower TTFT than the baseline
> when the baseline's memory is fully exhausted. These results
> demonstrate that the photonic-CXL memory pooling effectively
> closes the capacity-bandwidth gap for production-scale LLM
> serving.
>
> GeSi electro-absorption modulators are emerging as the
> preferred CPO technology. Recent demonstrations include >100
> GHz bandwidth at sub-100 μm active lengths [43] and 400 Gb/s
> per lane on 300 mm silicon photonics [44]. EAMs avoid MRR
> thermal stabilization overhead and footprint penalties—the
> approach used in the PF Memory Module [17, 21].

</details>

<a id="ev-142"></a>
### ev-142 — `2607.27187-d6a67efd` p.4

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0004:elem-2607.27187-d6a67efd-p0004-text-group-009-2667c614567e:span-00000-01140` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `4` / `4` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `elem-2607.27187-d6a67efd-p0004-text-group-009-2667c614567e` |
| 원본 element | `elem-2607.27187-d6a67efd-p0004-text-group-009-2667c614567e` |
| Text span | `0:1140` |
| Table cell | - |
| BBox | `45.28, 544.01, 569.38, 699.88` |
| Content SHA-256 | `8131a461734e477f22322d6250565a6e3f6b138449eb26aec8985f41a91ab3c0` |

<details>
<summary>원문 스니펫 보기</summary>

> CXL shared memory. CXL Type-3 devices provide byte-
> addressable memory accessible by multiple hosts via load/store
> semantics, without involving the network stack [14]. Recent
> work demonstrates using CXL as both a KV transfer substrate
> and a rack-wide prefix cache. TraCT [15] maps a CXL device
> into all servers via DAX, registers it with CUDA for GPU DMA,
> and maintains a shared prefix hash table with two-tier software
> locks and explicit cache-line flushes for cross-node consistency
> on non-coherent memory. Beluga [16] scales this to 16 hosts and
>
> Scaling electrical CXL to tens of terabytes requires switch
> hierarchies that sacrifice the very latency and bandwidth
> advantages motivating CXL adoption. What is needed is an
> interconnect that preserves CXL's byte-addressable load/store
> memory semantics while eliminating electrical switching from
> the data path. Section III presents the PF Memory Appliance,
> which replaces the electrical switch fabric with a passive optical
> fiber shuffle to deliver 32 TB of shared CXL memory across 16
> hosts without intermediate switching, distance constraints, or
> contention-induced latency variability.

</details>

<a id="ev-143"></a>
### ev-143 — `2607.27187-d6a67efd` p.2

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0002:elem-2607.27187-d6a67efd-p0002-text-group-003-cf1cb47304a1:span-00000-02814` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `2` / `2` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `elem-2607.27187-d6a67efd-p0002-text-group-003-cf1cb47304a1` |
| 원본 element | `elem-2607.27187-d6a67efd-p0002-text-group-003-cf1cb47304a1` |
| Text span | `0:2814` |
| Table cell | - |
| BBox | `45.28, 364.46, 569.48, 712.63` |
| Content SHA-256 | `3f99fcea85a3c596ca9f28280bb1b4145723d6663d36a9a269e96612b15a342d` |

<details>
<summary>원문 스니펫 보기</summary>

> Phase 1: Input creation and initial cache population. We
> generate test inputs with configurable batch sizes (1–32) and
> prompt lengths (1K–4M tokens), submit the initial request to the
> model for prefill computation, during which the model generates
> and stores the complete KV cache.
>
> Phase 2: Cache offloading. For the host memory path, cache
> is offloaded to system DRAM for fast retrieval with limited
> capacity. For the disk storage path, cache persisted to SSD for
> large capacity with slower retrieval.
>
> To address this gap, we present the Marvell® Photonic
> Fabric™ (PF™) Memory Appliance, a novel photonic fabric-
> CXL hybrid architecture. By replacing electrical switches with
> a passive optical fiber shuffle [17], the PF Memory Appliance
> delivers 32 TB capacity with 128 GB/s unidirectional bandwidth
> per host, enabling up to 16 hosts to share pooled memory
> without interconnect bottlenecks. We evaluate the PF Memory
> Appliance design through emulation on the Siemens Veloce
> Strato-M platform, demonstrating over 50% latency reduction
> compared to electrical CXL switched memory pools [16]. End-
> to-end serving simulations confirm that PF Memory Appliance
> eliminates KV cache eviction cliffs, improving TTFT by 6.6×
> for multi-turn conversations workload.
>
> Phase 3: Retrieval performance measurement. We measure
> memory retrieval time (Tmemory) to load KV cache from host
> DRAM, disk retrieval time (Tdisk) to load KV cache from SSD,
> and a no-cache baseline (Tcompute) for full KV re-computation.
> The speedup of retrieving KV cache from host memory is
> calculated as Tcompute / Tmemory, while the speedup from SSD is
> Tcompute / Tdisk.
>
> The benchmark evaluates five model variants: LLaMA-8B
> (single GPU), LLaMA-70B (2×H200, TP=2), LLaMA-405B
> (8×H200, TP=8, BF16), and extended-context MoE variants
> LLaMA Maverick and LLaMA Scout (8×H200, TP=8, BF16).
>
> Our contributions are as follows:
>
> An empirical characterization of the memory wall in LLM
> inference, quantifying the capacity-bandwidth gap across GPU
> HBM, host DRAM, and SSD tiers.
>
> 2) Experimental Setup
> We run vLLM with LMCache enabled to offload and
> retrieve KV blocks across requests. We compare tier
> configurations that offload KV blocks to host DRAM and local
> storage when HBM is insufficient. We report time-to-first-token
> (TTFT) as the primary user-facing latency metric.
>
> The PF Memory Appliance architecture, a photonic-CXL
> hybrid achieving 32 TB shared memory through a switch-free
> optical fiber shuffle, with bandwidth and latency evaluated
> through hardware emulation.
>
> Our evaluation uses a local A100 server and cloud instances
> on Runpod with H100/H200 GPUs. The A100 testbed includes
> one NVIDIA A100 (80 GB HBM2e) connected to a dual-socket
>
> End-to-end serving evaluation demonstrating that PF
> Memory Appliance-augmented systems sustain flat TTFT as

</details>

<a id="ev-144"></a>
### ev-144 — `2607.27187-d6a67efd` p.10

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0010:elem-2607.27187-d6a67efd-p0010-text-group-025-e3f4941f8530:span-00000-02834` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `10` / `10` |
| 절 | 2.0 switched memory pool (Beluga), measured via Intel MLC. |
| Object | `elem-2607.27187-d6a67efd-p0010-text-group-025-e3f4941f8530` |
| 원본 element | `elem-2607.27187-d6a67efd-p0010-text-group-025-e3f4941f8530` |
| Text span | `0:2834` |
| Table cell | - |
| BBox | `45.28, 54.12, 569.48, 359.78` |
| Content SHA-256 | `18b20251fb964c5f0cf27308fa33bdba0718db5876e2afcbd3f74c5426010738` |

<details>
<summary>원문 스니펫 보기</summary>

> CacheGen [30] compresses KV cache into 3.5–4.3× smaller
> bitstreams for network streaming. InfiniGen [31] speculatively
> prefetches critical KV entries from CPU memory. KVQuant
> [32] provides sub-4-bit quantization enabling 10M+ token
> contexts.
> FlashAttention
> [33,
> 34]
> optimizes
> attention
> computation by minimizing GPU SRAM↔HBM data
> movement. These optimizations are orthogonal to memory
> pooling and compose directly with PF Memory Appliance.
>
> VIII. LIMITATIONS AND FUTURE WORK
>
> This study has several limitations. First, our empirical
> characterization is focused on disk storage experiments on the
> 8B and 405B models; more characterization of the MoE
> variants, including new architectures from DeepSeek and Qwen
> models, will be future work. Second, the PF Memory Appliance
> performance projections in the serving evaluation are derived
> from
> emulation-characterized
> bandwidth
> and
> latency
> parameters fed into the LLMServingSim framework; validation
> on the physical PF Memory Appliance hardware with end-to-
> end inference workloads remains pending.
>
> The common limitation is that per-node memory capacity
> forces multi-tier caching with escalating latency penalties, and
> cross-node
> sharing
> requires
> network
> transfers
> with
> unpredictable overhead—the gap the PF Memory Appliance
> addresses.
>
> Future work will address these gaps through several
> directions. We plan to conduct end-to-end validation on the PF
> Memory Appliance hardware once it becomes available later
> this year, including the integration with the vLLM and SGLang
> connectors described in Section V. We will extend the serving
> evaluation to multi-GPU, multi-host configurations to quantify
> the benefits of the PF Memory Appliance's shared memory pool
> for
> cross-host
> KV
> reuse
> in
> disaggregated
> inference
> deployments. Cost-benefit analysis comparing PF Memory
> Appliance against alternative scaling approaches—including
> CXL switch hierarchies, active optical interconnects, and simply
> provisioning additional servers—will provide additional
> deployment guidance. Finally, we plan to explore PF Memory
> Appliance's applicability beyond KV cache management,
> including model weight sharing across hosts and checkpoint
> storage for fault-tolerant serving.
>
> B. CXL Memory Disaggregation
>
> Pond [30] showed that 8–16 socket CXL pools capture most
> DRAM savings but estimated 70–90 ns overhead rising to >180
> ns at rack scale. DirectCXL [35] demonstrated 8.3× lower
> latency than RDMA via load/store semantics. TPP [36]
> contributed transparent page placement for tiered CXL memory,
> now merged into the Linux kernel. Melody [37] found
> significant latency instability across commercial CXL devices,
> with p99.99 tail latency exceeding 700 ns–1 μs. COAXIAL [38]
> proposed replacing all DDR with CXL for 1.39× average
> speedup. Seo et al. [25] explored CXL-attached memory for
> long-context LLM fine-tuning.

</details>

<a id="ev-145"></a>
### ev-145 — `2607.27187-d6a67efd` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0005:elem-2607.27187-d6a67efd-p0005-text-group-010-f0b0912faa3e:span-00000-00848` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | 8 TB capacity via a CXL 2.0 switch, replacing network RPCs |
| Object | `elem-2607.27187-d6a67efd-p0005-text-group-010-f0b0912faa3e` |
| 원본 element | `elem-2607.27187-d6a67efd-p0005-text-group-010-f0b0912faa3e` |
| Text span | `0:848` |
| Table cell | - |
| BBox | `45.28, 54.12, 569.41, 168.21` |
| Content SHA-256 | `33e3a1cef4ecaffce334ac2ca95359833ef287224934a6f7637b0156b5fc3e12` |

<details>
<summary>원문 스니펫 보기</summary>

> shuffle provides dedicated optical paths between every host-
> memory pair. This topology eliminates switch-induced latency
> entirely while enabling truly concurrent access—all 16 hosts can
> simultaneously access different memory modules without
> contention in the interconnect fabric.
>
> III. PHOTONIC FABRIC MEMORY APPLIANCE ARCHITECTURE
>
> We introduce the Photonic Fabric Memory Appliance: a
> memory disaggregation platform that combines the capacity
> advantages of pooled DDR5 with the bandwidth characteristics
> of HBM, while leveraging photonic interconnects to eliminate
> the switching bottlenecks and reach limitations of electrical
> CXL architectures. Photonics [17] can replace the electrical
> switching fabric entirely, providing all-to-all connectivity
> without intermediate switches while maintaining CXL protocol
> compatibility at the host interface.

</details>

<a id="ev-146"></a>
### ev-146 — `2607.27187-d6a67efd` p.7

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0007:elem-2607.27187-d6a67efd-p0007-text-group-020-cabf47709270:span-00000-01088` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `7` / `7` |
| 절 | 2.0 switched memory pool (Beluga), measured via Intel MLC. |
| Object | `elem-2607.27187-d6a67efd-p0007-text-group-020-cabf47709270` |
| 원본 element | `elem-2607.27187-d6a67efd-p0007-text-group-020-cabf47709270` |
| Text span | `0:1088` |
| Table cell | - |
| BBox | `45.28, 563.76, 569.46, 707.88` |
| Content SHA-256 | `59fcc891ef103b51282c9f6525d4ee3f499682c22fe8d995455a0c023b46ed93` |

<details>
<summary>원문 스니펫 보기</summary>

> This latency comprises CXL protocol processing at the host,
> switch forwarding delay, and DDR5 device access. In contrast,
> our characterization of the CXL pod using PF Memory
> Appliance yields an average 64-byte access from memory pool
> to host results in a latency of 350 ns, representing a more than
> 50% reduction.
>
> We evaluate latency under two workload conditions. The
> first configuration, referred to as idle latency, issues a single
> write transaction followed by a read, capturing system
> performance under minimal load. The second configuration,
> referred to as loaded latency, generates a sequence of read and
> write operations, offset by 64 bytes to remove any cache
> considerations, that exceeds the implemented CXL credit
> exchange limits, thereby stressing the protocol pipeline and
> exposing contention effects.
>
> V. SOFTWARE INTEGRATION
> This section describes how our optically connected CXL
> memory appliance is discovered and enumerated with possible
> integration paths in the ML inference software stack, from OS-
> level device bring-up through framework-specific KV cache
> management.

</details>

<a id="ev-147"></a>
### ev-147 — `2607.27187-d6a67efd` p.1

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0001:elem-2607.27187-d6a67efd-p0001-text-group-001-9bb3b434ba81:span-00000-02992` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `1` / `1` |
| 절 | 32 TB shared memory across 16 hosts via a switch-free full- |
| Object | `elem-2607.27187-d6a67efd-p0001-text-group-001-9bb3b434ba81` |
| 원본 element | `elem-2607.27187-d6a67efd-p0001-text-group-001-9bb3b434ba81` |
| Text span | `0:2992` |
| Table cell | - |
| BBox | `45.28, 321.44, 569.47, 699.38` |
| Content SHA-256 | `d28693dd28e876ecf87b6e6707fd81270752211709093d629fe54f3dfea75a80` |

<details>
<summary>원문 스니펫 보기</summary>

> Enterprise applications at scale face even more severe
> memory challenges due to their inherently long contexts and
> high concurrency requirements. Legal document analysis
> systems must process extensive contracts alongside vast
> regulatory frameworks and case precedents, with each session
> requiring tens of gigabytes of KV cache memory. Medical
> diagnosis platforms combine complete patient histories with
> comprehensive medical knowledge bases and clinical
> guidelines, quickly exhausting available GPU memory when
> serving
> multiple
> healthcare
> providers
> simultaneously.
> Educational platforms delivering personalized tutoring must
> maintain extensive context including curriculum materials,
> learning history, and performance analytics for thousands of
> concurrent students, pushing memory requirements into the
> multi-terabyte range. These domain-specific applications
> demonstrate that KV cache management is a fundamental
> barrier to deploying LLMs in enterprise settings where long
> context and high concurrency are non-negotiable requirements.
>
> crossbar topology. Emulation results demonstrate over 50 percent
> latency reduction versus electrical CXL pools. Simulation results
> show that the PF Memory Appliance eliminates cache eviction
> cliffs by improving time-to-first-token by 6.6x for multi-turn
> conversations workloads.
>
> Keywords— photonic interconnects, CXL, LLM inference, KV
> cache, datacenter architecture
>
> I. INTRODUCTION
>
> The rapid deployment of Large Language Models (LLMs)
> in production systems has created unprecedented challenges in
> memory management, particularly for Key-Value (KV) cache
> placement. As models scale to support context windows
> exceeding 1 million tokens—exemplified by Claude Opus,
> Gemini 3, GPT-5.4, LLaMA 4 Maverick [1, 2, 3, 4]—the
> memory requirements for KV cache have become a critical
> bottleneck in achieving cost-effective and performant inference
> at scale.
>
> Current inference frameworks employ hierarchical memory
> management to address these challenges. NVIDIA's Dynamo
> [5], vLLM [6] with LMCache [7] integration, and SGLang
> (HiCache) [8] implement multi-tier caching strategies spanning
> GPU HBM, host DRAM, local SSDs, and network-attached
> storage. While host memory offloading effectively preserves
> GPU compute resources and accelerates inference for long-
> context workloads, it faces fundamental capacity constraints.
> Modern servers equipped with up to 2 TB of DRAM can support
> only a limited number of active users before exhausting
> available memory. SSD-based caching offers virtually unlimited
> capacity but introduces a critical bandwidth bottleneck—10 to
> 15× lower than CPU-to-GPU bandwidth. Consequently, loading
> KV cache from SSDs can be even slower than recomputing it
> entirely, making it viable mostly for offline processing scenarios
> where latency sensitivity is not critical.
>
> Consider a LLaMA 70B parameter model serving enterprise
> applications. For each token in the context, the KV cache
> requires approximately 328KB (assuming BF16 precision with

</details>

<a id="ev-148"></a>
### ev-148 — `2607.27187-d6a67efd` p.2

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0002:elem-2607.27187-d6a67efd-p0002-text-group-002-9023707fda56:span-00000-03257` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `2` / `2` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `elem-2607.27187-d6a67efd-p0002-text-group-002-9023707fda56` |
| 원본 element | `elem-2607.27187-d6a67efd-p0002-text-group-002-9023707fda56` |
| Text span | `0:3257` |
| Table cell | - |
| BBox | `45.28, 54.12, 569.47, 420.78` |
| Content SHA-256 | `d544d890e3b340ceee6696f96483d6f5394e791faa463f0c821cb16390b06541` |

<details>
<summary>원문 스니펫 보기</summary>

> Meanwhile, disaggregated inference architectures—which
> separate the compute-bound prefill phase from the memory-
> bandwidth-bound decode phase onto distinct GPU workers [9,
> 10, 11]—further exacerbate the data movement challenge. KV
> tensors produced during prefill must be delivered to decode
> workers before token generation can begin, and this transfer
> latency increasingly dominates time-to-first-token (TTFT) at
> long context lengths. Existing transfer mechanisms—from
> CPU-driven RDMA to GPUDirect RDMA [12] to tiered KV
> offloading via NIXL [13]—each leave components on the
> critical path that limit throughput and introduce latency
> variability. CXL shared memory has emerged as a promising
> alternative, enabling byte-addressable access across multiple
> hosts without involving the network stack [14]. Recent work
> including TraCT [15] and Beluga [16] demonstrates CXL as
> both a KV transfer substrate and a rack-wide prefix cache.
> However, electrical CXL deployments face fundamental scaling
> constraints: switch-induced latency of 70–500 ns per hop, multi-
> meter cable reach limits requiring power-hungry retimers, and
> super-linear power scaling that prevents practical TB-scale
> memory pooling.
>
> workload scales to 300 concurrent conversations, achieving
> 6.6× improvement over eviction-degraded baselines.
>
> The remainder of this paper is organized as follows. Section
> II provides background on our empirical characterization of the
> memory wall and disaggregated inference transfer mechanisms.
> Section III introduces the PF Memory Appliance architecture.
> Section IV presents the emulation methodology and hardware
> evaluation results. Section V describes software integration with
> production inference frameworks. Section VI evaluates end-to-
> end serving performance with simulations. Section VII
> discusses related work. Section VIII addresses limitations and
> future work. Section IX concludes.
>
> II. BACKGROUND AND MOTIVATION
>
> A. Empirical Characterization of the Memory Wall
>
> To quantify the capacity-bandwidth gap and establish design
> requirements for next-generation memory architectures, we
> conduct a systematic characterization of KV cache retrieval
> performance across the memory hierarchy. Our evaluation spans
> A100, H100, and H200 GPU systems with models from 8B to
> 405B parameters and contexts up to 4M tokens.
>
> In this paper, we present a comprehensive characterization
> of KV cache retrieval efficiency across the memory hierarchy,
> evaluating offloading across A100, H100, and H200 systems
> with models from 8B to 405B parameters and contexts up to 4M
> tokens using repeated request. Our findings reveal that retrieving
> KV cache from host memory achieves up to 100× speedup over
> GPU re-computation but is severely capacity-constrained, while
> retrieving KV cache from SSD delivers limited speedups
> (maximum 9.7×) due to bandwidth bottlenecks. These results
> quantify the critical requirement: tens of terabytes of capacity at
> over 100 GB/s bandwidth—capabilities that current systems
> cannot simultaneously deliver.
>
> 1) Repeated Request Benchmark
> The benchmark isolates KV cache retrieval performance by
> measuring load latency under ideal conditions (100% cache hit
> rate) with identical repeated requests. The experimental
> workflow consists of three phases:

</details>

<a id="ev-149"></a>
### ev-149 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | - |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `6ce9ad853a03eb25dee46e3f53f8bb76997e5076d2959e35690a16e701de33f1` |

<details>
<summary>원문 스니펫 보기</summary>

> | Model | Platform | Host Memory | Disk Storage |
> | --- | --- | --- | --- |
> | LLaMA-8B | 1×A100 | 3.3×-27.5× | 0.53×-1.72× |
> | LLaMA-8B | 1×H100 | 1.9×-11.8× | — |
> | LLaMA-8B | 1×H200 | 1.5×-17.2× | 0.38×-1.27× |
> | LLaMA-70B | 2×H200 | 2.7×-51.4× | — |
> | LLaMA-405B | 8×H200 | 2.7×-100.0× | 2.1×-9.7× |
> | Maverick | 8×H200 | 2.7×-23.1× | — |
> | Scout | 8×H200 | 2.6×-54.6× | — |

</details>

<a id="ev-150"></a>
### ev-150 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r00-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r0c0=Model |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `8401c53bc8bbfcf85cf14eb6e7b6f5b66a0c5851fce8ca7759ee3b2fc162e3a7` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=0; column=0; column_header=Model; value=Model

</details>

<a id="ev-151"></a>
### ev-151 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r00-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r0c1=Platform |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `1515159e938a0ba52f812ce69de84a4c04d7ca7d06fe7fcf11ca8f99727f8937` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=0; column=1; column_header=Platform; value=Platform

</details>

<a id="ev-152"></a>
### ev-152 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r00-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r0c2=Host Memory |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `56c6956932afe072f6eb2eb3112dddd05880d91458cc228a5dfa2264ab42d978` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=0; column=2; column_header=Host Memory; value=Host Memory

</details>

<a id="ev-153"></a>
### ev-153 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r00-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r0c3=Disk Storage |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `3cbb82efae19a476e3c1b7d03bc013b9912227ffafb5b40da4132c571e8b9819` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=0; column=3; column_header=Disk Storage; value=Disk Storage

</details>

<a id="ev-154"></a>
### ev-154 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r01-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r1c0=LLaMA-8B |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `5f8672fae13359ac7d71766f574ec84d8ee7856f08a954fd7968f882445e1292` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=1; column=0; row_header=LLaMA-8B; column_header=Model; value=LLaMA-8B

</details>

<a id="ev-155"></a>
### ev-155 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r01-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r1c1=1×A100 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `738bdea2d3b7ab77e60ffe08e28b8ac0a5a961000f38cbd61bb0e96fc31013ff` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=1; column=1; row_header=LLaMA-8B; column_header=Platform; value=1×A100

</details>

<a id="ev-156"></a>
### ev-156 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r01-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r1c2=3.3×-27.5× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `5de082283aebd904d2966e1ed47621cfab1f7fc3faf9c1a4d3a3b688d5ee5c6d` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=1; column=2; row_header=LLaMA-8B; column_header=Host Memory; value=3.3×-27.5×

</details>

<a id="ev-157"></a>
### ev-157 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r01-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r1c3=0.53×-1.72× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `ce45d50b3097c5247e5b7b2d135a0550f923e2d6568b19b18fd582efdf8ef40c` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=1; column=3; row_header=LLaMA-8B; column_header=Disk Storage; value=0.53×-1.72×

</details>

<a id="ev-158"></a>
### ev-158 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r02-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r2c0=LLaMA-8B |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `8b36d6cd510ab4882690a2943ad45646a57c1ec5e36dbd41018d1acd3139b2db` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=2; column=0; row_header=LLaMA-8B; column_header=Model; value=LLaMA-8B

</details>

<a id="ev-159"></a>
### ev-159 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r02-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r2c1=1×H100 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `9f1c6bb0bacc82178cd4be57947c6007310a85c6ef3480fdf0561ba4b4e4e4a7` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=2; column=1; row_header=LLaMA-8B; column_header=Platform; value=1×H100

</details>

<a id="ev-160"></a>
### ev-160 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r02-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r2c2=1.9×-11.8× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `33732d05c5cc7da52e86dc5acd1c4bf16d1c2847231bafd991bb858160075a53` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=2; column=2; row_header=LLaMA-8B; column_header=Host Memory; value=1.9×-11.8×

</details>

<a id="ev-161"></a>
### ev-161 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r02-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r2c3=— |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `a43b72217ba6e400151dfffd5fc9949761082aad279e810285a048339d16856c` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=2; column=3; row_header=LLaMA-8B; column_header=Disk Storage; value=—

</details>

<a id="ev-162"></a>
### ev-162 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r03-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r3c0=LLaMA-8B |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `0a304821106e4003e3b9b09b0ce34ac0d9792da4b7c854f2eb73fcdd08be0266` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=3; column=0; row_header=LLaMA-8B; column_header=Model; value=LLaMA-8B

</details>

<a id="ev-163"></a>
### ev-163 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r03-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r3c1=1×H200 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `3eb549795001abcdc095ddc29acb48dedce3e9a9acd791a99c0d5581b7203086` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=3; column=1; row_header=LLaMA-8B; column_header=Platform; value=1×H200

</details>

<a id="ev-164"></a>
### ev-164 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r03-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r3c2=1.5×-17.2× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `304890166b1c6e6d8f58001cca6ca705633c10f89d4bf1061e35a74b941754b2` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=3; column=2; row_header=LLaMA-8B; column_header=Host Memory; value=1.5×-17.2×

</details>

<a id="ev-165"></a>
### ev-165 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r03-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r3c3=0.38×-1.27× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `d5864e461c4940c98bba7aadf65857c7d1c846d4201b40eae5060f87e6447668` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=3; column=3; row_header=LLaMA-8B; column_header=Disk Storage; value=0.38×-1.27×

</details>

<a id="ev-166"></a>
### ev-166 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r04-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r4c0=LLaMA-70B |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `4e61090f4b6a19f37885f07b6d4cbcdc70539446ffe5d47eb0346ed50b011194` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=4; column=0; row_header=LLaMA-70B; column_header=Model; value=LLaMA-70B

</details>

<a id="ev-167"></a>
### ev-167 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r04-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r4c1=2×H200 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `9810b6c74e270bc9bc0ef9ed70d3cf5166fddb54368c7a1f75fec8a9f027e3f6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=4; column=1; row_header=LLaMA-70B; column_header=Platform; value=2×H200

</details>

<a id="ev-168"></a>
### ev-168 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r04-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r4c2=2.7×-51.4× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `5adac900059d1cd731707a0baa3b2df60f68b07601be1ce52f1e69dee30889e7` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=4; column=2; row_header=LLaMA-70B; column_header=Host Memory; value=2.7×-51.4×

</details>

<a id="ev-169"></a>
### ev-169 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r04-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r4c3=— |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `d1f4e4fb6cd151b5c997362ff31e3a6ffc892908c8d46dc904e5b2c37d0ab067` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=4; column=3; row_header=LLaMA-70B; column_header=Disk Storage; value=—

</details>

<a id="ev-170"></a>
### ev-170 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r05-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r5c0=LLaMA-405B |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `6cd3fd53af1b8784a276f7890fe1a850b049e80394215954a1c265f410b8079b` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=5; column=0; row_header=LLaMA-405B; column_header=Model; value=LLaMA-405B

</details>

<a id="ev-171"></a>
### ev-171 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r05-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r5c1=8×H200 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `ed46813c422afd3aacebaea94625cf744952193d2bc4e3d4fa004e093a34b5bb` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=5; column=1; row_header=LLaMA-405B; column_header=Platform; value=8×H200

</details>

<a id="ev-172"></a>
### ev-172 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r05-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r5c2=2.7×-100.0× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `38023ee6ab0cd1ca58ae710ea0600afdf48adbd2a6ffe46cf716c6573cfe309c` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=5; column=2; row_header=LLaMA-405B; column_header=Host Memory; value=2.7×-100.0×

</details>

<a id="ev-173"></a>
### ev-173 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r05-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r5c3=2.1×-9.7× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `ce64ff0d7785df47865c6fd28eea3298be030853fead6133a3fb7dd011ea0828` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=5; column=3; row_header=LLaMA-405B; column_header=Disk Storage; value=2.1×-9.7×

</details>

<a id="ev-174"></a>
### ev-174 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r06-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r6c0=Maverick |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `c8b5fb6bd592a49baf1061fded9d4b1090c28bf0393e58c2d8fa37e76923b8d9` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=6; column=0; row_header=Maverick; column_header=Model; value=Maverick

</details>

<a id="ev-175"></a>
### ev-175 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r06-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r6c1=8×H200 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `704cd5f3e1b68b42a0d30d66d95bdb93d84464d1635793170c9daba00b7a947e` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=6; column=1; row_header=Maverick; column_header=Platform; value=8×H200

</details>

<a id="ev-176"></a>
### ev-176 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r06-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r6c2=2.7×-23.1× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `86c6ec18e7c0acbe778a45d3ca801e202a57bc345018f4ed4d35076f6a1ceeec` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=6; column=2; row_header=Maverick; column_header=Host Memory; value=2.7×-23.1×

</details>

<a id="ev-177"></a>
### ev-177 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r06-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r6c3=— |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `be79a9b2e1c1ed62c7f10da7af2f6fa53a255dc344b86f8773ce4c284e8d0357` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=6; column=3; row_header=Maverick; column_header=Disk Storage; value=—

</details>

<a id="ev-178"></a>
### ev-178 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r07-c00` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r7c0=Scout |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `cbfeb7ff5425aff9474918fda87e44b59fa47a17136b746c30e86ce35c59fc53` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=7; column=0; row_header=Scout; column_header=Model; value=Scout

</details>

<a id="ev-179"></a>
### ev-179 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r07-c01` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r7c1=8×H200 |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `82cccd41c7c9609fe8739a6ef3c9563ffabb7d81b298b98c123d6b11ee6a080c` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=7; column=1; row_header=Scout; column_header=Platform; value=8×H200

</details>

<a id="ev-180"></a>
### ev-180 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r07-c02` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r7c2=2.6×-54.6× |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `bc2da49f761677e842b4251a08a8270ce19b31d9925ece671b3b3b725a5eb2ff` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=7; column=2; row_header=Scout; column_header=Host Memory; value=2.6×-54.6×

</details>

<a id="ev-181"></a>
### ev-181 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:cell-r07-c03` |
| 출처 종류 | `paper` |
| 콘텐츠 | `table` / `pdfplumber` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-table-000-0d2d5492636d` |
| Text span | `0:377` |
| Table cell | r7c3=— |
| BBox | `49.65, 276.23, 292.75, 402.25` |
| Content SHA-256 | `399bd39bcd2fc8f2fc78f7233074dc99dae46c94652b637fb61b3b481458d0e6` |

<details>
<summary>원문 스니펫 보기</summary>

> Table I; row=7; column=3; row_header=Scout; column_header=Disk Storage; value=—

</details>

<a id="ev-182"></a>
### ev-182 — `2607.27187-d6a67efd` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0005:figure-04:span-00000-00105` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | 4 illustrates the connectivity diagram. An External Laser Source |
| Object | `Figure 4` |
| 원본 element | `elem-2607.27187-d6a67efd-p0005-caption-010-24e4f8cd7138` |
| Text span | `0:105` |
| Table cell | - |
| BBox | `315.13, 403.38, 568.73, 421.60` |
| Content SHA-256 | `80a95a950e9358c27b228fbe0ca9ed2c6a0120b75a19548a43bb4068789f0ea4` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 4. PF Memory Appliance server connectivity via Photonic Fabric NIC
> (PF-NIC) over PCIe/CXL interface.

</details>

<a id="ev-183"></a>
### ev-183 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:table-01:span-00000-00125` |
| 출처 종류 | `paper` |
| 콘텐츠 | `caption` / `native_text` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Table I` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-caption-006-0f16c0ccc3c0` |
| Text span | `0:125` |
| Table cell | - |
| BBox | `45.53, 236.59, 298.51, 253.81` |
| Content SHA-256 | `c7d0be8584eb1235cdc626bdc221bfe468cf86de69d1317e6ae1af50079a3bdb` |

<details>
<summary>원문 스니펫 보기</summary>

> TABLE I.
> TESTING MATRIX AND PERFORMANCE SPEEDUP RANGES FOR
> REPEATED REQUEST BENCHMARK. ALL CONFIGURATIONS USE BATCH SIZES {1,

</details>

<a id="ev-184"></a>
### ev-184 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:elem-2607.27187-d6a67efd-p0003-text-group-004-2df559764180:span-00000-01330` |
| 출처 종류 | `paper` |
| 콘텐츠 | `text` / `native_text` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `elem-2607.27187-d6a67efd-p0003-text-group-004-2df559764180` |
| 원본 element | `elem-2607.27187-d6a67efd-p0003-text-group-004-2df559764180` |
| Text span | `0:1330` |
| Table cell | - |
| BBox | `45.28, 52.98, 569.47, 225.24` |
| Content SHA-256 | `4772f57e5a4f02517a2ac179e5a417c4544b5985341db3bf719e65c826ebf270` |

<details>
<summary>원문 스니펫 보기</summary>

> S=Tcompute/Tmemory
> ()
>
> Intel Xeon server over PCIe 4.0 ×16 (~32 GB/s unidirectional)
> with 512 GB system DRAM and 7 TB local disk. The
> H100/H200 testbeds provide PCIe 5.0 ×16 (~64 GB/s
> unidirectional), with multi-GPU nodes (up to eight H100 or
> H200) providing up to 2 TB host DRAM.
>
> Tcompute=b(2sP+2s2nheadhheadL)/MFU
> ()
>
> Tmemory=K+bs
> ()
>
> 3) Results
> TABLE I summarizes the KV cache retrieval speedup ranges
> across all model-platform configurations. All configurations use
> batch sizes {1, 2, 8, 16, 32}. Standard context lengths span 1K–
> 100K tokens; Maverick extends to 1M; Scout to 4M. The
> experimental results demonstrate that host memory-based KV
> cache retrieval consistently provides substantial performance
> improvements over baseline re-computation, while disk-based
> caching shows more nuanced benefits depending on workload,
> model size, and deployed systems.
>
> where b is batch size, s is prompt length, P represents the
> number of parameters, nhead is the number of attention heads,
> hhead is the head dimension, L is the number of transformer
> layers, K represents fixed overhead, and α is the per-token
> loading cost. For the 405B model, attention FLOPs achieve
> parity with feed-forward FLOPs at approximately 20,000 tokens
> and dominate at longer contexts, explaining the super linear
> scaling of speedup with prompt length.

</details>

<a id="ev-185"></a>
### ev-185 — `2607.27187-d6a67efd` p.3

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0003:figure-01:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `3` / `3` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Figure 1` |
| 원본 element | `elem-vision-50e722a2a640c6d230b4` |
| Text span | `0:1763` |
| Table cell | - |
| BBox | `312.00, 24.00, 588.00, 357.58` |
| Content SHA-256 | `47ba3a36aabec2d954bfb5a5652ee84630719114e4e2c5ee148f8961f22b2889` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 1. KV retrieval from host memory speedup compared to GPU re-
> computation versus (a) Prompt Length and (b) Batch size for LLaMA 405B
> model on eight H200 systems.
> S=T_compute/T_memory (1)
>
> T_compute=b(2sP+2s²n_headh_headL)/MFU (2)
>
> T_memory=K+bsα (3)
>
> where b is batch size, s is prompt length, P represents the number of parameters, n_head is the number of attention heads, h_head is the head dimension, L is the number of transformer layers, K represents fixed overhead, and α is the per-token loading cost. For the 405B model, attention FLOPs achieve parity with feed-forward FLOPs at approximately 20,000 tokens and dominate at longer contexts, explaining the super linear scaling of speedup with prompt length.
>
> Left chart: Host Memory Retrieval Speedup; Prompt Length (tokens). Legend: Batch 1, Batch 2, Batch 8, Batch 16, Batch 32.
> Right chart: Host Memory Retrieval Speedup; Batch Size. Legend: 1K tokens, 5K tokens, 10K tokens, 20K tokens, 50K tokens, 100K tokens.
>
> Fig. 1. KV retrieval from host memory speedup compared to GPU re-computation versus (a) Prompt Length and (b) Batch size for LLaMA 405B model on eight H200 systems.
> The left chart plots host-memory retrieval speedup against prompt length for five batch sizes; the right chart plots it against batch size for six token lengths.
> Across the left chart, all displayed batch-size series increase with prompt length.
> In the right chart, the 100K-token series rises to 100 at batch size 8, then declines at larger displayed batch sizes.
> The printed text states that attention FLOPs reach parity with feed-forward FLOPs at approximately 20,000 tokens and dominate at longer contexts.

</details>

<a id="ev-186"></a>
### ev-186 — `2607.27187-d6a67efd` p.4

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0004:figure-02:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `4` / `4` |
| 절 | 80 layers, 8 KV heads, and 128-dimensional head size). In |
| Object | `Figure 2` |
| 원본 element | `elem-vision-93fdc00e42ed3ffb084e` |
| Text span | `0:2849` |
| Table cell | - |
| BBox | `24.00, 119.16, 300.00, 546.15` |
| Content SHA-256 | `3f93c5a448a0bc046ba35a081cf3fe66168e38dd8f73c415b759b69d1886a9e0` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 2. Evolution of KV cache transfer data paths in disaggregated LLM
> inference. Solid lines represent the KV data plane; dashed lines represent CPU
> control operations. Each generation removes components from the critical path:
> (a)→(b) eliminates DRAM bounces; (b)→ (c,d) eliminates the network. CXL
> modes additionally enable write-once-read-many KV reuse and eliminate KV-
> locality-aware scheduling.
> (a) CPU-driven RDMA
> Prefill Server; Decode Server
> Prefill GPU; Decode GPU; D2H; H2D; DRAM; CPU; RDMA NIC; IB/RoCE
>
> (b) GPUDirect RDMA
> Prefill Server; Decode Server
> Prefill GPU
> BAR1; Decode GPU
> BAR1; P2P; RDMA NIC; IB/RoCE; CPU
>
> (c) CXL direct attach (TraCT)
> Prefill Server; Decode Server
> Prefill GPU; Decode GPU; DMA; CPU
> CXL Type 3
> Shared Memory
> Prefix Hash,
> KV Block Store,
> LRU, Locks
>
> (d) CXL switch (Beluga)
> Prefill Server; Decode Server
> Prefill GPU; Decode GPU; DMA; CPU
> CXL 2.0 Switch
> CXL Memory Pool
> (8 TB)
> KV Blocks, Global KV Index,
> RPC mailbox
>
> Data (RDMA); Data (CXL DMA); Control (CPU)
>
> Fig. 2. Evolution of KV cache transfer data paths in disaggregated LLM inference. Solid lines represent the KV data plane; dashed lines represent CPU control operations. Each generation removes components from the critical path: (a)→(b) eliminates DRAM bounces; (b)→ (c,d) eliminates the network. CXL modes additionally enable write-once-read-many KV reuse and eliminate KV-locality-aware scheduling.
> Prefill GPU -> DRAM: (a) red solid D2H data arrow
> DRAM -> RDMA NIC: (a) red solid data arrow
> RDMA NIC -> RDMA NIC: (a) red solid IB/RoCE data arrow between prefill and decode servers
> RDMA NIC -> DRAM: (a) red solid data arrow
> DRAM -> Decode GPU: (a) red solid H2D data arrow
> CPU -> DRAM / RDMA NIC: (a) dashed control connections are shown on each server
> Prefill GPU BAR1 -> RDMA NIC: (b) red solid P2P data arrow
> RDMA NIC -> RDMA NIC: (b) red solid IB/RoCE data arrow between servers
> RDMA NIC -> Decode GPU BAR1: (b) red solid P2P data arrow
> CPU -> RDMA NIC: (b) dashed control connection on each server
> Prefill GPU -> CXL Type 3 Shared Memory: (c) green solid DMA arrow
> CXL Type 3 Shared Memory -> Decode GPU: (c) green solid DMA arrow
> CPU -> CXL Type 3 Shared Memory: (c) dashed control connections from both servers
> Prefill GPU -> CXL 2.0 Switch: (d) green solid DMA data arrow
> CXL 2.0 Switch -> Decode GPU: (d) green solid DMA data arrow
> CXL 2.0 Switch -> CXL Memory Pool (8 TB): (d) green solid vertical data arrows
> CPU -> CXL Memory Pool (8 TB): (d) dashed control connections from both servers
> The legend identifies red solid lines as “Data (RDMA),” green solid lines as “Data (CXL DMA),” and gray dashed lines as “Control (CPU).”
> Panels (a) and (b) show RDMA NICs and an IB/RoCE connection; panels (c) and (d) show CXL shared-memory components.
> The caption states that (a)→(b) eliminates DRAM bounces and (b)→(c,d) eliminates the network.

</details>

<a id="ev-187"></a>
### ev-187 — `2607.27187-d6a67efd` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0005:figure-03:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | 7.2 Tbps of bidirectional bandwidth. |
| Object | `Figure 3` |
| 원본 element | `elem-vision-4cc136b591b3bf102a21` |
| Text span | `0:1398` |
| Table cell | - |
| BBox | `24.00, 270.96, 300.00, 670.43` |
| Content SHA-256 | `8f25e0f20c9fabcd91504bb6162813f57baa2a8540c3a17c0fe545fc4bcd5367` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 3. PF Memory Appliance architecture: 256 optical paths creating full-
> mesh connectivity connecting up to 16 host servers without intermediate
> switching.
> Host 0; Host 1; Host 2; Host 3; Host 4; Host 5; Host 6; Host 7; Host 8; Host 9; Host 10; Host 11; Host 12; Host 13; Host 14; Host 15
> CXL
> Port 0; Port 1; Port 2; Port 3; Port 4; Port 5; Port 6; Port 7; Port 8; Port 9; Port 10; Port 11; Port 12; Port 13; Port 14; Port 15
> 16x16 Passive Fiber Shuffle
> PFM 0; PFM 1; PFM 2; PFM 3; PFM 4; PFM 5; PFM 6; PFM 7; PFM 8; PFM 9; PFM 10; PFM 11; PFM 12; PFM 13; PFM 14; PFM 15
> Photonic Fabric Memory Appliance
> Fig. 3. PF Memory Appliance architecture: 256 optical paths creating full-mesh connectivity connecting up to 16 host servers without intermediate switching.
> Host 0–Host 15 -> Port 0–Port 15: Each host is visibly connected through a labeled CXL link to a corresponding port.
> Port 0–Port 15 -> 16x16 Passive Fiber Shuffle: Ports connect into the passive fiber shuffle.
> 16x16 Passive Fiber Shuffle -> PFM 0–PFM 15: Visible crossing optical-path lines connect the shuffle to the PFM modules.
> PFM 0–PFM 15 -> Photonic Fabric Memory Appliance: The PFM modules are enclosed within the appliance boundary.
> The diagram visibly presents 16 hosts, 16 ports, and 16 PFM modules labeled from 0 through 15.
> The fiber connections form a crisscrossing full-mesh-like pattern between the port row and PFM row.

</details>

<a id="ev-188"></a>
### ev-188 — `2607.27187-d6a67efd` p.5

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0005:figure-04:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `diagram` / `vision` |
| 물리·인쇄 페이지 | `5` / `5` |
| 절 | 4 illustrates the connectivity diagram. An External Laser Source |
| Object | `Figure 4` |
| 원본 element | `elem-vision-861e71d2dbe6727fc23a` |
| Text span | `0:814` |
| Table cell | - |
| BBox | `312.00, 43.38, 588.00, 433.60` |
| Content SHA-256 | `44eeefa18fcbd4d0a7e4cce5174e0c51c24fcb974e82b1aab6989c8ec2a06685` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 4. PF Memory Appliance server connectivity via Photonic Fabric NIC
> (PF-NIC) over PCIe/CXL interface.
> Server
> Host
> Processor
> PCIe/CXL
> PF-NIC
> ELS
> Fiber Optic
> Cable
> PF-NIC to PFM
> Photonic Fabric Appliance
> PFM
> ELS
> Fig. 4. PF Memory Appliance server connectivity via Photonic Fabric NIC
> (PF-NIC) over PCIe/CXL interface.
> Host Processor -> PF-NIC: bidirectional PCIe/CXL connection
> ELS (Server) -> PF-NIC: upward arrow
> PF-NIC -> PFM: fiber-optic cable connection labeled “PF-NIC to PFM”
> ELS (Photonic Fabric Appliance) -> PFM: orange upward optical paths to the displayed PFM modules
> The Server contains a Host Processor and a PF-NIC/ELS block.
> The Photonic Fabric Appliance contains multiple stacked PFM blocks and an ELS block.
> The Host Processor and PF-NIC are connected by a bidirectional arrow labeled PCIe/CXL.

</details>

<a id="ev-189"></a>
### ev-189 — `2607.27187-d6a67efd` p.7

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0007:figure-06:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `7` / `7` |
| 절 | 16 ports, sustaining 25.6 GB/s per port after accounting for |
| Object | `Figure 6` |
| 원본 element | `elem-vision-d4be57d49b91972ea6ec` |
| Text span | `0:607` |
| Table cell | - |
| BBox | `312.00, 24.00, 588.00, 184.03` |
| Content SHA-256 | `bb072489d1100fa8102c505e5834b268e7c37d60d1dd3e0bf5ce1fa9c4ea07e6` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 6. Latency distribution under loaded conditions for (a) Write and (b) Read
> operations.
> Count
> Write Latency (ns)
> Count
> Read Latency (ns)
>
> Fig. 6. Latency distribution under loaded conditions for (a) Write and (b) Read operations.
> The figure contains two side-by-side histograms: write latency on the left and read latency on the right.
> Write-latency histogram bars are visibly concentrated between roughly 225 ns and 245 ns, with bars also near 210–224 ns and 248–252 ns.
> Read-latency histogram bars are visibly concentrated around 278–284 ns, with isolated bars near 290 ns, 300 ns, 301 ns, and 320 ns.

</details>

<a id="ev-190"></a>
### ev-190 — `2607.27187-d6a67efd` p.8

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0008:figure-07:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `8` / `8` |
| 절 | 2.0 switched memory pool (Beluga), measured via Intel MLC. |
| Object | `Figure 7` |
| 원본 element | `elem-vision-1fab1250b4b7eb8858c6` |
| Text span | `0:2864` |
| Table cell | - |
| BBox | `312.00, 24.00, 588.00, 324.33` |
| Content SHA-256 | `c9bead5671b71655aab3da1a063ce6ef2603dd874fdf673f8f350fe615d1276a` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 7. Software integration approach of PF Memory Appliance with various
> ML Frameworks
> User Application (serving endpoint, batch serving, agent)
>
> Existing inference frameworks (unmodified)
> vLLM
> KV Connector
> SGLang
> HiCache Backend
> Dynamo
> KVBM + NIXL
> PyTorch
> allocator API
> LMCache
> storage backend
>
> PFMA integration layer (custom to each framework)
> vLLM
> CXL KV Connector
> store() / load()
> SGLang
> CXL HiCache plugin
> get/set/exist
> Dynamo
> NIXL CXL Backend
> Southbound API
> PyTorch
> NUMA / CUDA host alloc
> mbind / pin
> LMCache
> CXL storage tier
> KV offload
>
> PFMA runtime library (common to all frameworks)
> KV block allocator
> KV block indexing
> Coherency (rendezvous) consistency
> Eviction policy manager
> ** conceptual stage, specs to be finalized later
>
> Linux Kernel + CUDA runtime (existing, unmodified)
>
> Host 1 (prefill)
> GPU
> CPU + DRAM
> mmap + cudaHostRegister
>
> Host 2 (decode)
> GPU
> CPU + DRAM
> mmap + cudaHostRegister
>
> Host N (prefill or decode)
> GPU
> CPU + DRAM
> mmap + cudaHostRegister
>
> Root Complex + PF NIC + PFLink
>
> PFMA (Photonic Fabric™ Memory Appliance) - optically connected CXL Type 3 memory appliance
>
> Fig. 7. Software integration approach of PF Memory Appliance with various ML Frameworks
> User Application (serving endpoint, batch serving, agent) -> Existing inference frameworks (unmodified): feeds downward into
> Existing inference frameworks (unmodified) -> PFMA integration layer (custom to each framework): framework-specific dashed downward connections
> PFMA integration layer (custom to each framework) -> PFMA runtime library (common to all frameworks): feeds downward into
> PFMA runtime library (common to all frameworks) -> Linux Kernel + CUDA runtime (existing, unmodified): feeds downward into
> Linux Kernel + CUDA runtime (existing, unmodified) -> Host 1 (prefill): connects downward to
> Linux Kernel + CUDA runtime (existing, unmodified) -> Host 2 (decode): connects downward to
> Linux Kernel + CUDA runtime (existing, unmodified) -> Host N (prefill or decode): connects downward to
> Host 1 (prefill) -> PFMA (Photonic Fabric™ Memory Appliance) - optically connected CXL Type 3 memory appliance: connects downward through Root Complex + PF NIC + PFLink
> Host 2 (decode) -> PFMA (Photonic Fabric™ Memory Appliance) - optically connected CXL Type 3 memory appliance: connects downward through Root Complex + PF NIC + PFLink
> Host N (prefill or decode) -> PFMA (Photonic Fabric™ Memory Appliance) - optically connected CXL Type 3 memory appliance: connects downward through Root Complex + PF NIC + PFLink
> The figure separates existing/unmodified components from the PFMA integration layer and PFMA runtime library.
> The PFMA integration layer has five visible framework-specific paths: vLLM, SGLang, Dynamo, PyTorch, and LMCache.
> Three hosts—Host 1 (prefill), Host 2 (decode), and Host N (prefill or decode)—each show GPU and CPU + DRAM, with "mmap + cudaHostRegister".

</details>

<a id="ev-191"></a>
### ev-191 — `2607.27187-d6a67efd` p.9

| 항목 | 값 |
|---|---|
| Evidence ID | `paper:2607.27187-d6a67efd@d6a67efde2a1:p0009:figure-08:whole` |
| 출처 종류 | `paper` |
| 콘텐츠 | `figure` / `vision` |
| 물리·인쇄 페이지 | `9` / `9` |
| 절 | 2.0 switched memory pool (Beluga), measured via Intel MLC. |
| Object | `Figure 8` |
| 원본 element | `elem-vision-92629eac4ff456cd795b` |
| Text span | `0:2080` |
| Table cell | - |
| BBox | `312.00, 82.66, 588.00, 491.13` |
| Content SHA-256 | `883e24832166d6d9386f10e924e262da988b33558d366b65a904152b2c2094a6` |

<details>
<summary>원문 스니펫 보기</summary>

> Fig. 8. (a) Mean TTFT results for multi-turn conversation workload over
> different number of conversations with and without PF Memory Appliance; (b)
> Total prefix cache hit rate over different number of conversations with and
> without PF Memory Appliance.
> B. Results
>
> Fig. 8(a) shows mean TTFT as the total token working set scales from 50 conversations to 300 conversations. With the 32 TB PF Memory Appliance, TTFT remains flat at 2,690 ms regardless of conversation count—all KV cache entries are retained in the pooled memory, and subsequent turns benefit from full prefix cache hits (82% hit rate). In contrast, the 2 TB baseline degrades rapidly: at 100 conversations, mean TTFT rises to 8,156 ms (3× higher) as the LRU eviction policy forces full re-computation of evicted KV cache. At 300 conversations, the gap widens to 6.6×, with the prefix hit rate collapsing from 82% to 6.35% (Fig. 8(b)).
>
> Left plot: Mean Compute TTFT (ms); Conversations. Legend: 2 TB CPU; 32 TB CXL. X-axis labels: 50, 100, 150, 200, 250, 300. Y-axis labels: 5000, 10000, 15000.
>
> Right plot: Total Prefix Hit (%); Conversations. Legend: 2 TB CPU; 32 TB CXL. X-axis labels: 50, 100, 150, 200, 250, 300. Y-axis labels: 20, 40, 60, 80.
>
> Fig. 8. (a) Mean TTFT results for multi-turn conversation workload over different number of conversations with and without PF Memory Appliance; (b) Total prefix cache hit rate over different number of conversations with and without PF Memory Appliance.
> In the left plot, the red dashed-square 2 TB CPU series rises sharply as conversations increase, while the green dash-dot-triangle 32 TB CXL series remains nearly flat.
> In the right plot, the red dashed-square 2 TB CPU total-prefix-hit series declines as conversations increase, while the green dash-dot-triangle 32 TB CXL series remains flat near the 80% tick.
> The visible paragraph explicitly states that 32 TB PF Memory Appliance TTFT remains flat at 2,690 ms and prefix-cache hit rate is 82%; at 100 conversations the 2 TB baseline mean TTFT is 8,156 ms; and at 300 conversations its prefix-hit rate is 6.35%.

</details>
