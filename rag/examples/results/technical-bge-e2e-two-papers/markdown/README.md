# 기술조사 결과 검토본

> 이 문서는 `run.json`과 관련 기술조사 JSON을 사람이 검토하기 쉽게 변환한 보기입니다.
> 기계 간 전달과 무결성 검증에는 원본 JSON을 사용하세요.

## 실행 요약

| 항목 | 값 |
|---|---|
| 상태 | succeeded |
| schema version | 1.0.0 |
| job ID | `technical-bge-e2e-20260922-v22` |
| OpenAI 모델 | `gpt-5.6-terra` |
| 임베딩 | `BAAI/bge-m3` |
| 임베딩 revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| index profile | `655f2fe31d32595a2c7063dc6144f4da2a8390283cdfcb84ea0e53f56b5681e6` |
| 시작 | 2026-09-21 23:31:11.248821+00:00 |
| 종료 | 2026-09-21 23:32:36.392662+00:00 |
| 입력 토큰 | 122,043 |
| 출력 토큰 | 6,697 |
| 총 토큰 | 128,740 |
| peak RSS | 1,874,685,952 bytes (1.75 GiB) |

## 품질 지표

| 지표 | 값 |
|---|---:|
| Evidence 해석률 | 1.000 |
| Locator 해석률 | 1.000 |
| Critical inventory 계약 충족률 | 1.000 |
| Unsupported numeric claim | 0 |

## 검토 파일

- [RDKV: Rate-Distortion Bit Allocation for Joint](dossiers/2605.08317-25836a41.md)
- [A Photonic-CXL Memory Appliance for Scalable KV](dossiers/2607.27187-d6a67efd.md)
- [교차 논문 비교](comparison.md)
- [근거 레지스트리](evidence_registry.md)

## 주의 사항

- 2605.08317-25836a41: Roman-numeral Table I의 모든 operating-condition header 및 model/platform row — 제공된 evidence registry에는 Roman-numeral Table I의 caption, 표 본문 또는 cell evidence가 없으며, Arabic-numbered Table 1과 동일한 표라는 근거도 없다.
- 2605.08317-25836a41: Roman-numeral Table I의 operating-condition header 및 model/platform별 system testing matrix — 제공된 evidence registry에는 `Table I`의 caption, header, row, cell이 없다. Arabic-numbered `Table 1`은 LongBench 성능 표이며 Roman-numeral `Table I`의 대체 근거가 아니다.
- 2605.08317-25836a41: multi-GPU/multi-node serving, concurrency, production traffic workload의 system 평가 조건 — 제공 근거는 단일 A100 64 GB system 측정과 Qwen2.5-72B-Instruct의 2-GPU tensor-parallel LongBench 기능 평가를 제시하지만, 요청 동시성 또는 production traffic workload 조건을 제시하지 않는다.
- 2607.27187-d6a67efd: 학습 또는 fine-tuning 절차 — 제공된 evidence registry에서 training 또는 fine-tuning 절차를 뒷받침하는 paper-owned evidence를 확인하지 못했다.
