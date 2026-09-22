# 기술조사 결과 검토본

> 이 문서는 `run.json`과 관련 기술조사 JSON을 사람이 검토하기 쉽게 변환한 보기입니다.
> 기계 간 전달과 무결성 검증에는 원본 JSON을 사용하세요.

## 실행 요약

| 항목 | 값 |
|---|---|
| 상태 | succeeded |
| schema version | 1.0.0 |
| job ID | `technical-long-context-qa-datacenter-20260922` |
| OpenAI 모델 | `gpt-5.6-terra` |
| 임베딩 | `BAAI/bge-m3` |
| 임베딩 revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| index profile | `655f2fe31d32595a2c7063dc6144f4da2a8390283cdfcb84ea0e53f56b5681e6` |
| 시작 | 2026-09-22 03:00:41.992184+00:00 |
| 종료 | 2026-09-22 03:09:20.932458+00:00 |
| 입력 토큰 | 588,031 |
| 출력 토큰 | 53,765 |
| 총 토큰 | 641,796 |
| peak RSS | 3,131,867,136 bytes (2.92 GiB) |

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

- 2605.08317-25836a41: 프로덕션 클라우드 서빙의 concurrency, batch size, request arrival rate, multi-tenant interference 조건 — 제공된 증거에는 단일 A100 64 GB 조건은 있으나, 해당 프로덕션 운영 변수를 명시한 평가는 확인되지 않는다.
