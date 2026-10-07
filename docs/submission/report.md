# KV Cache 다관점 평가 보고서 - 판교 7반 2조

## SUMMARY

KV Cache 최적화 기술 다관점 평가

판교 7반 2조 | 평가 기준일 2026-10-07 | 장문맥 문서 QA 클라우드 서빙

RDKV는 제거와 저비트 양자화를 공동 최적화해 KV 데이터량을 줄인다. Photonic-CXL은 KV 저장 위치를 광 연결 기반 외부 공유 메모리로 확장한다. 두 접근은 메모리 병목을 다른 경로로 완화하며, 압축 품질·커널 통합과 데이터 이동·장비 연동이라는 서로 다른 검증 과제를 남긴다. [1,2]

기존 Review의 공개 정보 기반 팀 추정은 RDKV TRL 6, Photonic-CXL TRL 4다. RDKV의 근거는 연구용 GPU 장문맥 시스템 평가이고, Photonic-CXL은 에뮬레이션 범위의 구성 검증까지 반영했다. 실제 클라우드 운영·물리 PFMA 통합 검증을 뜻하지 않으며 공식 인증도 아니다. [3]

선정 기술 자체의 매출·고객 배포·총소유비용은 확보 자료만으로 확정되지 않는다. 시장 12항목을 모두 다루되 사실·팀 추론·확인 공백을 구분한다. 서로 다른 실험의 성능 배수를 직접 비교해 순위를 정하지 않는다. [1,2,3]

### 1. 분석 목적과 범위

질문: 두 접근은 장문맥 문서 QA 운영 조직의 용량, 품질, 지연, 운영 부담에 어떤 조건부 의미를 가지는가? 기술 성숙도·시장·이해관계자·도메인 네 관점을 같은 질문으로 비교한다. 입력에 목표 동시성, 지연 SLO, 품질 허용 손실, 비용 상한은 주어지지 않았다.

| 구분 | 이번 보고서의 평가 경계 |
| --- | --- |
| 기술 대상 | RDKV 논문 알고리즘·TriZone 구현 / Photonic-CXL 논문의 PF Memory Appliance 설계 |
| 자료 범위 | 저장된 기술 분석·근거 레지스트리와 후속 검색 기록. RDKV 28쪽 + Photonic-CXL 12쪽 = 40쪽 |
| 증거 구분 | 논문 저자 보고 / 업체·인접 기술 자료 / 공개 자료에 근거한 팀 추론 / 미확인 |
| 작성 방식 | 기존 기록을 Codex가 대조·편집한 정리본. pipeline 자동 생성 또는 새 AI Judge 통과 결과가 아님 |

자료 무결성 검증과 원 논문 실험 재현은 구별한다. 이번 정리에서는 신규 원본 PDF 재검증·retrieval·embedding·실험 재현을 수행하지 않았다. 실행과 품질 한계는 8쪽에 별도로 기록한다. [3,4]


---

## 2. 기술 선정과 작동 원리

사람이 SW와 HW에서 각각 한 기술을 선정했다. 논리적 데이터량 감소와 물리적 저장 공간 확장을 비교하면 필요한 구현 변경과 병목 이동을 같은 KV 문제에 연결할 수 있다. 두 기술의 결합 효과는 별도 실험 없이 확정하지 않는다.

| 공통 질문 | RDKV / SW | Photonic-CXL / HW |
| --- | --- | --- |
| 무엇을 바꾸나 | Value 토큰과 Key 채널에 0·2·4·8·16비트 할당. 0비트는 제거로 처리. [1, p.2·5·17] | KV를 외부 공유 메모리에 저장. 32TB·최대 16호스트 광-CXL 설계 제안. [2, p.1·4·5] |
| 핵심 구현 | Rate-distortion·비트 예산과 TriZone 패킹·역양자화 attention 커널. prefill 직후 한 번 압축하고 decoding 중 재평가하지 않음. [1, p.2·17·28] | PF-NIC·광섬유 셔플·메모리 장치와 allocator/KV indexing 등 연동 계층. [2, p.4·5·8] |
| 품질·비용 조건 | 정보 손실이 가능해 과제별 정확도·보존 문맥과 커널 비용을 확인해야 한다. [1, p.7·21·23] | 완전한 KV 저장은 압축 손실을 추가하지 않는 방향이다. 답변 정확성·안전성 보장은 별도 검증 대상이다. [2, p.1·10] |
| 새로운 병목 | 비트 배정·패킹 준비 비용과 혼합 정밀도 커널 호환성. [1, p.17·21·23] | 외부 메모리 접근 지연·대역폭·동시 접근·장애 복구 및 장비 연동. [2, p.8·10] |

### 실험 결과를 읽는 방법

RDKV의 시스템 성능 근거는 LLaMA-3.1-8B-Instruct·단일 A100 64GB 조건이다. 추가 기능 평가에는 다른 모델도 포함된다. LongBench의 FullKV 정확도 대비 97.81% 회복은 상대 값이며 전체 과제의 절대 정확도가 아니다. [1, p.1·7·9·16]

Photonic-CXL은 기존 메모리 계층의 KV 검색 실측, Veloce 하드웨어 에뮬레이션, LLMServingSim 서빙 시뮬레이션을 구분한다. 논문은 물리 PFMA의 end-to-end 검증을 향후 과제로 명시한다. [2, p.2·7·9·10]

RDKV의 4.5배는 128K에서 FullKV FlashAttention-2 대비 decode 속도이고, PFMA의 6.6배는 300개 다회차 대화에서 용량이 다른 baseline과 비교한 시뮬레이션 TTFT다. 지표·baseline·검증 방식이 달라 배수로 직접 순위화할 수 없다. [1, p.8·9; 2, p.9]


---

## 3. 기술 성숙도: TRL 단계별 평가

기존 실행의 Review 최종 결과를 사용했다. 모델의 초안은 단계별 조건·이유·근거 ID를 갖고, Review가 기술 귀속과 원문의 의미를 검사한다. 1단계부터 연속으로 충족한 최고 단계만 기록한다. 근거 공백을 실패 또는 공식 인증으로 바꾸지 않는다. [3]

| 단계·요구 조건 | RDKV 최종 팀 판정 | Photonic-CXL 최종 팀 판정 |
| --- | --- | --- |
| 1 기본 원리 | 충족: rate-distortion 모델. [1, p.1·5] | 충족: KV 메모리 문제와 광-CXL 원리. [2, p.1·4] |
| 2 개념·적용 방식 | 충족: 제거·양자화 공동 비트 할당. [1, p.2] | 충족: 공유 메모리 구조와 적용 목적. [2, p.1·5] |
| 3 개념 검증 | 충족: 장문맥 벤치마크·추가 모델 평가. [1, p.7·16] | 충족: 계층 실측·에뮬레이션. [2, p.2·3·7] |
| 4 실험실 통합 | 충족: GPU 커널과 시스템 통합 평가. [1, p.9] | 충족: 에뮬레이션 범위의 구성 평가. [2, p.5·7] |
| 5 관련 환경 검증 | 충족: 대표 장문맥 과제·시스템 조건. [1, p.8·9] | 미확인: 물리 PFMA end-to-end 검증 공백. [2, p.10] |
| 6 대표 규모 시제품 | 충족: 단일 A100의 128K-256K 시스템 시험. [1, p.9·23] | 미확인: 물리 통합 시제품 시험 근거 부족. [2, p.10] |
| 7 실제 운용 시연 | 미확인: 확보 자료의 현장 파일럿 공백. | 미확인: 실제 장비 운용 시연 공백. [2, p.10] |
| 8 완성·적합성 검증 | 미확인: 최종 안정성·운영 문서 공백. | 미확인: 완성 구성·운영 검증 공백. |
| 9 지속 성공 운용 | 미확인: 지속적인 운용·유지보수 기록 공백. | 미확인: 지속적인 운용·유지보수 기록 공백. |
| 연속 충족 최고 단계 | 공개 정보 기반 팀 추정 TRL 6 | 공개 정보 기반 팀 추정 TRL 4 |

판정 범위: RDKV의 대표 규모는 논문에 보고된 연구용 단일 GPU 시스템이다. 다중 호스트 운영 규모까지 검증됐다는 뜻이 아니다. PFMA의 4단계는 물리 장비 완성 판정이 아닌 에뮬레이션 기반 추정이다. 입력에 표준 버전이 unknown으로 남아 있어 공식 표준 적격 판정을 주장하지 않는다. [3]


---

## 4. 시장성: 두 기술의 12개 항목

6개 기준을 두 기술에 공통 적용해 12개 평가 셀을 구성한다. 확인한 자료가 부족해도 알려진 사실·조건·공백·다음 확인을 전달한다. 항목을 모두 작성한 상태와 사실이 모두 입증된 상태는 다르다.

| 시장 기준 | RDKV / SW | Photonic-CXL / HW |
| --- | --- | --- |
| 시장 규모·성장 | 선정 기술의 직접 규모는 미확인. 논문은 장문맥 KV 압축 필요성을 설명한다. 관련 분야의 관심을 RDKV 매출·점유율로 대입하지 않는다. [1, p.1] | 선정 PFMA의 직접 규모는 미확인. CXL 컴포넌트·메모리 풀링 시장은 인접 시장이다. 그 전망을 PFMA 매출로 바꾸지 않는다. [5,6] |
| 제품화·상용화 | 연구 알고리즘·커널 구현과 실험이 확인된다. 유료 제품 버전·라이선스·지원 정책은 확보 자료에서 미확인이다. [1, p.9·17] | 설계와 에뮬레이션·시뮬레이션이 확인된다. 물리 장비 end-to-end 검증은 향후 과제다. 일반 CXL 출하를 PFMA 출시로 귀속하지 않는다. [2, p.10] |
| 실제 채택 | 선정 RDKV의 고객 배포·운영 자료가 포함되지 않았다. 배포가 전혀 없다고 단정하지 않는다. [1; 3] | 선정 PFMA의 운영 고객 배포 자료가 포함되지 않았다. 시뮬레이션 대화 수는 실제 고객 접속 수가 아니다. [2, p.9·10] |
| 생태계 지원 | TriZone 구현 근거가 있다. 범용 추론 엔진의 공식 버전 지원·장비 호환표는 추가 확인 대상이다. [1, p.17] | vLLM 등 연동 구조가 제안된다. Figure 7의 사용자 정의 계층은 개념 단계이며 완성된 connector 목록이 아니다. [2, p.8] |
| 표준화 | RDKV를 명시한 규격 채택·인증 근거는 미확인. 공개 알고리즘과 산업 표준 채택은 구별한다. [1, p.2] | CXL 의미를 유지하려는 설계. 선정 구현의 상호운용성 통과·인증은 미확인이다. CXL 규격 존재와 PFMA 인증을 구별한다. [2, p.4·8] |
| 비용·고객 가치 | 팀 추론: 메모리·decode 개선은 비용에 영향을 줄 수 있다. 커널 통합·압축 준비·품질 손실을 포함한 TCO 검증이 필요하다. [1, p.9·21·23] | 팀 추론: 공유 KV 재사용은 용량 부족·재계산을 완화할 수 있다. 장비 가격·전력·연동 비용을 포함한 TCO는 미확인이며 향후 과제다. [2, p.9·10] |

다음 조사: 제품 버전·지원 장비·고객 배포 범위·운영 기록·동일 부하 TCO를 직접 확보한다. 정량 시장 전망은 시장 정의·기간·지역이 혼재된 이전 초안의 오류를 피하기 위해 이 정리본에서 사용하지 않았다. [4]


---

## 5. 도메인 적용성: 장문맥 클라우드 QA

도메인은 장문맥 문서 QA를 제공하는 클라우드 데이터센터다. 평가 질문은 용량·품질·지연·처리량·호환성·전용 장비·배포 복잡도·성숙도·고객 가치·적합성 10개 기준이며 두 기술에 동일하게 적용한다. 요구조건이 비어 있어 도입 적합성의 최종 pass/fail을 확정하지 않는다. [3]

| 운영 질문 | 조건별 비교와 검증 과제 |
| --- | --- |
| 용량·처리량 | RDKV: 압축률과 유지할 품질의 관계를 측정한다. PFMA: KV 재사용·공유 용량·동시 접근의 관계를 측정한다. 각각 논문 조건과 실제 목표 부하의 차이를 남긴다. [1, p.8·9; 2, p.9] |
| 품질·문맥 보존 | RDKV는 업무별 정보 삭제·양자화 영향이 필요하다. 완전 KV를 저장하는 PFMA도 생성 답변 품질·안전성을 보장하지는 않는다. 법률·의료 적용 예를 분야별 실증으로 해석하지 않는다. [1, p.7; 2, p.1·10] |
| 지연 예측 가능성 | Decode, TTFT, 전체 응답시간과 p95/p99를 구별한다. RDKV의 압축 준비 비용, PFMA의 외부 경로와 동시성 비용을 포함해 측정해야 한다. [1, p.21·23; 2, p.8·10] |
| 호환성·장비 의존 | RDKV는 기존 GPU를 쓰더라도 전용 패킹·attention 커널 연동이 필요하다. PFMA는 광 연결·PF-NIC·메모리 장비와 소프트웨어 연동이 필요하다. [1, p.17; 2, p.5·8] |
| 배포·성숙도 | 연구 벤치마크와 실제 클라우드 운영은 다르다. 모델·드라이버·엔진 버전, 장애·재시작·관측·지원 정책을 확인한다. 팀 추정 TRL만으로 배포 준비를 확정하지 않는다. [1,2,3] |
| 고객 가치·적합성 | 팀 추론: 처리 가능한 문맥·응답 대기·요청당 비용이 고객 가치와 연결될 수 있다. 측정된 목표 SLO·비용·품질 하한이 없으므로 경제성 또는 절대 승자를 제시하지 않는다. |

### 비교 실험을 설계한다면

같은 모델·문서 QA 세트·입력/출력 토큰·동시 요청·KV 재사용률을 고정한다. FullKV를 기준으로 정확도, TTFT, decode latency, peak GPU memory, 처리량, 전력·장비 및 소프트웨어 비용을 기록한다. PFMA 물리 장비를 확보하지 못하면 시뮬레이션 결과와 GPU 실측을 별도 표로 보고한다. 이는 후속 검증 제안이며 이번에 수행한 실험이 아니다.


---

## 6. 이해관계자 평가와 관점 간 상충

아래 영향은 논문에 나타난 구현 부담과 공개 자료를 연결한 팀 추론이다. 특정 집단이 실제로 우호적·반대한다는 조사 결과로 제시하지 않는다. 실제 의견에는 발언 주체·날짜·대상 기술·직접 인용의 확인이 필요하다.

| 이해관계자 | RDKV의 기대·부담 | Photonic-CXL의 기대·부담 |
| --- | --- | --- |
| 서비스 운영자 | 메모리·decode 개선 가능성. 품질 손실, 압축 준비 비용, 커널 유지·모델별 재검증 부담. [1, p.9·21·23] | 공유 KV 보존·재계산 감소 가능성. 장비 지연·장애·구축비·물리 시스템 검증 부담. [2, p.9·10] |
| 추론 엔진 개발자 | 혼합 비트 저장·패킹·역양자화 attention 연동. 프레임워크 버전별 호환성과 fallback 확인. [1, p.17] | allocator·KV indexing·일관성·connector 설계. 개념 계층과 완료된 제품 지원을 구별. [2, p.8] |
| 메모리·장비 공급사 | 팀 추론: 기존 GPU 활용을 위한 소프트웨어 기능으로 평가 가능. 실제 제휴·투자·반응 자료는 미확인. | 업체는 광 메모리 계층의 가치를 설명한다. 업체 설명은 독립 재현·선정 PFMA 고객 채택 증거가 아니다. [7] |
| 개발자·최종 사용자 | 팀 추론: 문맥 처리와 비용 개선 가능성. 업무 정확도·운영 SLO 충족을 별도로 확인해야 한다. | 팀 추론: 재사용 KV의 응답 지연 개선 가능성. 답변 안전성·서비스 안정성은 별도 실증 대상이다. |
| 투자·분석 관점 | 선정 RDKV의 투자 규모·제품 매출·공식 고객 발표를 확보 자료에서 확인하지 못했다. | 인접 CXL 전망과 선정 PFMA의 투자·매출을 구별한다. 가격·비용 편익은 추가 검증 과제다. [5,6; 2, p.10] |

### 시사점: 함께 일치하는 점과 달라지는 조건

두 기술은 KV 메모리와 데이터 이동 문제를 다룬다. 압축은 저장량과 품질·커널 준비 비용을, 확장은 저장 공간과 전송·장비 비용을 함께 변화시킨다. 서비스 운영자의 용량 요구와 개발자의 연동 부담이 상충할 수 있다. 공개된 대표 환경의 성능과 실제 운영 성숙도도 구별해야 한다. [1,2]

병행 가능성은 설계 가설이다. 압축한 KV를 외부 메모리에 저장할 경우 정확도·전송량·역양자화·캐시 일관성·재사용률이 함께 변하므로 효과를 독립적으로 검증해야 한다. 결합 결과를 두 논문의 개별 배수로 계산하지 않는다.


---

## 7. 에이전트 구조와 State 설계

OW를 선택한 이유는 세 관점이 같은 기술 자료를 독립적으로 평가할 수 있고, 빠진 항목만 계획·재조사하기 때문이다. 고정된 역할 catalog와 실행되는 task 수는 다르다. State에 구조화된 계획을 저장한 뒤 Send를 만든다. [8]

RAG 확보 → Planner → State의 task → 동적 Send → terminal 취합 → TRL/Review → Report/PDF → Quality → 저장 판정 분기

| State 항목 | 코드 적용과 이유 |
| --- | --- |
| 제어 / payload | phase·task·pending cell·반복 수는 State, 큰 원문·PDF는 외부 artifact와 hash 참조. |
| 관측성 | 결정·상태와 상세 로그를 분리. events.jsonl·usage.json·LangSmith metadata로 추적. |
| 지속성 비용 | 큰 자료 중복 대신 상대 경로·SHA-256 참조와 SQLite checkpoint. 자동 pruning은 미구현. |
| 상관 ID | run_id를 thread_id·task_id·call_id와 연결. LangSmith evaluation_run_id로 상관. |
| 재개 / 복구 | attempt·오류·retryable·fingerprint를 보존. 유효한 완료 결과만 재사용하고 실패 사용량도 유지. |
| 동시 처리 | outcome reducer로 중복 처리·충돌 거부. aggregator 한 곳이 채택 결과를 병합. |
| 종료 보장 | worker retry·재계획·Quality·호출·토큰·시간·recursion 상한과 termination_reason 기록. |

기본 재계획 2회, 완료된 내용 Quality 평가 3회와 공통 예산을 적용한다. 기술 호출 실패는 성공으로 처리하지 않는다. 가능한 보완 경로와 실제 실행된 경로를 구별한다. [8]


---

## 8. 품질 평가·검증 결과·남은 한계

3안 Hybrid를 적용했다. 객관 조건은 코드 검사, 의미는 별도 AI Judge로 검사한다. 근거성 40%, 중립성·편향 통제·관점 커버리지 각 20%이며 축별 4/5, 총점 80 이상과 모든 필수 gate 통과를 함께 요구한다. 점수만으로 최종 채택하지 않는다. [8]

| 검증 | 실제 기록과 해석 |
| --- | --- |
| 코드 검증 | 선택 회귀 470개 통과 / 0 실패 / 14.14초. pipeline·domain·market·선택 Review·report 범위이며 전체 suite 또는 실제 API 성공을 뜻하지 않는다. [4] |
| 기존 Report 7 | 실제 PDF 6쪽, TRL 6·4. Quality 84점, 네 축 4/5/4/4. H1·H2·H7과 미해결 major gate가 실패했다. 점수는 해당 기존 PDF에만 적용된다. [4] |
| 검사 분모 | 기존 Quality에서 6/6 블록, 216/216 분석 단위, 169/169 주장, 시장12/12 셀을 검사. 검사 완료와 의미적 통과는 다른 판정이다. [4] |
| 수정 이후 Report 8 | 모델 접근 오류로 새 TeX·PDF·Quality 결과 미생성. 마지막 완료 Quality의 실패 상태와 후속 실행 오류를 따로 기록한다. [4] |
| 이번 정리본 | 원문 귀속과 실험 조건을 보존하도록 재편집한 PDF. 컴파일·쪽수·시각 확인은 별도 검사하며, 새 AI Judge 점수·통과를 주장하지 않는다. |
| 실제 동적 제어 trace | LangSmith에 33개 run 저장 확인. 최초 Worker 3개, HW 시장 표준화 1셀 재조사 Worker 1개, Report·Quality 각 3회. 모델·보고서·Quality 경계는 합성 fixture이며 LLM·검색 호출 0회다. 실제 제어 경로 검증으로만 해석한다. [11] |

### 한계와 다음 확인

기술 연구의 독립 재현·운영 검증, 선정 기술의 제품·고객·TCO, 새로운 HitRate@K/MRR, Judge 보정은 미검증이다. 기존 시장 전망의 기간·시장 정의 혼재와 인접 제품의 기술 귀속 문제를 이 정리본에서 제거했다. [4]

이번 PNG는 같은 offline 제어 테스트의 앞·뒤 캡처다. 이 PDF와 동일한 live 생성 실행의 증빙은 아니다. 제출 내용 검증을 완료하려면 사용 가능한 모델로 새 자동 보고서·독립 Quality·같은 실행 trace를 확보해야 한다. 합성 passed와 기존 84점을 이 PDF에 적용하지 않는다.

참조 실행: integration-fcb4b36916fd49e6. 코드는 feat/skala-multi-agent-orchestration의 검증된 역할 커밋과 연결한다. 실행 기록은 여러 개발·재개·오류를 포함하므로 단일 실행 속도·비용으로 해석하지 않는다.


---

## REFERENCE

[1] Junkai Zhang, Hang Guo, Luca Benini, Yawei Li (2026). RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache. arXiv:2605.08317. https://arxiv.org/abs/2605.08317

[2] Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep (2026). A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference. arXiv:2607.27187. https://arxiv.org/abs/2607.27187

[3] KV-Cache-Multi-Perspective-Evaluator (2026-10-07). 저장 기술 연구·Review 최종 결과: technical-bge-e2e-two-papers / research.context_manifest.json / review.output.json / trl.output.json. 후속 run: integration-fcb4b36916fd49e6.

[4] KV-Cache-Multi-Perspective-Evaluator (2026-10-07). 실행 및 역할 재구성 검증: docs/validation-20261007-quality-fix.md·json, docs/role-implementation-history.json, 기존 outputs/ow-validation-20261007/quality/attempt-7/quality.json과 report.output.json. Git 이력: 아래 링크.

[5] Strategic Market Research (저장 서지일 2025-10-06). Compute Express Link (CXL) Component Market. https://www.strategicmarketresearch.com/market-report/compute-express-link-component-market

[6] Fortune Business Insights (저장 서지일 2026-09-14). CXL Memory Pooling Appliance Market Size, Share [2026-2034]. https://www.fortunebusinessinsights.com/cxl-memory-pooling-appliance-market-117960

[7] Marvell Technology (발행일 미확인). Photonic Fabric Technology: How Optical Connectivity Enables the Next Generation of AI Infrastructure. https://www.marvell.com/blogs/photonic-fabric-technology-optical-connectivity-ai-infrastructure.html

[8] KV-Cache-Multi-Perspective-Evaluator (2026-10-07). pipeline/contracts.py·planner.py·graph.py·report_quality.py·trl.py 및 docs/model-architecture.md·orchestration.md. 기준 코드 이력: dbfc331, 수업 브랜치 아래 링크.

[9] 배기주 / SK AX·SKALA (페이지 표시 갱신일 2026-10-07). Multi-Agent Orchestration 실습 가이드. Safari에서 필수 항목·State·품질 평가·제출 3종 본문 확인. https://actually-war-1ea.notion.site/Multi-Agent-Orchestration-3d57f4c866938020a992fcc97e942ee6

[10] 배기주 / SK AX·SKALA. KV cache 최적화 기술 평가 가이드. 기존 가이드 검토 기록 및 Safari의 제출 기준으로 목차·분량 확인. https://actually-war-1ea.notion.site/KV-cache-3ba7f4c866938099b7a8fdaa1831c07e

[11] KV-Cache-Multi-Perspective-Evaluator (2026-10-07). 실제 그래프 제어 테스트 tools/trace_orchestration_smoke.py. LangSmith trace 47df0864-e944-4660-834c-d64a9c8f6392. 모델·보고서·Quality 합성 경계. 상세 URL·원격 저장 검증은 제출 trace.receipt.json 참조.

Git 브랜치: https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/tree/feat/skala-multi-agent-orchestration

페이지 표기는 저장 원본 PDF의 물리 페이지다. 서지일 미확인은 임의 날짜로 채우지 않았다. 인접 시장 자료는 시장 경계 설명에만 사용했고 수치 전망·선정 기술 매출로 전환하지 않았다. [9,10]은 보고서 형식·설계·제출 조건의 기준 자료다.
