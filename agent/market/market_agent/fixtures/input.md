# 이해관계자 에이전트 입력

이 파일은 인터페이스 검토용 수작업 샘플이다. 실제 RAG 실행 결과가 아니다. 논문 초록에서 확인한 최소 요약을 사용했으며 상세 구현·평가 조건은 미확인으로 남긴다.

## 실행 정보

| 항목 | 값 |
| --- | --- |
| schema_version | 0.1 |
| run_id | demo |
| domain | cloud_datacenter |
| 조사 기준일 | 2026-09-21 |
| 언어 | 한국어 |
| 남은 검색 요청 한도 | 6 |
| 남은 원문 조회 한도 | 10 |
| 남은 LLM 시도 한도 | 5 |

## 기술 목록

| 기술 ID | 이름 | 구분 | 논문·버전·URL |
| --- | --- | --- | --- |
| SW-01 | RDKV | SW | RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache, arXiv:2605.08317v1, https://arxiv.org/abs/2605.08317v1 |
| HW-01 | Photonic-CXL | HW | A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference, arXiv:2607.27187v1, https://arxiv.org/abs/2607.27187v1 |

## 논문 기반 기술 요약

### SW-01

- 메커니즘: 제거와 양자화를 비트 할당 문제로 함께 다루며, prefill 이후 할당을 수행하는 KV cache 압축 방법이다. [E-SW-001](#e-sw-001)
- 세부 원리: attention 계산에 생기는 왜곡을 기준으로 token 또는 channel의 중요도를 구하고, full precision부터 0bit까지 비트 폭을 배정한다. [E-SW-001](#e-sw-001)
- 적용 문제: 긴 문맥의 LLM 추론에서 메모리 용량·대역폭 제약 완화. [E-SW-001](#e-sw-001)
- 평가 정보: 여러 벤치마크에서 품질과 decoding 성능을 평가했다고 논문 초록이 보고한다. 이 샘플에는 상세 GPU·커널·워크로드 조건을 포함하지 않았다. [E-SW-001](#e-sw-001)
- 도입 요구: 실제 추론 엔진 통합 방식, 지원 하드웨어, 유지보수 조건은 이 입력에 없음.
- 한계: 압축 방법의 품질·성능 결과를 모든 클라우드 워크로드에 일반화할 근거가 이 입력에는 없음.

### HW-01

- 메커니즘: 논문은 Marvell Photonic Fabric Memory Appliance라는 이름의 광학·CXL 공유 메모리 구조를 제안한다. 관련 외부 자료를 검색할 때 Marvell Photonic Fabric이라는 제품·기술 명칭을 사용할 수 있다. [E-HW-001](#e-hw-001)
- 구성: 전기 스위치를 수동 광섬유 shuffle로 대체하는 구조이며, 16개 호스트에 32TB 공유 메모리를 제공하도록 제안한다. 실제 고객에게 판매·배포됐다는 뜻은 아니다. [E-HW-001](#e-hw-001)
- 적용 문제: 대규모 LLM 추론의 KV cache 저장·검색 수요. [E-HW-001](#e-hw-001)
- 평가 정보: 어플라이언스 관련 효과를 에뮬레이션과 시뮬레이션으로 보고한다. [E-HW-001](#e-hw-001)
- 도입 요구: 실제 고객 환경의 통합 절차·구매 가격·운영 지원 조건은 이 입력에 없음.
- 한계: 위 평가만으로 실제 클라우드 고객의 운영 효과나 채택 여부를 판단할 수 없음.

## 근거 목록

### E-SW-001

- 문서 ID: SW-01
- 저자: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일·버전: 2026-05-08 / v1
- 원문: https://arxiv.org/abs/2605.08317v1
- 위치: Abstract
- 근거 요지(요약): 제거와 양자화를 함께 최적화하고 prefill 뒤 비트 할당을 적용한다. 여러 벤치마크와 decoding 비교를 보고한다. attention 계산의 압축 왜곡으로 token 또는 channel의 가중치를 구하고, full precision부터 0bit까지 비트 폭을 배정한다. 논문 초록은 긴 문맥 추론의 메모리 용량과 대역폭 제약을 해결 대상으로 제시한다. 품질·성능 평가는 LongBench, RULER, InfiniteBench 등의 벤치마크 범위에서 보고된다.
- 성격: 논문 저자의 기술·실험 보고. 고객 도입·독립 재현 근거가 아님.

### E-HW-001

- 문서 ID: HW-01
- 저자: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일·버전: 2026-07-29 / v1
- 원문: https://arxiv.org/abs/2607.27187v1
- 위치: Abstract
- 근거 요지(요약): Marvell Photonic Fabric Memory Appliance라는 광학·CXL 공유 메모리 구조를 제안하고, 구조·서빙 효과를 에뮬레이션과 시뮬레이션으로 보고한다. 전기 스위치를 수동 광섬유 shuffle로 대체하며, 16개 호스트에 32TB 공유 메모리를 제공하는 구조를 제안한다. 전기 CXL pool 대비 지연시간은 에뮬레이션으로, multi-turn 대화의 TTFT 효과는 시뮬레이션으로 평가한다.
- 성격: 논문 저자의 구조·평가 보고. 고객 실운영 결과와 구별해야 함.

## 추가 요청 및 정보 공백

- 대상 환경은 클라우드 데이터센터로 한정한다.
- 코드 공개·공식 제품 발표 등 당사자 행동을 직접 확인한다.
- 클라우드 운영자·개발자·고객·경쟁사·외부 평가자의 실제 입장은 외부 자료에서 조사한다.
- 자료가 부족하면 미확인으로 남기며 기술 편익으로 기업의 지지를 추정하지 않는다.
- 구체적인 품질 허용치·비용·운영 규모가 없어 수치형 경제성이나 특정 조직의 구매 판단은 보류한다.
