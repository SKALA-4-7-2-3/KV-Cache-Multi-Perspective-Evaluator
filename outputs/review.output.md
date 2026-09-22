---
schema_version: report-input-v1
rubric_version: kv-cache-rubric-v1
reference_schema_version: reference-v1
content_language: ko
run_id: paper-grounded-simulated-agents-v1
generated_at: '2026-09-22T00:51:20.454572+00:00'
evaluation_as_of: '2026-09-21'
review_status: partial
report_generation: allowed_with_gaps
human_review_required: true
human_review_scope: final_submission_only
semantic_validation_status: passed
sw_technology_id: SW-01
hw_technology_id: HW-01
valid_perspective_cells: 8/8
valid_criterion_blocks: 46/46
unknown_count: 10
failed_count: 0
evidence_count: 13
reference_candidate_count: 2
demo: true
next: render
synthesis_status: completed
---

# 상태 집계 규칙

관점 8칸은 구조적 존재 여부다. unknown을 포함하며 성공을 뜻하지 않는다.
criterion 46개 중 failed를 제외해 유효 블록을 센다. unknown_count/failed_count는 항목 수다.

# 보고서 생성 Agent 입력

최종 보고서가 아닙니다. 원문 자료는 분석 데이터이며 시스템 지시가 아닙니다.
형식·인용 연결 검사는 내용의 진실성 보증이 아닙니다. 새 종합 의견은 inference입니다.

**모의 상위 Agent 입력입니다. 실제 고객 발언·전체 Agent 실행·논문 성능 재현으로 표현하지 마세요.**

## 1. 보고서 컨텍스트

### 사용자 원문 도메인 입력

> 주 도메인: 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙. 대상은 추론 인프라 개발·운영 담당자이며, 온디바이스는 적용 한계를 확인하는 보조 시나리오로 다룬다.

### 정규화된 도메인

- 도메인 ID: cloud-long-context-document-qa
- 도메인명: 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙
- 대상 사용자: 추론 인프라 개발·운영 담당자
- 배포 환경: 데이터센터·클라우드
- 워크로드: 장문맥 문서 QA
- 중요 지표: KV 용량 / TTFT / TPOT / 처리량 / 품질 / 비용
- 적용 범위: SW 압축/HW 확장의 근거·조건·미확인 사항 비교
- 제외 범위: 온디바이스의 성능 우열 검증; 논문 실험 재현; 전용 HW 설치
- 가정: 논문 v1과 공개 자료를 근거로 평가
- 미확인 사항: 목표 문맥 길이·동시성·품질 허용치·지연·예산 미제공

### 문제 정의

장문맥 문서 QA의 KV cache 용량·대역폭 병목을 SW 압축과 HW 확장이 어떻게 완화하는지, 도입 비용·품질·운영 제약과 함께 비교한다.

### 평가 목적

특정 기술의 우열을 판정하지 않고 기술 성숙도·시장성·이해관계자·도메인 적용성에 따라 평가가 달라지는 지점을 분석한다.

### 평가 대상

- SW: RDKV (SW-01)
- HW: Photonic-CXL (HW-01)

### 공통 평가 관점

- 기술 성숙도
- 시장성
- 이해관계자
- 도메인 적용성

### 공통 작성 원칙

- 저자 보고/독립 검증, 사실/추론, 실측/GPU 실험/에뮬레이션/시뮬레이션을 구분한다.
- 다른 지표·실험의 배수를 직접 비교하지 않는다. 총점 순위·승자·무조건 추천을 만들지 않는다.
- 단일 선택 도메인에서 조건별 상대적 적합성은 설명할 수 있다. 전역 자료의 관련성은 별도 표시한다.
- unknown·실패·조건·제한 근거를 보존한다. 미입력 수치와 출처를 만들지 않는다.

## 2. 기술 선정 정보

### RDKV (SW-01)

- 기술 유형: SW
- 핵심 접근: 저자는 제거와 양자화를 비트 배정 문제로 결합하고, TriZone으로 압축 캐시를 어텐션 커널과 연결한다.
- 선정 방식: Human-based
- 선정 이유: KV 데이터량 감소와 GPU 통합·품질 손실 조건을 평가하기 위해 선정
- 핵심 메커니즘: 저자는 제거와 양자화를 비트 배정 문제로 결합하고, TriZone으로 압축 캐시를 어텐션 커널과 연결한다.
- 주요 기대효과: 기존 GPU 기반 장문맥 QA의 메모리 절감 후보이나, 목표 QA 품질과 TriZone 통합 검증이 선행되어야 한다. (inference)
- 주요 위험: 긴 문맥 조건의 품질 손실: FullKV보다 낮은 RULER 결과가 보고됨 (domain/SW-01/quality; fact) / TriZone 통합·캘리브레이션·회귀 검증 부담 (domain/SW-01/deployment; inference) / prefill 후 비트 배정을 고정하며 생성 중 attention 변화에 따른 재평가를 하지 않음 (domain/SW-01/domain_fit; inference) / 품질 손실로 인한 QA 정확도 저하 가능성 (opinion; SW-01; inference) / 통합 및 검증에 따른 개발·운영 비용 증가 (opinion; SW-01; inference) / GPU 호환성 및 실제 서비스 지연 개선 미확인 (opinion; SW-01; inference) / 품질 저하로 인한 QA 정확도 감소 위험 (tension; SW-01; inference) / 통합 및 검증 비용 증가로 인한 총비용 절감 불확실성 (tension; SW-01; inference)
- 원문 Reference ID: [SW-01]
- 주요 Evidence ID: [SW-implementation] / [SW-kernel] / [SW-limit] / [SW-memory] / [SW-principle] / [SW-quality]

### Photonic-CXL (HW-01)

- 기술 유형: HW
- 핵심 접근: 저자는 광학 패브릭과 CXL 호스트 인터페이스로 공유 메모리 어플라이언스 구조를 제안한다.
- 선정 방식: Human-based
- 선정 이유: 메모리 확장과 호스트 경로·전용 인프라·검증 수준을 평가하기 위해 선정
- 핵심 메커니즘: 저자는 광학 패브릭과 CXL 호스트 인터페이스로 공유 메모리 어플라이언스 구조를 제안한다.
- 주요 기대효과: 반복 문맥을 재사용하는 고동시성 QA의 메모리 확장 후보이나, 실제 장비 검증·호스트 경로·비용 확인이 선행되어야 한다. (inference)
- 주요 위험: 단일 CXL 호스트 경로의 대역폭 제약과 캐시 재사용 패턴 의존 (domain/HW-01/latency; inference) / 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존 (domain/HW-01/hardware_dependency; fact) / 물리 PF 장비와 프레임워크 커넥터의 종단간 통합 미검증 (domain/HW-01/deployment; inference) / 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존성 (opinion; HW-01; inference) / 물리 장비 미검증으로 인한 성능·품질 불확실성 (opinion; HW-01; inference) / 통합 및 운용 검증 미완료로 인한 도입 위험 (opinion; HW-01; inference) / 전용 인프라 투자 부담과 운용 복잡성 (tension; HW-01; inference) / 미검증된 성능과 품질로 인한 도입 위험 (tension; HW-01; inference)
- 원문 Reference ID: [HW-01]
- 주요 Evidence ID: [HW-architecture] / [HW-emulation] / [HW-host-limit] / [HW-integration] / [HW-pending] / [HW-serving]

## 3. 핵심 평가 요약 재료

최종 SUMMARY가 아니라 원래 평가와 새 종합 의견을 연결하는 재료입니다.

### RDKV

- 핵심 평가: 기존 GPU 기반 장문맥 QA의 메모리 절감 후보이나, 목표 QA 품질과 TriZone 통합 검증이 선행되어야 한다.
- 새 종합 의견: RDKV는 GPU 기반 장문맥 QA에서 메모리 사용량을 효과적으로 줄여 HBM 부족 문제를 완화할 수 있으나, 품질 저하와 통합 검증 부담이 존재한다.
- 주요 적용 조건: 긴 입력·상대적으로 짧은 생성이며 품질 손실을 별도 검증하는 환경
- 핵심 가치: 메모리가 부족한 QA 운영자에게 기존 장비에서 긴 문맥을 처리할 가능성이 고객 가치가 된다.
- 핵심 제약: 긴 문맥 조건의 품질 손실: FullKV보다 낮은 RULER 결과가 보고됨 (domain/SW-01/quality; fact) / TriZone 통합·캘리브레이션·회귀 검증 부담 (domain/SW-01/deployment; inference) / prefill 후 비트 배정을 고정하며 생성 중 attention 변화에 따른 재평가를 하지 않음 (domain/SW-01/domain_fit; inference) / 품질 손실로 인한 QA 정확도 저하 가능성 (opinion; SW-01; inference) / 통합 및 검증에 따른 개발·운영 비용 증가 (opinion; SW-01; inference) / GPU 호환성 및 실제 서비스 지연 개선 미확인 (opinion; SW-01; inference) / 품질 저하로 인한 QA 정확도 감소 위험 (tension; SW-01; inference) / 통합 및 검증 비용 증가로 인한 총비용 절감 불확실성 (tension; SW-01; inference)
- 가장 중요한 미확인 사항: RDKV 고유 시장의 규모·성장률·지역·기간은 두 논문 범위에서 확인하지 못했다. (market/SW-01/market_size_growth; 미확인) / 실제 유료 고객·상용 배포를 증명하는 자료를 이번 입력에 확보하지 않았다. 미채택이라는 뜻은 아니다. (market/SW-01/adoption; 미확인) / 논문에서 비교에 사용한 오픈소스 기준선을 RDKV의 공식 프레임워크 지원으로 간주할 수 없다. (market/SW-01/ecosystem; 미확인) / 경쟁사의 RDKV 지지·반대 원문을 확보하지 않았다. 비교 벤치마크는 경쟁사의 반응이 아니다. (stakeholders/SW-01/competitors; 미확인) / RDKV에 대한 투자·애널리스트·미디어의 직접 평가를 확보하지 않았다. (stakeholders/SW-01/investors_analysts_media; 미확인) / 목표 QA 서비스의 다중 사용자 동시성·처리량 요구값과 운영 측정 자료를 확보하지 않았다. (domain/SW-01/throughput; 미확인) / 실제 통합 인건비와 서비스 환경의 운용 검증 자료 부족 (domain/SW-01/deployment; 미확인) / 목표 문맥 길이·동시성·품질 허용치 미확인 (opinion; SW-01; inference; 미확인) / 실제 서비스 검증 및 다중 사용자 동시성 처리량 미확인 (opinion; SW-01; inference; 미확인) / 실제 서비스 품질 및 비용 절감 효과 미확인 (tension; SW-01; inference; 미확인)
- 주요 Evidence ID: [SW-implementation] / [SW-kernel] / [SW-limit] / [SW-memory] / [SW-quality]

### Photonic-CXL

- 핵심 평가: 반복 문맥을 재사용하는 고동시성 QA의 메모리 확장 후보이나, 실제 장비 검증·호스트 경로·비용 확인이 선행되어야 한다.
- 새 종합 의견: Photonic-CXL은 공유 메모리 확장으로 KV 수용량 병목을 완화할 잠재력이 있으나, 전용 하드웨어 의존성과 통합 검증 미완료로 도입 위험이 존재한다.
- 주요 적용 조건: 반복 문맥·높은 동시성으로 캐시 수용량이 병목인 환경
- 핵심 가치: 반복 문맥의 캐시 축출·재계산이 병목인 운영자에게 응답시간 안정화의 잠재 가치가 있다.
- 핵심 제약: 단일 CXL 호스트 경로의 대역폭 제약과 캐시 재사용 패턴 의존 (domain/HW-01/latency; inference) / 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존 (domain/HW-01/hardware_dependency; fact) / 물리 PF 장비와 프레임워크 커넥터의 종단간 통합 미검증 (domain/HW-01/deployment; inference) / 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존성 (opinion; HW-01; inference) / 물리 장비 미검증으로 인한 성능·품질 불확실성 (opinion; HW-01; inference) / 통합 및 운용 검증 미완료로 인한 도입 위험 (opinion; HW-01; inference) / 전용 인프라 투자 부담과 운용 복잡성 (tension; HW-01; inference) / 미검증된 성능과 품질로 인한 도입 위험 (tension; HW-01; inference)
- 가장 중요한 미확인 사항: Photonic-CXL 어플라이언스 고유 시장의 규모·성장률은 두 논문만으로 확인하지 못했다. (market/HW-01/market_size_growth; 미확인) / 이 어플라이언스의 실제 고객 도입 증거를 확보하지 않았다. 관련 CXL 제품의 도입을 대신 쓰지 않는다. (market/HW-01/adoption; 미확인) / 타 공급자의 Photonic-CXL에 대한 찬반 입장을 확보하지 않았다. 저자의 관련 기술 비교는 직접 반응이 아니다. (stakeholders/HW-01/competitors; 미확인) / Photonic-CXL에 대한 독립 투자·애널리스트·미디어 평가를 확보하지 않았다. (stakeholders/HW-01/investors_analysts_media; 미확인) / 실배포·장비 가격·운영비·비용 편익 분석 자료 부족 (domain/HW-01/deployment; 미확인) / 목표 QA 품질 및 지연 SLO 충족 여부 미확인 (opinion; HW-01; inference; 미확인) / 실제 고객 도입 및 시장 규모 미확인 (opinion; HW-01; inference; 미확인) / 실제 비용 대비 편익 비율 미확인 (tension; HW-01; inference; 미확인)
- 주요 Evidence ID: [HW-architecture] / [HW-emulation] / [HW-host-limit] / [HW-integration] / [HW-pending] / [HW-serving]

### 전체 평가 상태

- 유효 관점 칸: 8/8
- 유효 criterion 블록: 46/46
- unknown 항목 수: 10
- failed 항목 수: 0
- 종합 상태: partial
- 보고서 생성 조건: allowed_with_gaps
- 자동 처리 결과 및 남은 자료 공백: market/SW-01/market_size_growth: RDKV 고유 시장의 규모·성장률·지역·기간은 두 논문 범위에서 확인하지 못했다. / market/SW-01/adoption: 실제 유료 고객·상용 배포를 증명하는 자료를 이번 입력에 확보하지 않았다. 미채택이라는 뜻은 아니다. / market/SW-01/ecosystem: 논문에서 비교에 사용한 오픈소스 기준선을 RDKV의 공식 프레임워크 지원으로 간주할 수 없다. / market/HW-01/market_size_growth: Photonic-CXL 어플라이언스 고유 시장의 규모·성장률은 두 논문만으로 확인하지 못했다. / market/HW-01/adoption: 이 어플라이언스의 실제 고객 도입 증거를 확보하지 않았다. 관련 CXL 제품의 도입을 대신 쓰지 않는다. / stakeholders/SW-01/competitors: 경쟁사의 RDKV 지지·반대 원문을 확보하지 않았다. 비교 벤치마크는 경쟁사의 반응이 아니다. / stakeholders/SW-01/investors_analysts_media: RDKV에 대한 투자·애널리스트·미디어의 직접 평가를 확보하지 않았다. / stakeholders/HW-01/competitors: 타 공급자의 Photonic-CXL에 대한 찬반 입장을 확보하지 않았다. 저자의 관련 기술 비교는 직접 반응이 아니다. / stakeholders/HW-01/investors_analysts_media: Photonic-CXL에 대한 독립 투자·애널리스트·미디어 평가를 확보하지 않았다. / domain/SW-01/throughput: 목표 QA 서비스의 다중 사용자 동시성·처리량 요구값과 운영 측정 자료를 확보하지 않았다. / domain/SW-01/deployment: 실제 통합 인건비와 서비스 환경의 운용 검증 자료 부족 / domain/HW-01/deployment: 실배포·장비 가격·운영비·비용 편익 분석 자료 부족 / 미확인 항목 또는 실패 결과가 있다. / 도메인 목표값 일부가 TBD다. / TRL 상위 단계 근거가 미확인이다. / 독립 검증 근거가 확인되지 않았다. / 일부 근거 신뢰도는 상위 Agent가 평가하지 않았다.

## 4. 관점별 평가

### 공통 판정 Rubric

- favorable: 선택 도메인의 명시된 요구조건을 충족하는 검증 가능한 근거가 있다.
- conditional: 조건부 충족 또는 요구값이 TBD다.
- unfavorable: 선택 도메인의 핵심 요구와 충돌하는 근거가 있다.
- unknown: 판단 근거 부족. failed: 실행·파싱·처리 실패. 서로 혼용하지 않는다.
- not_applicable: 기술/도메인에 적용되지 않으며 평가 문장에 사유가 필요하다.
- 판정의 합산·평균·총점 순위를 만들지 않는다. 논문 주장은 독립 검증이 아니다.

### 4.1 기술 성숙도

#### [technical][SW-01][mechanism]

- criterion_id: mechanism
- 판정: conditional
- 사실·추론: fact
- 분석 범위: global
- 선택 도메인과의 관련성: direct
- 평가: 저자는 제거와 양자화를 비트 배정 문제로 결합하고, TriZone으로 압축 캐시를 어텐션 커널과 연결한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 선정 논문 v1의 알고리즘·구현 범위
- Evidence ID: [SW-principle] / [SW-kernel]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [technical][SW-01][validation_scope]

- criterion_id: validation_scope
- 판정: conditional
- 사실·추론: inference
- 분석 범위: global
- 선택 도메인과의 관련성: direct
- 평가: GPU 기반 구현과 벤치마크를 보고했으나, 실제 서비스의 품질·동시성·운용 보증과 구분한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 저자 실험이며 이 실습에서 재현하지 않음
- Evidence ID: [SW-implementation] / [SW-quality]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [technical][SW-01][maturity]

- criterion_id: maturity
- 판정: conditional
- 사실·추론: inference
- 분석 범위: global
- 선택 도메인과의 관련성: direct
- 평가: 공개 근거로 확인한 TRL 4 (추정)
- 해당 기술과의 관련성: unknown
- 적용 조건: 선정 논문 v1에 기록된 검증 범위
- Evidence ID: [SW-implementation] / [SW-principle] / [SW-quality]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [technical][HW-01][mechanism]

- criterion_id: mechanism
- 판정: conditional
- 사실·추론: fact
- 분석 범위: global
- 선택 도메인과의 관련성: direct
- 평가: 저자는 광학 패브릭과 CXL 호스트 인터페이스로 공유 메모리 어플라이언스 구조를 제안한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 물리 배포 완료가 아닌 제안 구조
- Evidence ID: [HW-architecture]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [technical][HW-01][validation_scope]

- criterion_id: validation_scope
- 판정: conditional
- 사실·추론: fact
- 분석 범위: global
- 선택 도메인과의 관련성: direct
- 평가: PF 경로는 에뮬레이션, 서빙은 시뮬레이션으로 평가했으며 실제 PF 장비의 종단간 검증은 미완료로 명시한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 기존 GPU/DRAM 실험을 PF 장비의 실측으로 대체하지 않음
- Evidence ID: [HW-emulation] / [HW-serving] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [technical][HW-01][maturity]

- criterion_id: maturity
- 판정: conditional
- 사실·추론: inference
- 분석 범위: global
- 선택 도메인과의 관련성: direct
- 평가: 공개 근거로 확인한 TRL 3 (추정)
- 해당 기술과의 관련성: unknown
- 적용 조건: 선정 논문 v1에 기록된 검증 범위
- Evidence ID: [HW-architecture] / [HW-emulation]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

### 4.2 시장성

#### [market][SW-01][market_size_growth]

- criterion_id: market_size_growth
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: RDKV 고유 시장의 규모·성장률·지역·기간은 두 논문 범위에서 확인하지 못했다.
- 추가 조사 필요: true

#### [market][SW-01][commercialization]

- criterion_id: commercialization
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 별도 메모리 장비보다 추론 소프트웨어 기능으로 제공하는 사업화 경로를 가정할 수 있다. 판매 제품이 확인된 것은 아니다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 커널 통합과 배포 권한을 별도 확인해야 하는 사업화 가설
- Evidence ID: [SW-kernel] / [SW-impact]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [market][SW-01][adoption]

- criterion_id: adoption
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 실제 유료 고객·상용 배포를 증명하는 자료를 이번 입력에 확보하지 않았다. 미채택이라는 뜻은 아니다.
- 추가 조사 필요: true

#### [market][SW-01][ecosystem]

- criterion_id: ecosystem
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 논문에서 비교에 사용한 오픈소스 기준선을 RDKV의 공식 프레임워크 지원으로 간주할 수 없다.
- 추가 조사 필요: true

#### [market][SW-01][cost]

- criterion_id: cost
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 기존 GPU의 메모리 사용을 줄이면 증설 부담을 완화할 가능성이 있지만, 통합 인건비를 포함한 실제 총비용 절감은 미확인이다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 목표 품질 유지 및 통합 비용이 메모리 절감 편익을 상쇄하지 않을 때
- Evidence ID: [SW-memory] / [SW-kernel]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [market][SW-01][customer_value]

- criterion_id: customer_value
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 메모리가 부족한 QA 운영자에게 기존 장비에서 긴 문맥을 처리할 가능성이 고객 가치가 된다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 운영비 절감은 추론이며 품질 허용치 검증 전에는 경제적 이익을 확정하지 않음
- Evidence ID: [SW-memory]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [market][HW-01][market_size_growth]

- criterion_id: market_size_growth
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: Photonic-CXL 어플라이언스 고유 시장의 규모·성장률은 두 논문만으로 확인하지 못했다.
- 추가 조사 필요: true

#### [market][HW-01][commercialization]

- criterion_id: commercialization
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 메모리 어플라이언스와 호스트 어댑터를 공급하는 사업화 경로를 가정할 수 있으나, 논문은 실장비 검증을 향후 과제로 남긴다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 제품 구조 제안과 출시·판매 증거를 구분
- Evidence ID: [HW-architecture] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [market][HW-01][adoption]

- criterion_id: adoption
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 이 어플라이언스의 실제 고객 도입 증거를 확보하지 않았다. 관련 CXL 제품의 도입을 대신 쓰지 않는다.
- 추가 조사 필요: true

#### [market][HW-01][ecosystem]

- criterion_id: ecosystem
- 판정: conditional
- 사실·추론: fact
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: vLLM·SGLang·Dynamo 연결 방안을 제시하지만, vLLM 커넥터는 구현 예정 표현이므로 공식 통합 완료로 볼 수 없다.
- 해당 기술과의 관련성: unknown
- 적용 조건: v1에서 제안한 통합 경로만 평가
- Evidence ID: [HW-integration] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [market][HW-01][cost]

- criterion_id: cost
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 공유 메모리로 증설을 줄일 가능성과 전용 장비·어댑터·광학 인프라 투자 부담을 함께 검토해야 한다. 비용·편익 분석은 논문의 향후 과제다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 장비 가격·전력·유지보수와 서버 추가 구매 대안의 비용을 확보한 뒤 비교
- Evidence ID: [HW-architecture] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [market][HW-01][customer_value]

- criterion_id: customer_value
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 반복 문맥의 캐시 축출·재계산이 병목인 운영자에게 응답시간 안정화의 잠재 가치가 있다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 캐시 재사용이 높은 시뮬레이션 조건이며 모든 QA 요청의 효과를 보장하지 않음
- Evidence ID: [HW-serving]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

### 4.3 이해관계자

#### [stakeholders][SW-01][competitors]

- criterion_id: competitors
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 경쟁사의 RDKV 지지·반대 원문을 확보하지 않았다. 비교 벤치마크는 경쟁사의 반응이 아니다.
- 추가 조사 필요: true

#### [stakeholders][SW-01][adopters]

- criterion_id: adopters
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 운영자는 메모리 절감을 편익으로 볼 수 있지만, QA 품질 변화와 서비스 검증 비용도 부담할 수 있다.
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 운영자의 실제 인터뷰가 아닌 논문으로부터 도출한 이해관계 추론
- Evidence ID: [SW-memory] / [SW-quality]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [stakeholders][SW-01][developers]

- criterion_id: developers
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 개발자는 TriZone 커널·캘리브레이션·압축 예산을 통합하고 품질 회귀를 점검해야 할 것으로 해석된다.
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 실제 개발자 반응이 아닌 구현 요구에 대한 추론
- Evidence ID: [SW-kernel] / [SW-implementation] / [SW-limit]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [stakeholders][SW-01][investors_analysts_media]

- criterion_id: investors_analysts_media
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: RDKV에 대한 투자·애널리스트·미디어의 직접 평가를 확보하지 않았다.
- 추가 조사 필요: true

#### [stakeholders][HW-01][competitors]

- criterion_id: competitors
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 타 공급자의 Photonic-CXL에 대한 찬반 입장을 확보하지 않았다. 저자의 관련 기술 비교는 직접 반응이 아니다.
- 추가 조사 필요: true

#### [stakeholders][HW-01][adopters]

- criterion_id: adopters
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 운영자는 캐시 재사용 편익과 전용 장비의 조달·운용·비용 불확실성을 함께 고려할 수 있다.
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 실제 고객 도입 의견이 아닌 이해관계 추론
- Evidence ID: [HW-serving] / [HW-architecture] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [stakeholders][HW-01][developers]

- criterion_id: developers
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 개발자는 프레임워크 커넥터와 공유 메모리의 인덱스·일관성 처리를 구현·검증해야 할 것으로 해석된다.
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 공급자 저자의 설계 설명에서 추론하며 외부 개발자의 지지로 해석하지 않음
- Evidence ID: [HW-integration]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [stakeholders][HW-01][investors_analysts_media]

- criterion_id: investors_analysts_media
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: indirect
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 이해관계자 집단: unknown
- 발언 주체: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: Photonic-CXL에 대한 독립 투자·애널리스트·미디어 평가를 확보하지 않았다.
- 추가 조사 필요: true

### 4.4 도메인 적용성

#### [domain][SW-01][capacity]

- criterion_id: capacity
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 저자가 보고한 압축 캐시의 메모리 절감은 HBM 부족 완화의 근거가 된다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 원문 모델·장비·문맥·압축 예산 범위에서의 보고이며 목표 서비스에서 재검증
- Evidence ID: [SW-memory]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][quality]

- criterion_id: quality
- 판정: conditional
- 사실·추론: fact
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 압축 방식이므로 FullKV와 동일 품질을 보장하지 않는다. RULER의 긴 문맥 조건에서 FullKV보다 낮은 결과도 확인된다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 문서 QA의 정답률·근거 회수율 허용 손실을 별도 정의해야 함
- Evidence ID: [SW-quality]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 긴 문맥 조건의 품질 손실: FullKV보다 낮은 RULER 결과가 보고됨
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][latency]

- criterion_id: latency
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 압축 상태를 유지하는 커널 경로가 지연 개선의 조건이며, 단순 저비트 저장만으로 서비스 지연 개선을 확정할 수 없다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 통합된 커널의 목표 장비 지연 및 상위 백분위 지연을 실측해야 함
- Evidence ID: [SW-kernel]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][throughput]

- criterion_id: throughput
- 판정: unknown
- 사실·추론: unknown
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 판단 보류
- 해당 기술과의 관련성: unknown
- 적용 조건: 조사 범위는 선정 논문 v1 두 편에 한정
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 목표 QA 서비스의 다중 사용자 동시성·처리량 요구값과 운영 측정 자료를 확보하지 않았다.
- 추가 조사 필요: true

#### [domain][SW-01][gpu_compatibility]

- criterion_id: gpu_compatibility
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 기존 NVIDIA GPU에서 구현 실험을 수행한 근거는 있으나 모든 GPU·엔진에서 호환된다는 뜻은 아니다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 원문에 보고된 장비에서 목표 장비·서빙 엔진으로 이식 검증
- Evidence ID: [SW-implementation]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][hardware_dependency]

- criterion_id: hardware_dependency
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 논문의 구현은 별도 광학 메모리 어플라이언스가 아닌 GPU와 압축 커널을 사용한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 특정 커널·장비 의존성을 무시한 범용 호환성으로 확대하지 않음
- Evidence ID: [SW-implementation] / [SW-kernel]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][deployment]

- criterion_id: deployment
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: TriZone과 캘리브레이션을 기존 서빙 경로에 통합하고 품질·지연 회귀 검사를 수행해야 한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 실제 엔진 연결 난이도·개발 기간은 미측정
- Evidence ID: [SW-kernel] / [SW-implementation]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: TriZone 통합·캘리브레이션·회귀 검증 부담
- 미확인 사항: 실제 통합 인건비와 서비스 환경의 운용 검증 자료 부족
- 추가 조사 필요: true

#### [domain][SW-01][maturity]

- criterion_id: maturity
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 논문에 구현·실험 근거가 있어도 상용 QA 서비스의 운용 검증과 같지는 않다.
- 해당 기술과의 관련성: unknown
- 적용 조건: TRL 숫자는 technical 체크리스트 결과를 사용
- Evidence ID: [SW-implementation] / [SW-limit]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][customer_value]

- criterion_id: customer_value
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 같은 장비의 문맥 처리 여지를 늘리는 편익은 QA 품질이 허용 범위에 남을 때 유효하다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 시장 관점의 메모리 편익에 QA 품질 조건을 추가
- Evidence ID: [SW-memory] / [SW-quality]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][SW-01][domain_fit]

- criterion_id: domain_fit
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 기존 GPU 기반 장문맥 QA의 메모리 절감 후보이나, 목표 QA 품질과 TriZone 통합 검증이 선행되어야 한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 긴 입력·상대적으로 짧은 생성이며 품질 손실을 별도 검증하는 환경
- Evidence ID: [SW-memory] / [SW-quality] / [SW-kernel] / [SW-limit]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: prefill 후 비트 배정을 고정하며 생성 중 attention 변화에 따른 재평가를 하지 않음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][capacity]

- criterion_id: capacity
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 공유 메모리 확장은 KV 수용량 부족을 완화하는 설계이나, 논문 구조의 실제 설치 성능과는 구분한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 대상 호스트 연결·용량 배분·실장비 준비가 필요
- Evidence ID: [HW-architecture]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][quality]

- criterion_id: quality
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: KV를 보관·재사용하는 방향은 압축 손실 회피에 의미가 있으나, 문서 QA 정답 정확성을 보장하거나 검증한 것은 아니다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 데이터 보존과 모델 답변 정확성을 분리하고 QA 벤치마크를 별도 수행
- Evidence ID: [HW-serving] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][latency]

- criterion_id: latency
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 캐시 재사용에 따른 응답시간 편익은 호스트 대역폭·접근 경로와 워크로드에 의존한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 서빙 시뮬레이션을 실제 서비스의 지연 SLO 충족으로 간주하지 않음
- Evidence ID: [HW-host-limit] / [HW-serving]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 단일 CXL 호스트 경로의 대역폭 제약과 캐시 재사용 패턴 의존
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][throughput]

- criterion_id: throughput
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 대화 수 증가 시 캐시 축출 완화 결과는 확장 가능성의 근거이나 실제 운영 처리량을 확정하지 못한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 프리픽스 재사용이 있는 대화 부하와 실제 QA 요청 분포의 차이를 검증
- Evidence ID: [HW-serving] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][gpu_compatibility]

- criterion_id: gpu_compatibility
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: PF-NIC를 통한 호스트 연결 경로를 제안한다. 모든 GPU를 새로 설계해야 한다는 결론은 이 논문에서 도출하지 않는다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 호스트 PCIe/CXL·DMA·펌웨어·소프트웨어 통합 조건을 별도 확인
- Evidence ID: [HW-architecture] / [HW-integration]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][hardware_dependency]

- criterion_id: hardware_dependency
- 판정: conditional
- 사실·추론: fact
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 전용 메모리 모듈·PF-NIC·외부 광원 등 추가 인프라가 필요하다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 기존 GPU만으로 소프트웨어 설치 즉시 사용할 수 있는 방식이 아님
- Evidence ID: [HW-architecture]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][deployment]

- criterion_id: deployment
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 물리 인프라와 프레임워크 커넥터·공유 인덱스·일관성 프로토콜의 통합 검증이 필요하다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 논문의 통합 설계를 실제 완료된 운영 구성으로 간주하지 않음
- Evidence ID: [HW-architecture] / [HW-integration] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 물리 PF 장비와 프레임워크 커넥터의 종단간 통합 미검증
- 미확인 사항: 실배포·장비 가격·운영비·비용 편익 분석 자료 부족
- 추가 조사 필요: true

#### [domain][HW-01][maturity]

- criterion_id: maturity
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 에뮬레이션·시뮬레이션 근거를 실제 PF 어플라이언스 운용 실증과 구분한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: TRL 숫자는 technical 체크리스트 결과를 사용
- Evidence ID: [HW-emulation] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][customer_value]

- criterion_id: customer_value
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 캐시 재계산 억제의 편익은 재사용 패턴과 실제 투자 비용에 따라 달라진다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 재사용이 적은 QA나 비용 제한이 큰 환경에는 동일 편익을 가정하지 않음
- Evidence ID: [HW-serving] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

#### [domain][HW-01][domain_fit]

- criterion_id: domain_fit
- 판정: conditional
- 사실·추론: inference
- 분석 범위: selected_domain
- 선택 도메인과의 관련성: direct
- 평가: 반복 문맥을 재사용하는 고동시성 QA의 메모리 확장 후보이나, 실제 장비 검증·호스트 경로·비용 확인이 선행되어야 한다.
- 해당 기술과의 관련성: unknown
- 적용 조건: 반복 문맥·높은 동시성으로 캐시 수용량이 병목인 환경
- Evidence ID: [HW-serving] / [HW-host-limit] / [HW-integration] / [HW-pending]
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 없음
- 추가 조사 필요: false

## 5. TRL 판정 결과

기술 조사 Agent가 단계별 근거를 제공하고, 검증·종합 Agent가 출처와 단계의 연속성을 검사해 최종 추정 TRL을 정한다.
시장·이해관계자·도메인 평가만으로 TRL을 추정하지 않는다. 보고서 Agent는 아래 판정과 한계를 유지한다.

### RDKV

- 추정 TRL: 4
- 판정 기준 시점: v1
- 충족한 최고 단계: 4
- 충족 근거: [SW-implementation] / [SW-principle] / [SW-quality]
- 다음 단계에 필요한 근거: 대표 워크로드·연동 환경·요구 성능·확장 조건의 검증
- 공개되지 않은 정보: 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인
- 추정 신뢰도: low
- 추정의 한계: low는 사람 검수 전 보수적 기본 표시이며 확률이 아니다. TRL은 공개 정보 기반의 팀 추정이며 실제 내부 개발·배포 수준을 확정하지 않는다. 형식·인용 검사는 주장의 진실성을 보증하지 않으며 핵심 결론은 사람이 원문과 대조한다.

#### 단계별 TRL 검토

met=단계 조건 확인, not_met=미충족 근거 확인, unknown=근거 부족. 최종 TRL은 하위 단계부터 연속 확인된 최고 단계다.

| TRL | 판정 | 판정 이유 | Evidence ID |
|---|---|---|---|
| 1 | met | 원리와 목적 함수의 문서화된 근거 | [SW-principle] |
| 2 | met | 비트 배정 및 TriZone 적용 개념을 구체화 | [SW-principle] |
| 3 | met | 벤치마크로 압축 접근의 작동을 검증한 저자 보고 | [SW-quality] |
| 4 | met | 핵심 압축·디코드 구성요소의 GPU 통합 실험을 보고 | [SW-implementation] |
| 5 | unknown | 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인 | 없음 |
| 6 | unknown | 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인 | 없음 |
| 7 | unknown | 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인 | 없음 |
| 8 | unknown | 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인 | 없음 |
| 9 | unknown | 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인 | 없음 |

### Photonic-CXL

- 추정 TRL: 3
- 판정 기준 시점: v1
- 충족한 최고 단계: 3
- 충족 근거: [HW-architecture] / [HW-emulation]
- 다음 단계에 필요한 근거: 구현된 핵심 요소, 통합 범위, 시험 결과, 목표 환경 정의
- 공개되지 않은 정보: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
- 추정 신뢰도: low
- 추정의 한계: low는 사람 검수 전 보수적 기본 표시이며 확률이 아니다. TRL은 공개 정보 기반의 팀 추정이며 실제 내부 개발·배포 수준을 확정하지 않는다. 형식·인용 검사는 주장의 진실성을 보증하지 않으며 핵심 결론은 사람이 원문과 대조한다.

#### 단계별 TRL 검토

met=단계 조건 확인, not_met=미충족 근거 확인, unknown=근거 부족. 최종 TRL은 하위 단계부터 연속 확인된 최고 단계다.

| TRL | 판정 | 판정 이유 | Evidence ID |
|---|---|---|---|
| 1 | met | 공유 메모리·광학 연결의 구조적 원리 제시 | [HW-architecture] |
| 2 | met | PF-NIC·메모리 모듈·호스트 적용 구조 정의 | [HW-architecture] |
| 3 | met | PF-NIC 및 메모리 모듈의 에뮬레이션 기반 개념 검증 | [HW-emulation] |
| 4 | unknown | 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류 | 없음 |
| 5 | unknown | 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류 | 없음 |
| 6 | unknown | 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류 | 없음 |
| 7 | unknown | 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류 | 없음 |
| 8 | unknown | 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류 | 없음 |
| 9 | unknown | 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류 | 없음 |

## 6. 관점 간 종합

- 종합 실행 상태: completed
- 모델: gpt-4.1-mini
- 이번 실행 API 시도: 2
- 자동 의미 검사: passed
- 자동 수정 횟수: 0
- 입력과 종합 의견의 정합성을 자동 검사한다. 외부 사실의 진실성 보증은 아니다.

### 새로운 종합 의견

#### 새로운 종합 의견 1

- 종합 의견: RDKV는 GPU 기반 장문맥 QA에서 메모리 사용량을 효과적으로 줄여 HBM 부족 문제를 완화할 수 있으나, 품질 저하와 통합 검증 부담이 존재한다.
- 관점 연결 설명: 시장 평가에서 메모리 절감이 운영비 절감 가능성으로 인식되나, 도메인 평가에서는 압축으로 인한 품질 손실과 TriZone 통합·캘리브레이션의 검증 필요성이 지적된다. 이해관계자 평가에서는 운영자와 개발자가 품질 변화와 검증 비용 부담을 함께 고려해야 한다고 추론된다.
- 관련 기술: SW-01
- 연결된 평가 ID: market/SW-01/cost / stakeholders/SW-01/developers / domain/SW-01/domain_fit / domain/SW-01/quality / domain/SW-01/deployment
- 성립 조건: 목표 QA 품질 유지 및 TriZone 통합 검증 완료 / 통합 인건비가 메모리 절감 편익을 상쇄하지 않을 때 / 긴 입력과 상대적으로 짧은 생성 환경에서 품질 손실 별도 검증
- 추가 위험: 품질 손실로 인한 QA 정확도 저하 가능성 / 통합 및 검증에 따른 개발·운영 비용 증가 / GPU 호환성 및 실제 서비스 지연 개선 미확인
- 미확인 사항: 목표 문맥 길이·동시성·품질 허용치 미확인 / 실제 서비스 검증 및 다중 사용자 동시성 처리량 미확인
- Evidence ID: [SW-implementation] / [SW-kernel] / [SW-limit] / [SW-memory] / [SW-quality]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false

#### 새로운 종합 의견 2

- 종합 의견: Photonic-CXL은 공유 메모리 확장으로 KV 수용량 병목을 완화할 잠재력이 있으나, 전용 하드웨어 의존성과 통합 검증 미완료로 도입 위험이 존재한다.
- 관점 연결 설명: 시장 평가에서 전용 장비와 광학 인프라 투자 부담이 비용·편익 분석의 주요 변수로 지적되며, 도메인 평가에서는 물리 장비의 종단간 검증 미완료와 추가 인프라 의존성이 도입 제약으로 작용한다. 이해관계자 평가에서는 운영자가 비용 불확실성과 캐시 재사용 편익을 함께 고려해야 한다고 추론된다.
- 관련 기술: HW-01
- 연결된 평가 ID: market/HW-01/cost / stakeholders/HW-01/developers / domain/HW-01/domain_fit / domain/HW-01/hardware_dependency / domain/HW-01/deployment
- 성립 조건: 물리 PF 어플라이언스의 종단간 검증 완료 / 호스트 경로 및 비용 분석이 확보되어야 함 / 반복 문맥과 높은 동시성 환경에서 캐시 재사용 패턴 확인
- 추가 위험: 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존성 / 물리 장비 미검증으로 인한 성능·품질 불확실성 / 통합 및 운용 검증 미완료로 인한 도입 위험
- 미확인 사항: 목표 QA 품질 및 지연 SLO 충족 여부 미확인 / 실제 고객 도입 및 시장 규모 미확인
- Evidence ID: [HW-architecture] / [HW-host-limit] / [HW-integration] / [HW-pending] / [HW-serving]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false

### 일치하는 평가

#### 일치하는 평가 1

- 종합 의견: 두 기술 모두 장문맥 QA에서 KV 메모리 병목 완화라는 공통 목표를 가지며, 고객 가치로 메모리 부족 완화와 응답시간 안정화 가능성을 공유한다.
- 관점 연결 설명: 시장과 도메인 평가에서 RDKV는 메모리 절감, Photonic-CXL은 공유 메모리 확장으로 각각 병목 완화를 추구한다. 두 기술 모두 고객 가치로 긴 문맥 처리 가능성과 응답시간 개선 잠재력을 인정받으나, 품질과 비용 조건이 중요하다.
- 관련 기술: SW-01 / HW-01
- 연결된 평가 ID: market/SW-01/customer_value / domain/SW-01/customer_value / market/HW-01/customer_value / domain/HW-01/customer_value
- 성립 조건: QA 품질 허용 범위 내에서 메모리 병목 완화가 유효할 때
- 추가 위험: 별도 기재 없음; 위험이 없다는 뜻이 아님
- 미확인 사항: 시장 규모 및 성장률 미확인
- Evidence ID: [HW-pending] / [HW-serving] / [SW-memory] / [SW-quality]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false
- 일치 내용: 두 기술 모두 장문맥 QA에서 KV 메모리 병목 완화라는 공통 목표를 가지며, 고객 가치로 메모리 부족 완화와 응답시간 안정화 가능성을 공유한다.
- 관련 평가 기준: customer_value
- 관련 관점: domain / market

### 상충하는 평가

#### 상충하는 평가 1

- 종합 의견: RDKV는 메모리 절감 편익과 품질 저하 및 통합 검증 부담 사이에 상충이 존재한다.
- 관점 연결 설명: 도메인 평가에서 압축으로 인한 품질 손실과 TriZone 통합·캘리브레이션의 검증 부담이 지적되며, 시장 평가에서는 통합 비용이 메모리 절감 편익을 상쇄할 가능성이 언급된다.
- 관련 기술: SW-01
- 연결된 평가 ID: technical/SW-01/validation_scope / market/SW-01/cost / domain/SW-01/quality / domain/SW-01/deployment
- 성립 조건: 목표 품질 유지 및 통합 비용 균형 미확인
- 추가 위험: 품질 저하로 인한 QA 정확도 감소 위험 / 통합 및 검증 비용 증가로 인한 총비용 절감 불확실성
- 미확인 사항: 실제 서비스 품질 및 비용 절감 효과 미확인
- Evidence ID: [SW-implementation] / [SW-kernel] / [SW-memory] / [SW-quality]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false
- 상충 원인: 도메인 평가에서 압축으로 인한 품질 손실과 TriZone 통합·캘리브레이션의 검증 부담이 지적되며, 시장 평가에서는 통합 비용이 메모리 절감 편익을 상쇄할 가능성이 언급된다.
- 기술 성숙도 관점: GPU 기반 구현과 벤치마크를 보고했으나, 실제 서비스의 품질·동시성·운용 보증과 구분한다.
- 시장성 관점: 기존 GPU의 메모리 사용을 줄이면 증설 부담을 완화할 가능성이 있지만, 통합 인건비를 포함한 실제 총비용 절감은 미확인이다.
- 이해관계자 관점: 이 의견에 연결된 평가 없음; 해당 관점 전체의 자료 부재를 뜻하지 않음
- 도메인 적용성 관점: 압축 방식이므로 FullKV와 동일 품질을 보장하지 않는다. RULER의 긴 문맥 조건에서 FullKV보다 낮은 결과도 확인된다. / TriZone과 캘리브레이션을 기존 서빙 경로에 통합하고 품질·지연 회귀 검사를 수행해야 한다.
- 관련 평가 기준: cost / deployment / quality / validation_scope
- 관련 관점: domain / market / technical

#### 상충하는 평가 2

- 종합 의견: Photonic-CXL은 하드웨어 의존성과 미검증된 통합으로 인한 비용·운용 위험과 캐시 재사용 편익 간에 상충이 존재한다.
- 관점 연결 설명: 도메인 평가에서 전용 메모리 모듈, PF-NIC, 외부 광원 등 인프라 의존성이 비용과 운용 위험을 증가시키며, 시장 평가에서는 비용·편익 분석 미완료가 도입 판단을 어렵게 한다. 운영자는 캐시 재사용 편익과 비용 불확실성을 함께 고려해야 한다.
- 관련 기술: HW-01
- 연결된 평가 ID: technical/HW-01/validation_scope / market/HW-01/cost / domain/HW-01/hardware_dependency / domain/HW-01/deployment
- 성립 조건: 물리 장비 검증 및 비용 분석 미완료
- 추가 위험: 전용 인프라 투자 부담과 운용 복잡성 / 미검증된 성능과 품질로 인한 도입 위험
- 미확인 사항: 실제 비용 대비 편익 비율 미확인
- Evidence ID: [HW-architecture] / [HW-emulation] / [HW-integration] / [HW-pending] / [HW-serving]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false
- 상충 원인: 도메인 평가에서 전용 메모리 모듈, PF-NIC, 외부 광원 등 인프라 의존성이 비용과 운용 위험을 증가시키며, 시장 평가에서는 비용·편익 분석 미완료가 도입 판단을 어렵게 한다. 운영자는 캐시 재사용 편익과 비용 불확실성을 함께 고려해야 한다.
- 기술 성숙도 관점: PF 경로는 에뮬레이션, 서빙은 시뮬레이션으로 평가했으며 실제 PF 장비의 종단간 검증은 미완료로 명시한다.
- 시장성 관점: 공유 메모리로 증설을 줄일 가능성과 전용 장비·어댑터·광학 인프라 투자 부담을 함께 검토해야 한다. 비용·편익 분석은 논문의 향후 과제다.
- 이해관계자 관점: 이 의견에 연결된 평가 없음; 해당 관점 전체의 자료 부재를 뜻하지 않음
- 도메인 적용성 관점: 전용 메모리 모듈·PF-NIC·외부 광원 등 추가 인프라가 필요하다. / 물리 인프라와 프레임워크 커넥터·공유 인덱스·일관성 프로토콜의 통합 검증이 필요하다.
- 관련 평가 기준: cost / deployment / hardware_dependency / validation_scope
- 관련 관점: domain / market / technical

### 조건에 따른 가치 차이

#### 조건에 따른 가치 차이 1

- 종합 의견: RDKV는 품질 유지와 통합 검증이 완료될 때 적합하며, Photonic-CXL은 물리 인프라와 비용 검증이 완료되어야 적합하다.
- 관점 연결 설명: RDKV는 긴 입력과 상대적으로 짧은 생성 환경에서 품질 손실 검증과 TriZone 통합 검증이 필요하며, Photonic-CXL은 반복 문맥과 높은 동시성 환경에서 캐시 재사용 패턴 확인과 물리 인프라 통합 검증이 선행되어야 한다.
- 관련 기술: SW-01 / HW-01
- 연결된 평가 ID: market/SW-01/cost / domain/SW-01/domain_fit / market/HW-01/cost / domain/HW-01/domain_fit
- 성립 조건: RDKV: 목표 QA 품질과 TriZone 통합 검증 완료 / Photonic-CXL: 물리 인프라 및 비용 검증 완료
- 추가 위험: 별도 기재 없음; 위험이 없다는 뜻이 아님
- 미확인 사항: 목표 품질 유지 및 비용 균형 미확인
- Evidence ID: [HW-architecture] / [HW-host-limit] / [HW-integration] / [HW-pending] / [HW-serving] / [SW-kernel] / [SW-limit] / [SW-memory] / [SW-quality]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false
- 조건: RDKV: 목표 QA 품질과 TriZone 통합 검증 완료 / Photonic-CXL: 물리 인프라 및 비용 검증 완료
- 조건부 적합성 결론: RDKV는 품질 유지와 통합 검증이 완료될 때 적합하며, Photonic-CXL은 물리 인프라와 비용 검증이 완료되어야 적합하다.
- RDKV가 상대적으로 적합한 조건: 목표 QA 품질과 TriZone 통합 검증 완료
- Photonic-CXL이 상대적으로 적합한 조건: 물리 인프라와 비용 검증 완료
- 판단 불가 조건: 목표 품질 및 비용 균형 미확인
- RDKV 해석: 목표 QA 품질과 TriZone 통합 검증 완료
- Photonic-CXL 해석: 물리 인프라와 비용 검증 완료

### 병행 가능성

병행 해석은 입력 평가에 기반한 가설이다. 공동 실증 여부는 제공된 근거 범위에서만 해석하며 실제 통합 가능성이나 효과가 검증되었다는 뜻이 아니다.

#### 병행 가능성 1

- 종합 의견: 두 기술은 KV 메모리 병목 완화라는 공통 목표를 공유하며, 병행 적용 시 통합 비용과 품질·지연 위험 검증이 필요하다.
- 관점 연결 설명: 기술 평가에서 RDKV는 SW 압축, Photonic-CXL은 HW 확장으로 각각 접근하며, 도메인 평가에서는 두 기술의 통합 시 TriZone 통합·캘리브레이션과 물리 인프라·커넥터 호환성 검증이 요구된다. 공동 실증과 고객 반응 자료는 제공되지 않았다.
- 관련 기술: SW-01 / HW-01
- 연결된 평가 ID: technical/SW-01/mechanism / domain/SW-01/deployment / technical/HW-01/mechanism / domain/HW-01/deployment
- 성립 조건: 통합 시 품질·지연 회귀 및 비용 검증 필요
- 추가 위험: 통합 비용 증가 및 품질·지연 위험
- 미확인 사항: 공동 실증 및 고객 반응 자료 미제공
- Evidence ID: [HW-architecture] / [HW-integration] / [HW-pending] / [SW-implementation] / [SW-kernel] / [SW-principle]
- 신뢰도: medium
- 사실·추론: inference
- 절대 우열 판정: false
- 병행 가능성: 두 기술은 KV 메모리 병목 완화라는 공통 목표를 공유하며, 병행 적용 시 통합 비용과 품질·지연 위험 검증이 필요하다.
- 기대 효과: 기술 평가에서 RDKV는 SW 압축, Photonic-CXL은 HW 확장으로 각각 접근하며, 도메인 평가에서는 두 기술의 통합 시 TriZone 통합·캘리브레이션과 물리 인프라·커넥터 호환성 검증이 요구된다. 공동 실증과 고객 반응 자료는 제공되지 않았다.
- 필요한 조건: 통합 시 품질·지연 회귀 및 비용 검증 필요
- 추가되는 위험: 통합 비용 증가 및 품질·지연 위험

### 직접 비교하면 안 되는 결과

자동 검사에서 직접 비교 불가로 분류한 쌍 없음. 비교 입력 부재일 수도 있으며, 동등한 실험이나 배수 우열을 보증하지 않는다.

## 7. 미확인 사항 및 한계

### 보고서 용도와 제출 전 보완

본 결과의 상위 관점별 평가는 모의 Agent 입력을 포함하며, 실제 고객 인터뷰나 전체 RAG 실행 및 성능 재현 결과를 의미하지 않는다.
현재 입력은 보고서 생성기 개발·LaTeX 변환 테스트·초안용이며 최종 제출 완료 자료로 표시하지 않는다.
현재 채택 근거는 논문뿐이다. 시장 규모·실제 채택·당사자 반응은 외부 원문 확인 전까지 미확인으로 유지한다.
신뢰도 unavailable은 상위 Agent의 미평가를 뜻한다. 출력 품질을 높이려고 임의로 high/medium/low로 바꾸지 않는다.

### 자료 공백

- market/SW-01/market_size_growth: RDKV 고유 시장의 규모·성장률·지역·기간은 두 논문 범위에서 확인하지 못했다.
- market/SW-01/adoption: 실제 유료 고객·상용 배포를 증명하는 자료를 이번 입력에 확보하지 않았다. 미채택이라는 뜻은 아니다.
- market/SW-01/ecosystem: 논문에서 비교에 사용한 오픈소스 기준선을 RDKV의 공식 프레임워크 지원으로 간주할 수 없다.
- market/HW-01/market_size_growth: Photonic-CXL 어플라이언스 고유 시장의 규모·성장률은 두 논문만으로 확인하지 못했다.
- market/HW-01/adoption: 이 어플라이언스의 실제 고객 도입 증거를 확보하지 않았다. 관련 CXL 제품의 도입을 대신 쓰지 않는다.
- stakeholders/SW-01/competitors: 경쟁사의 RDKV 지지·반대 원문을 확보하지 않았다. 비교 벤치마크는 경쟁사의 반응이 아니다.
- stakeholders/SW-01/investors_analysts_media: RDKV에 대한 투자·애널리스트·미디어의 직접 평가를 확보하지 않았다.
- stakeholders/HW-01/competitors: 타 공급자의 Photonic-CXL에 대한 찬반 입장을 확보하지 않았다. 저자의 관련 기술 비교는 직접 반응이 아니다.
- stakeholders/HW-01/investors_analysts_media: Photonic-CXL에 대한 독립 투자·애널리스트·미디어 평가를 확보하지 않았다.
- domain/SW-01/throughput: 목표 QA 서비스의 다중 사용자 동시성·처리량 요구값과 운영 측정 자료를 확보하지 않았다.
- domain/SW-01/deployment: 실제 통합 인건비와 서비스 환경의 운용 검증 자료 부족
- domain/HW-01/deployment: 실배포·장비 가격·운영비·비용 편익 분석 자료 부족
- 미확인 항목 또는 실패 결과가 있다.
- 도메인 목표값 일부가 TBD다.
- TRL 상위 단계 근거가 미확인이다.
- 독립 검증 근거가 확인되지 않았다.
- 일부 근거 신뢰도는 상위 Agent가 평가하지 않았다.

### 실행 실패

- 없음

### 종합 해석의 한계

- 목표 문맥 길이, 동시성, 품질 허용치, 지연, 예산 등 주요 목표값 미제공
- 실제 서비스 검증 및 다중 사용자 동시성 처리량 자료 부족
- 물리 PF 어플라이언스의 종단간 검증 및 비용·편익 분석 미완료
- 공동 실증 및 고객 도입 반응 자료 미제공

### 판단 보류

- market/SW-01/market_size_growth: RDKV 고유 시장의 규모·성장률·지역·기간은 두 논문 범위에서 확인하지 못했다.
- market/SW-01/adoption: 실제 유료 고객·상용 배포를 증명하는 자료를 이번 입력에 확보하지 않았다. 미채택이라는 뜻은 아니다.
- market/SW-01/ecosystem: 논문에서 비교에 사용한 오픈소스 기준선을 RDKV의 공식 프레임워크 지원으로 간주할 수 없다.
- market/HW-01/market_size_growth: Photonic-CXL 어플라이언스 고유 시장의 규모·성장률은 두 논문만으로 확인하지 못했다.
- market/HW-01/adoption: 이 어플라이언스의 실제 고객 도입 증거를 확보하지 않았다. 관련 CXL 제품의 도입을 대신 쓰지 않는다.
- stakeholders/SW-01/competitors: 경쟁사의 RDKV 지지·반대 원문을 확보하지 않았다. 비교 벤치마크는 경쟁사의 반응이 아니다.
- stakeholders/SW-01/investors_analysts_media: RDKV에 대한 투자·애널리스트·미디어의 직접 평가를 확보하지 않았다.
- stakeholders/HW-01/competitors: 타 공급자의 Photonic-CXL에 대한 찬반 입장을 확보하지 않았다. 저자의 관련 기술 비교는 직접 반응이 아니다.
- stakeholders/HW-01/investors_analysts_media: Photonic-CXL에 대한 독립 투자·애널리스트·미디어 평가를 확보하지 않았다.
- domain/SW-01/throughput: 목표 QA 서비스의 다중 사용자 동시성·처리량 요구값과 운영 측정 자료를 확보하지 않았다.
- domain/SW-01/deployment: 실제 통합 인건비와 서비스 환경의 운용 검증 자료 부족
- domain/HW-01/deployment: 실배포·장비 가격·운영비·비용 편익 분석 자료 부족

### 차단 사유

- 없음

### 실험 조건 차이

- 구조화된 정량 비교 입력이 없어 자동 대조를 하지 않았다. 실험 조건이 같다는 뜻은 아니다. 기술 조사 결과의 검증 방식·조건을 함께 확인한다.

### 공개 정보 기반 TRL 추정 한계

- TRL은 공개 정보 기반의 팀 추정이며 실제 내부 개발·배포 수준을 확정하지 않는다. 형식·인용 검사는 주장의 진실성을 보증하지 않으며 핵심 결론은 사람이 원문과 대조한다.

### 이해관계자 반응 추정 한계

- inference는 고객·개발자의 실제 발언이 아니다.

### 확증편향 방지 조치

- 동일 Rubric 적용 여부: pass (동일 criterion 집합)
- 반대·제한 근거 포함 여부: warn (입력 내용 보존; 미제공 근거는 생성하지 않음)
- 공급자 주장과 독립 자료 구분 여부: warn (출처 메타데이터 기반; 미입력은 unknown)
- 사실과 추론 구분 여부: enum 검사; 종합 의견의 의미 대조 결과는 SELF VALIDATION 참조
- 미확인 사항 유지 여부: pass (unknown/TBD 유지)

## 8. 도메인 요구조건

- 목표 문맥 길이: TBD
- 예상 동시 사용자 또는 동시 요청 수: TBD
- TTFT 목표: TBD
- TPOT 목표: TBD
- 허용 가능한 품질 손실: TBD
- GPU 메모리 제약: TBD
- 에너지 제약: TBD
- 비용 제약: TBD
- prefix cache 재사용률: TBD
- 배포 대상 GPU: TBD
- 입력 토큰 대비 출력 토큰 비율: TBD

사용자 미제공 수치를 임의로 생성하지 않았다.

## 9. 근거 인덱스

verified는 수집 모듈의 원문·인용 위치 연결 확인이다. 주장의 독립 재현 또는 실측 완료를 뜻하지 않는다.
독립성·검증 방식이 미제공이면 unknown이다. 기존 vendor는 author, third_party는 independent로 표기하며 입력값도 남긴다.

### [SW-impact]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.28; Appendix L: author impact statement
- 검증 방식: statement
- 입력 검증 방식: statement
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: RDKV reduces the memory footprint and decoding latency of long-context LLM inference without modifying model weights or training procedures.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [SW-implementation]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.15; Appendix B: Calibration / Hardware
- 검증 방식: gpu_experiment
- 입력 검증 방식: gpu_experiment
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: All models up to 8B parameters (LLaMA-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3, Qwen3-4B) run on a single NVIDIA A100 64 GB GPU. [...] Calibration is performed once per (ℓ, h) slice and cached to disk.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [SW-kernel]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.6; §3.3 Efficient Packed Decode
- 검증 방식: unknown
- 입력 검증 방식: documentation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: To translate bit-width savings into actual speedup and memory reduction, the cache must stay packed in HBM while dequantization is fused into the attention computation.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [SW-limit]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.28; Appendix K: Limitations
- 검증 방식: unknown
- 입력 검증 방식: documentation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: RDKV compresses the KV cache once after prefill and does not re-evaluate during decoding. [...] The allocation is therefore frozen with respect to attention-pattern shifts that may occur during generation.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [SW-memory]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.9; §4.2 Memory
- 검증 방식: gpu_experiment
- 입력 검증 방식: gpu_experiment
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: RDKV uses 30.5 GB at 128K (1.9× reduction vs. FullKV) and 44.5 GB at 256K, running on the same device where FullKV cannot.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [SW-principle]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.2; §1 Contributions
- 검증 방식: analysis
- 입력 검증 방식: analysis
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: We formulate KV cache compression as a rate–distortion problem. [...] We realize the resulting mixed-bit cache with TriZone, a packed-decode layout that fuses dequantization into the attention kernel, turning the mixed-bit allocation into actual memory savings.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [SW-quality]

- 연결 Reference ID: SW-01
- 문서 ID: SW-01
- 문서명: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- 출처 유형: paper
- 저자 또는 기관: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- 발행일: 2026-05-08
- URL: https://arxiv.org/pdf/2605.08317v1
- 위치: PDF/보존본 p.8; Table 2; §4.1 RULER (1024L budget)
- 검증 방식: gpu_experiment
- 입력 검증 방식: gpu_experiment
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: FullKV 98.58 98.88 96.98 90.33 88.49 79.91 [...] RDKV 98.62 98.61 95.65 88.28 80.07 66.95 [...] Table 2 reports results on LLaMA-3.1-8B-Instruct under Btotal = 1024L.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [HW-architecture]

- 연결 Reference ID: HW-01
- 문서 ID: HW-01
- 문서명: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- 출처 유형: paper
- 저자 또는 기관: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일: 2026-07-29
- URL: https://arxiv.org/pdf/2607.27187v1
- 위치: PDF/보존본 p.5; §III.A System Overview
- 검증 방식: unknown
- 입력 검증 방식: documentation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: The PF Memory Appliance is a memory device built using 16 Photonic Fabric Memory Modules, providing 32 TBs of shared DDR5 memory capacity with a unified address space [...] The PF Memory Appliance connects to host servers through a Photonic Fabric NIC (PF-NIC), a PCIe Gen6/CXL 3.1 adapter card [...] An External Laser Source (ELS) is required to produce optical illumination for the PF Memory Modules and the PF-NIC.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [HW-emulation]

- 연결 Reference ID: HW-01
- 문서 ID: HW-01
- 문서명: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- 출처 유형: paper
- 저자 또는 기관: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일: 2026-07-29
- URL: https://arxiv.org/pdf/2607.27187v1
- 위치: PDF/보존본 p.6; §IV.A Emulation Framework
- 검증 방식: emulation
- 입력 검증 방식: emulation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: The experimental framework is implemented on the Siemens Veloce Strato-M emulation platform [...] To emulate the host environment, we use QEMU to model a CPU running a guest Linux operating system that functions as the PCIe/CXL host.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [HW-host-limit]

- 연결 Reference ID: HW-01
- 문서 ID: HW-01
- 문서명: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- 출처 유형: paper
- 저자 또는 기관: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일: 2026-07-29
- URL: https://arxiv.org/pdf/2607.27187v1
- 위치: PDF/보존본 p.6; §IV.B Bandwidth Characterization
- 검증 방식: emulation
- 입력 검증 방식: emulation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: A single CXL host is limited to 128 GB/s due to the PCIe Gen6 interface constraint and therefore cannot independently saturate a PF Memory Module.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [HW-integration]

- 연결 Reference ID: HW-01
- 문서 ID: HW-01
- 문서명: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- 출처 유형: paper
- 저자 또는 기관: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일: 2026-07-29
- URL: https://arxiv.org/pdf/2607.27187v1
- 위치: PDF/보존본 p.8; §V, Fig.7: proposed integration
- 검증 방식: unknown
- 입력 검증 방식: documentation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: For vLLM, we will implement a CXL KV connector [...] The appliance supports coherence across hosts using a rendezvous-based consistency protocol. [...] Framework-specific connectors (top purple tier) implement thin adapters against each engine's pluggable API.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [HW-pending]

- 연결 Reference ID: HW-01
- 문서 ID: HW-01
- 문서명: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- 출처 유형: paper
- 저자 또는 기관: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일: 2026-07-29
- URL: https://arxiv.org/pdf/2607.27187v1
- 위치: PDF/보존본 p.10; §VIII Limitations and Future Work
- 검증 방식: unknown
- 입력 검증 방식: documentation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: validation on the physical PF Memory Appliance hardware [...] inference workloads remains pending. [...] Cost-benefit analysis comparing PF Memory Appliance against alternative scaling approaches [...] will provide additional deployment guidance.
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

### [HW-serving]

- 연결 Reference ID: HW-01
- 문서 ID: HW-01
- 문서명: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- 출처 유형: paper
- 저자 또는 기관: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- 발행일: 2026-07-29
- URL: https://arxiv.org/pdf/2607.27187v1
- 위치: PDF/보존본 p.9; §VI.A/B, Fig.8: serving simulation
- 검증 방식: simulation
- 입력 검증 방식: simulation
- 독립성: author
- 입력 독립성: author
- 해당 기술과의 관련성: unknown
- 발췌: We evaluate our proposed architecture using LLMServingSim [...] Each conversation consists of 10 turns, with each turn comprising 5,120 input tokens and 500 output tokens. [...] all KV cache entries are retained in the pooled memory, and subsequent turns benefit from full prefix cache hits (82% hit rate).
- 적용 조건: unknown; 평가자의 조건과 원문 실험 조건을 혼동하지 않는다
- 수집 시각: 2026-09-21T10:04:51.666310+00:00
- 검증 상태: verified
- 합성 발췌: false

## 10. REFERENCE CANDIDATES

검증 결과에서 사용된 후보다. 최종 보고서는 본문에서 실제 인용한 Reference만 남긴다.

### [SW-01]

- citation_key: SW01_RDKV
- source_type: paper
- authors_or_organization: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
- title: RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache
- year: 2026
- publication_date: 2026-05-08
- venue_or_site: arXiv
- volume_issue: 없음
- pages: 없음
- doi: 없음
- url: https://arxiv.org/pdf/2605.08317v1
- accessed_at: 2026-09-21
- language: en
- source_sha256: 25836a419005694122c571121030b89bd7ac634f74ac3b5d4c67bf0a19b10e3d
- 원문 라이선스: https://creativecommons.org/licenses/by/4.0/

### [HW-01]

- citation_key: HW01_PHOTONIC_CXL
- source_type: paper
- authors_or_organization: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
- title: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
- year: 2026
- publication_date: 2026-07-29
- venue_or_site: arXiv
- volume_issue: 없음
- pages: 없음
- doi: 없음
- url: https://arxiv.org/pdf/2607.27187v1
- accessed_at: 2026-09-21
- language: en
- source_sha256: d6a67efde2a1ed0e9fb38302708d83e1e43f2c237acd4826ec4daf1bd44e2326
- 원문 라이선스: https://creativecommons.org/licenses/by-sa/4.0/


논문 기반 실험의 한국어 해석·발췌 편집 데이터: CC BY-SA 4.0. 저자의 승인을 뜻하지 않는다.

## 11. 출력 완결성 및 보고서 전달 규칙

- unknown·없음·TBD를 유지하고 빈 템플릿을 후단에 전달하지 않는다.
- Evidence/Reference ID와 citation_key는 중복되지 않으며 인용 연결을 확인한다.
- 정량 주장은 값·단위·기준 시스템·검증 방식·Evidence를 함께 기록한다.
- 레이아웃 제어문을 만들지 않는다. LaTeX 변환·escape·표 배치·참고문헌 렌더링은 후단 책임이다.

## 12. SELF VALIDATION

### validation_summary

- overall_result: warn
- blocking_issue_count: 0
- warning_count: 17
- explanation: partial / allowed_with_gaps

### schema_validation

- result: pass
- explanation: 12개 제목과 필수 필드·enum을 생성 후 검사한다.
- affected_items: 1~12절; 46개 평가 블록

### domain_validation

- result: pass
- explanation: 선택 도메인 id/name과 목표값을 검사. 미입력 목표는 TBD, 입력 0·범위·시나리오는 보존.
- affected_items: cloud-long-context-document-qa

### assessment_coverage_validation

- result: pass
- explanation: 8칸/46항목 출력; 실패 칸은 failed로 표시.
- affected_items: 8/8 입력 칸; 46개 출력 항목

### rubric_validation

- result: warn
- explanation: 공통 판정 enum과 요구값을 검사함. 사유와 판정의 의미 일치는 사람 확인.
- affected_items: market/SW-01/market_size_growth / market/SW-01/adoption / market/SW-01/ecosystem / market/HW-01/market_size_growth / market/HW-01/adoption / stakeholders/SW-01/competitors / stakeholders/SW-01/investors_analysts_media / stakeholders/HW-01/competitors / stakeholders/HW-01/investors_analysts_media / domain/SW-01/throughput / domain/SW-01/deployment / domain/HW-01/deployment

### evidence_integrity_validation

- result: pass
- explanation: 출력 인용은 근거 인덱스와 연결됨. 잘못된 입력은 공백으로 표시.
- affected_items: HW-architecture / HW-emulation / HW-host-limit / HW-integration / HW-pending / HW-serving / SW-impact / SW-implementation / SW-kernel / SW-limit / SW-memory / SW-principle / SW-quality

### fact_inference_validation

- result: warn
- explanation: fact/inference/opinion/unknown 및 기존 mixed를 구분. opinion 발언 주체·인용 검사, 새 종합 의견은 inference. 외부 진실성은 보증하지 않음.
- affected_items: technical/SW-01/validation_scope: inference / technical/SW-01/maturity: inference / technical/HW-01/maturity: inference / market/SW-01/market_size_growth: unknown / market/SW-01/commercialization: inference / market/SW-01/adoption: unknown / market/SW-01/ecosystem: unknown / market/SW-01/cost: inference / market/SW-01/customer_value: inference / market/HW-01/market_size_growth: unknown / market/HW-01/commercialization: inference / market/HW-01/adoption: unknown / market/HW-01/cost: inference / market/HW-01/customer_value: inference / stakeholders/SW-01/competitors: unknown / stakeholders/SW-01/adopters: inference / stakeholders/SW-01/developers: inference / stakeholders/SW-01/investors_analysts_media: unknown / stakeholders/HW-01/competitors: unknown / stakeholders/HW-01/adopters: inference / stakeholders/HW-01/developers: inference / stakeholders/HW-01/investors_analysts_media: unknown / domain/SW-01/capacity: inference / domain/SW-01/latency: inference / domain/SW-01/throughput: unknown / domain/SW-01/gpu_compatibility: inference / domain/SW-01/hardware_dependency: inference / domain/SW-01/deployment: inference / domain/SW-01/maturity: inference / domain/SW-01/customer_value: inference / domain/SW-01/domain_fit: inference / domain/HW-01/capacity: inference / domain/HW-01/quality: inference / domain/HW-01/latency: inference / domain/HW-01/throughput: inference / domain/HW-01/gpu_compatibility: inference / domain/HW-01/deployment: inference / domain/HW-01/maturity: inference / domain/HW-01/customer_value: inference / domain/HW-01/domain_fit: inference

### comparability_validation

- result: warn
- explanation: 구조화 수치 조건 비교. 생성된 종합 문장의 지표 확대 해석은 자동 의미 검사.
- affected_items: 해당 미확인 항목 없음

### neutrality_validation

- result: warn
- explanation: 순위/추천 금지. 종합 문장의 확정·조건 표현은 자동 의미 검사.
- affected_items: opinion_1 / opinion_2 / opinion_3 / opinion_4 / opinion_5 / opinion_6 / opinion_7

### reference_validation

- result: pass
- explanation: 출력 Evidence의 Reference 연결 검사 완료.
- affected_items: SW-01 / HW-01

### status_consistency_validation

- result: pass
- explanation: 동일 report_decision 함수로 상태·생성 조건 판정.
- affected_items: review_status, report_generation, next, unknown_count, failed_count

### summary_aggregation_validation

- result: pass
- explanation: 네 관점의 counter_evidence/gaps와 검증된 종합 의견을 요약에 함께 반영. 미입력 위험은 미평가로 표시.
- affected_items: 2·3절 요약 재료, 6절 의견의 위험·제약

### synthesis_coverage_validation

- result: pass
- explanation: 일치·상충·조건 비교·병행의 기술별 의견 또는 보류 사유를 검사. 근거 부족과 모델 누락을 구분.
- affected_items: 새로운 종합 의견 / 일치하는 평가 / 상충하는 평가 / 조건에 따른 가치 차이 / 병행 가능성

### semantic_grounding_validation

- result: pass
- explanation: 모든 종합 의견을 연결 평가·근거와 의미 대조. 반려 시 한 번 수정 후 재검사, 미통과 시 후단 차단.
- affected_items: passed

### domain_requirements_validation

- result: warn
- explanation: 11개 목표 필드의 입력 보존 검사. unknown/TBD를 실험 수치로 대체하지 않음.
- affected_items: context_tokens / concurrency / ttft / tpot / quality / gpu_memory / energy / cost / prefix_cache_hit_rate / gpu_model / input_output_token_ratio

### quantitative_context_validation

- result: pass
- explanation: 구조화된 값·단위·조건·Evidence 검사. 조건 미확인은 보존하고 비교 제외. 자유 문장 수치는 완전 추출을 보증하지 않으며 아래 대상은 추가 구조화 필요.
- affected_items: 해당 미확인 항목 없음

### independence_validation

- result: pass
- explanation: author/independent/unknown 구분. verified를 독립 재현으로 해석하지 않음.
- affected_items: 해당 미확인 항목 없음

### verification_method_validation

- result: warn
- explanation: GPU 실험·HW 실측·에뮬레이션·시뮬레이션·분석·발언 구분. 옛 표기/미입력의 새 분류를 추측하지 않음.
- affected_items: HW-architecture / HW-integration / HW-pending / SW-kernel / SW-limit

### technology_relevance_validation

- result: warn
- explanation: 인접 시장·비교 기술을 선택 기술의 직접 채택·지원·당사자 반응으로 승격하지 않음. 직접/간접 미입력은 unknown.
- affected_items: technical/SW-01/mechanism / technical/SW-01/validation_scope / technical/SW-01/maturity / technical/HW-01/mechanism / technical/HW-01/validation_scope / technical/HW-01/maturity / market/SW-01/market_size_growth / market/SW-01/commercialization / market/SW-01/adoption / market/SW-01/ecosystem / market/SW-01/cost / market/SW-01/customer_value / market/HW-01/market_size_growth / market/HW-01/commercialization / market/HW-01/adoption / market/HW-01/ecosystem / market/HW-01/cost / market/HW-01/customer_value / stakeholders/SW-01/competitors / stakeholders/SW-01/adopters / stakeholders/SW-01/developers / stakeholders/SW-01/investors_analysts_media / stakeholders/HW-01/competitors / stakeholders/HW-01/adopters / stakeholders/HW-01/developers / stakeholders/HW-01/investors_analysts_media / domain/SW-01/capacity / domain/SW-01/quality / domain/SW-01/latency / domain/SW-01/throughput / domain/SW-01/gpu_compatibility / domain/SW-01/hardware_dependency / domain/SW-01/deployment / domain/SW-01/maturity / domain/SW-01/customer_value / domain/SW-01/domain_fit / domain/HW-01/capacity / domain/HW-01/quality / domain/HW-01/latency / domain/HW-01/throughput / domain/HW-01/gpu_compatibility / domain/HW-01/hardware_dependency / domain/HW-01/deployment / domain/HW-01/maturity / domain/HW-01/customer_value / domain/HW-01/domain_fit

### input_provenance_validation

- result: warn
- explanation: demo는 입력 선언과 모의 근거/역할 플래그를 확인. 생성 모델의 실제 호출만으로 demo:false가 되지 않음. 미표시 모의 데이터까지 자동 판별할 수는 없음.
- affected_items: demo=true; config.demo 및 상위 역할.demo, evidence.synthetic

### 사람 검수의 범위

실행 중 승인·수정 대기는 없다. 종합 내용은 자동 의미 검사와 최대 1회 수정으로 처리한다.
최종 제출자는 원문 맥락·상위 입력의 실제 실행 여부·선택 도메인의 요구값을 확인한다. 이는 자동 검사의 무오류를 보증할 수 없기 때문이며 unknown을 임의로 채우라는 뜻이 아니다.

### output_completeness_validation

- result: pass
- unresolved_placeholder_count: 0
- duplicate_id_count: 0
- invalid_citation_key_count: 0
- explanation: 아래 수치는 출력 완결성 검사 통과 시에만 저장된다.
- affected_items: 없음
