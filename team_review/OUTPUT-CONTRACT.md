# 평가 종합 Agent → 보고서 생성기 입력 계약

평가 종합 Agent의 최종 출력은 다음 파일이다.

```text
outputs/review.output.md
```

이 파일은 최종 보고서가 아니라 **보고서 생성기가 신뢰할 수 있는 평가·근거·종합 결과를 전달받는 공식 입력 문서**다.

평가 종합 Agent는 새로운 기술 조사를 수행하기보다 앞 단계의 결과를 다음 기준으로 검증하고 종합해야 한다.

- 두 기술 × 네 관점 결과가 모두 있는지 확인한다.
- 각 주장에 실제 Evidence ID가 있는지 확인한다.
- 사실과 추론이 구분됐는지 확인한다.
- 실측·GPU 실험·에뮬레이션·시뮬레이션이 구분됐는지 확인한다.
- 서로 직접 비교할 수 없는 수치를 비교하지 않았는지 확인한다.
- 자료가 없을 때 `unknown`으로 남겼는지 확인한다.
- 관점 간 일치·상충·조건 차이가 정리됐는지 확인한다.
- 최종 보고서를 생성할 수 있는 상태인지 판정한다.

## 출력 상태 규칙

자동 의미 검사 확장: 생성 의견을 연결된 평가·근거에 대조하고, 반려 시 한 번 수정한 뒤 재검사한다.
`semantic_validation_status`는 `passed / rejected / failed / not_run`이다. `passed`가 아니면
`report_generation=blocked`로 진단만 전달한다. `unknown` 입력은 충실히 보존했다면 `allowed_with_gaps`가 가능하다.
`human_review_required=true`는 기존 계약 호환 필드이며 `human_review_scope=final_submission_only`다.
종합 파이프라인에는 사람의 수정·승인 대기 단계가 없다. 이 상태는 외부 사실의 진실성 보증이나 모델 무오류 인증은 아니다.

```text
complete:
필수 평가와 근거가 모두 존재하고 중대한 공백이 없음

partial:
필수 구조는 존재하지만 일부 근거 부족, unknown 또는 Agent 실패가 있음

failed:
입력·인증·파일·구조 오류 등으로 유효한 종합 결과를 만들 수 없음
```

```text
allowed:
정상 보고서 생성 가능

allowed_with_gaps:
미확인·실패·한계를 명시하는 조건으로 보고서 생성 가능

blocked:
최종 보고서 생성 금지, 오류 진단만 출력
```

---

# `review.output.md` 출력 형식

```markdown
---
schema_version: report-input-v1
rubric_version: kv-cache-rubric-v1
reference_schema_version: reference-v1
content_language: ko
run_id: <실제 실행 ID>
generated_at: <ISO 8601 형식의 생성 시각>
evaluation_as_of: <YYYY-MM-DD 형식의 평가 기준일>
review_status: <complete | partial | failed>
report_generation: <allowed | allowed_with_gaps | blocked>
human_review_required: true
human_review_scope: final_submission_only
semantic_validation_status: <passed | rejected | failed | not_run>

sw_technology_id: SW-01
hw_technology_id: HW-01

valid_perspective_cells: <0/8 ~ 8/8>
valid_criterion_blocks: <0/46 ~ 46/46>
unknown_count: <정수>
failed_count: <정수>
evidence_count: <정수>
reference_candidate_count: <정수>
---

# 상태 집계 규칙

- `perspective cell`은 기술 2개 × 관점 4개의 조합을 의미하며 총 8개다.
- `criterion block`은 각 관점의 필수 criterion × 기술 2개의 조합을 의미하며 총 46개다.
- 한 perspective cell의 필수 criterion 블록이 모두 존재하면 구조적으로 유효한 cell로 계산한다.
- `unknown_count`는 판정이 `unknown`인 criterion 블록 수다.
- `failed_count`는 판정이 `failed`인 criterion 블록 수다.
- `unknown` 블록은 구조적으로 존재하므로 perspective cell의 존재 여부 계산에는 포함하지만, `review_status: complete`로 판정할 수는 없다.
- `failed` 블록은 `valid_criterion_blocks`에 포함하지 않는다.

# 보고서 생성 Agent 입력

## 1. 보고서 컨텍스트

### 사용자 원문 도메인 입력

<사용자가 최초 입력한 자연어를 수정하지 않고 기록>

### 정규화된 도메인

- 도메인 ID: <정규화된 ID>
- 도메인명: <도메인명>
- 대상 사용자: <사용자 또는 운영 주체>
- 배포 환경: <데이터센터·클라우드 등>
- 워크로드: <문서 QA, multi-turn 대화 등>
- 중요 지표: <용량, TTFT, TPOT, 처리량, 품질, 비용 등>
- 적용 범위: <이번 평가에 포함하는 범위>
- 제외 범위: <온디바이스 등 제외 범위>
- 가정: <명시적으로 사용한 가정>
- 미확인 사항: <사용자 입력에서 확인되지 않은 값>

### 문제 정의

<선택된 도메인에서 발생하는 KV cache 병목과 평가 필요성>

### 평가 목적

특정 기술의 우열을 판정하지 않고 기술 성숙도, 시장성,
이해관계자 및 도메인 적용성 관점에 따라 평가가 달라지는
지점을 분석한다.

### 평가 대상

- SW: RDKV
- HW: Photonic-CXL

### 공통 평가 관점

- 기술 성숙도
- 시장성
- 이해관계자
- 도메인 적용성

### 공통 작성 원칙

- 저자 보고와 독립 검증을 구분한다.
- 사실과 평가자의 추론을 구분한다.
- 실측·GPU 실험·에뮬레이션·시뮬레이션을 구분한다.
- 서로 다른 지표와 실험의 배수 성능을 직접 비교하지 않는다.
- 근거가 없으면 추측하지 않고 `unknown`으로 남긴다.
- 특정 기술의 절대적 승자나 총점 순위를 만들지 않는다.
- 근거가 있는 경우 선택 도메인과 조건에 따른 상대적 적합성은 설명할 수 있다.
- 시장성·이해관계자·도메인 적용성 평가는 정규화된 단일 도메인을 기준으로 수행한다.
- 전역 자료를 사용하면 선택 도메인에 직접 적용 가능한지 별도로 표시한다.

## 2. 기술 선정 정보

### RDKV (SW-01)

- 기술 유형: SW
- 핵심 접근: KV cache eviction과 혼합 정밀도 양자화의 공동 최적화
- 선정 방식: Human-based
- 선정 이유: <내용>
- 핵심 메커니즘: <내용>
- 주요 기대효과: <내용>
- 주요 위험: <내용>
- 원문 Reference ID: [SW-01]
- 주요 Evidence ID: <Evidence ID 목록>

### Photonic-CXL (HW-01)

- 기술 유형: HW
- 핵심 접근: 광학 패브릭 기반 CXL 공유 메모리 확장
- 선정 방식: Human-based
- 선정 이유: <내용>
- 핵심 메커니즘: <내용>
- 주요 기대효과: <내용>
- 주요 위험: <내용>
- 원문 Reference ID: [HW-01]
- 주요 Evidence ID: <Evidence ID 목록>

## 3. 핵심 평가 요약 재료

이 영역은 최종 SUMMARY가 아니라 보고서 생성기가 SUMMARY를 작성할 때 사용할 검증된 재료다.

### RDKV

- 핵심 평가: <내용>
- 주요 적용 조건: <내용>
- 핵심 가치: <내용>
- 핵심 제약: <내용>
- 가장 중요한 미확인 사항: <내용>
- 주요 Evidence ID: <목록>

### Photonic-CXL

- 핵심 평가: <내용>
- 주요 적용 조건: <내용>
- 핵심 가치: <내용>
- 핵심 제약: <내용>
- 가장 중요한 미확인 사항: <내용>
- 주요 Evidence ID: <목록>

### 전체 평가 상태

- 유효 관점 칸: <N/8>
- 유효 criterion 블록: <N/46>
- unknown 항목 수: <정수>
- failed 항목 수: <정수>
- 종합 상태: <complete | partial | failed>
- 보고서 생성 조건: <allowed | allowed_with_gaps | blocked>
- 사람이 최종 확인해야 할 사항: <목록>

## 4. 관점별 평가

모든 평가 항목은 다음 형식을 사용한다.

### 평가 블록 형식

#### [<perspective>][<technology_id>][<criterion_id>]

- criterion_id: <고정 criterion ID>
- 판정: <favorable | conditional | unfavorable | unknown | failed | not_applicable>
- 사실·추론: <fact | inference | mixed | unknown>
- 분석 범위: <selected_domain | global | mixed>
- 선택 도메인과의 관련성: <direct | indirect | unclear>
- 평가: <평가 결과>
- 적용 조건: <평가가 성립하는 조건>
- Evidence ID: <[ID], [ID] 또는 없음>
- 근거 신뢰도: <high | medium | low | unavailable>
- 반대 또는 제한 근거: <내용 또는 없음>
- 미확인 사항: <내용 또는 없음>
- 추가 조사 필요: <true | false>

### 공통 판정 Rubric

모든 관점 Agent와 평가 종합 Agent는 다음 판정 정의를 동일하게 사용한다.

- `favorable`: 선택 도메인의 해당 요구조건을 충족한다는 검증 가능한 근거가 있다.
- `conditional`: 특정 조건에서만 요구조건을 충족하거나, 필요한 도메인 요구값이 `TBD`여서 조건부 해석만 가능하다.
- `unfavorable`: 선택 도메인의 핵심 요구조건과 충돌한다는 검증 가능한 근거가 있다.
- `unknown`: 자료가 없거나 부족하여 해당 criterion을 판단할 수 없다.
- `failed`: Agent 실행, 입력 파싱, 도구 또는 파일 처리 실패로 평가를 생성하지 못했다.
- `not_applicable`: 해당 criterion이 기술 또는 선택 도메인에 적용되지 않는다. 반드시 이유를 기록한다.

추가 규칙:

- 논문 저자의 주장만 존재하는 경우 이를 독립 검증으로 표현하지 않는다.
- `unknown`과 `failed`를 혼용하지 않는다.
- 판정값을 합산하거나 평균 내어 기술의 총점 또는 절대 순위를 만들지 않는다.
- `favorable`과 `unfavorable`은 기술 일반이 아니라 선택 도메인과 명시된 조건을 기준으로 판정한다.

### 필수 블록 수

- 기술 성숙도: 3 criterion × 2 technologies = 6
- 시장성: 6 criterion × 2 technologies = 12
- 이해관계자: 4 criterion × 2 technologies = 8
- 도메인 적용성: 10 criterion × 2 technologies = 20
- 전체: 46 criterion blocks

평가 종합 Agent는 필수 criterion 블록을 생략하지 않는다. 자료가 없으면 `unknown`, 실행에 실패했으면 `failed`, 적용되지 않으면 사유와 함께 `not_applicable`로 출력한다.

### 4.1 기술 성숙도

필수 criterion:

- mechanism
- validation_scope
- maturity

#### [technical][SW-01][mechanism]
<평가 블록>

#### [technical][SW-01][validation_scope]
<평가 블록>

#### [technical][SW-01][maturity]
<평가 블록>

#### [technical][HW-01][mechanism]
<평가 블록>

#### [technical][HW-01][validation_scope]
<평가 블록>

#### [technical][HW-01][maturity]
<평가 블록>

### 4.2 시장성

필수 criterion:

- market_size_growth
- commercialization
- adoption
- ecosystem
- cost
- customer_value

RDKV와 Photonic-CXL 각각에 대해 위 criterion의 평가 블록을 모두 출력한다.

자료가 없더라도 블록을 생략하지 않고 다음처럼 출력한다.

#### [market][SW-01][adoption]

- criterion_id: adoption
- 판정: unknown
- 사실·추론: unknown
- 평가: 공개 정보만으로 판단할 수 없음
- 적용 조건: 조사 기준 시점까지 확보된 자료
- Evidence ID: 없음
- 근거 신뢰도: unavailable
- 반대 또는 제한 근거: 없음
- 미확인 사항: 실제 고객·상용 배포 자료 미확보
- 추가 조사 필요: true

### 4.3 이해관계자

필수 criterion:

- competitors
- adopters
- developers
- investors_analysts_media

RDKV와 Photonic-CXL 각각에 대해 위 criterion의 평가 블록을 모두 출력한다.

실제 발언이 아닌 경우 반드시 `inference`로 표시한다.

### 4.4 도메인 적용성

필수 criterion:

- capacity
- quality
- latency
- throughput
- gpu_compatibility
- hardware_dependency
- deployment
- maturity
- customer_value
- domain_fit

RDKV와 Photonic-CXL 각각에 대해 위 criterion의 평가 블록을 모두 출력한다.

도메인 요구값이 없는 경우 “충족”으로 단정하지 않고 `conditional` 또는 `unknown`으로 표시한다.

## 5. TRL 판정 결과

### RDKV

- 추정 TRL: <1~9 또는 unknown>
- 판정 기준 시점: <날짜 또는 자료 버전>
- 충족한 최고 단계: <단계>
- 충족 근거: <Evidence ID 목록>
- 다음 단계에 필요한 근거: <내용>
- 공개되지 않은 정보: <내용>
- 추정 신뢰도: <high | medium | low>
- 추정의 한계: <내용>

### Photonic-CXL

- 추정 TRL: <1~9 또는 unknown>
- 판정 기준 시점: <날짜 또는 자료 버전>
- 충족한 최고 단계: <단계>
- 충족 근거: <Evidence ID 목록>
- 다음 단계에 필요한 근거: <내용>
- 공개되지 않은 정보: <내용>
- 추정 신뢰도: <high | medium | low>
- 추정의 한계: <내용>

## 6. 관점 간 종합

### 일치하는 평가

#### 일치 1

- 관련 평가 기준: <criterion_id>
- 일치 내용: <내용>
- 관련 관점: <목록>
- 관련 기술: <SW-01 | HW-01 | both>
- Evidence ID: <목록>
- 신뢰도: <high | medium | low>

### 상충하는 평가

#### 상충 1

- 평가 기준: <criterion_id>
- 기술 관점: <내용>
- 시장 관점: <내용>
- 이해관계자 관점: <내용>
- 도메인 관점: <내용>
- 상충 원인: <비용 이동, 검증 수준, 적용 조건 등의 설명>
- 관련 기술: <SW-01 | HW-01 | both>
- Evidence ID: <목록>
- 신뢰도: <high | medium | low>

### 조건에 따른 가치 차이

#### 조건 1

- 조건: <내용>
- RDKV 해석: <내용>
- Photonic-CXL 해석: <내용>
- 절대 우열 판정: false
- 조건부 적합성 결론: <내용>
- RDKV가 상대적으로 적합한 조건: <내용 또는 판단 불가>
- Photonic-CXL이 상대적으로 적합한 조건: <내용 또는 판단 불가>
- 판단 불가 조건: <내용 또는 없음>
- Evidence ID: <목록>
- 사실·추론: <fact | inference | mixed>

### 병행 가능성

- 병행 가능성: <내용>
- 필요한 조건: <내용>
- 기대 효과: <내용>
- 추가되는 위험: <내용>
- Evidence ID: <목록 또는 없음>
- 사실·추론: <fact | inference | unknown>

### 직접 비교하면 안 되는 결과

#### 비교 금지 1

- RDKV 지표: <지표명·값·기준 시스템>
- Photonic-CXL 지표: <지표명·값·기준 시스템>
- 직접 비교 불가 사유: <지표·모델·장비·워크로드·평가 방식 차이>
- Evidence ID: <목록>

## 7. 미확인 사항 및 한계

### 자료 공백

- <관점/기술/criterion_id>: <확보하지 못한 자료>

### 실행 실패

- 없음 또는 `<Agent/도구/오류/재시도 여부>`

### 판단 보류

- <항목>: <보류 사유>

### 실험 조건 차이

- <내용>

### 공개 정보 기반 TRL 추정 한계

- <내용>

### 이해관계자 반응 추정 한계

- <실제 발언과 Agent 추론의 차이>

### 확증편향 방지 조치

- 동일 Rubric 적용 여부: <pass | warn | fail>
- 반대·제한 근거 포함 여부: <pass | warn | fail>
- 공급자 주장과 독립 자료 구분 여부: <pass | warn | fail>
- 사실과 추론 구분 여부: <pass | warn | fail>
- 미확인 사항 유지 여부: <pass | warn | fail>

## 8. 도메인 요구조건

- 목표 문맥 길이: <값 | TBD>
- 예상 동시 사용자: <값 | TBD>
- TTFT 목표: <값 | TBD>
- TPOT 목표: <값 | TBD>
- 허용 가능한 품질 손실: <값 | TBD>
- GPU 메모리 제약: <값 | TBD>
- 에너지 제약: <값 | TBD>
- 비용 제약: <값 | TBD>
- prefix cache 재사용률: <값 | TBD>

사용자가 제공하지 않은 값은 임의로 생성하지 않고 `TBD`로 기록한다.

## 9. 근거 인덱스

모든 Evidence는 다음 형식을 사용한다.

### [<Evidence ID>]

- 연결 Reference ID: <SW-01 | HW-01 | WEB-01 등>
- 문서 ID: <문서 ID>
- 문서명: <제목>
- 출처 유형: <paper | official_product | standard | news | market_report | community>
- 저자 또는 기관: <내용>
- 발행일: <날짜 또는 미확인>
- URL: <원문 URL>
- 위치: <PDF 페이지·절·표·웹 문단>
- 검증 방식: <gpu_experiment | measurement | emulation | simulation | statement | analysis>
- 독립성: <author | vendor | third_party>
- 발췌: <근거에 필요한 최소 발췌>
- 적용 조건: <내용>
- 수집 시각: <시각>
- 검증 상태: <verified | partially_verified | unverified>

## 10. REFERENCE CANDIDATES

최종 보고서에서 사용할 수 있는 전체 후보를 제공한다. 보고서 생성기는 본문에서 실제 사용한 Reference만 최종 REFERENCE에 포함한다.

모든 Reference는 다음 구조를 사용한다.

### [<Reference ID>]

- citation_key: <영문자·숫자·밑줄만 사용하는 고유 키>
- source_type: <paper | official_product | standard | news | market_report | community>
- authors_or_organization: <저자 목록 또는 기관명>
- title: <자료명>
- year: <발행 연도 또는 unknown>
- publication_date: <YYYY-MM-DD | YYYY-MM | YYYY | unknown>
- venue_or_site: <학회·저널·arXiv·웹사이트명 또는 없음>
- volume_issue: <권·호 또는 없음>
- pages: <페이지 범위 또는 없음>
- doi: <DOI 또는 없음>
- url: <원문 URL>
- accessed_at: <YYYY-MM-DD>
- language: <ko | en | other | unknown>

Reference 작성 규칙:

- `Reference ID`는 Evidence의 `연결 Reference ID`와 정확히 일치해야 한다.
- `citation_key`는 영문자로 시작하고 영문자, 숫자, 밑줄만 사용한다.
- `citation_key`와 `Reference ID`는 각각 문서 내에서 중복될 수 없다.
- RDKV 원문은 `SW-01`, Photonic-CXL 원문은 `HW-01`을 유지한다.
- 권장 citation key는 각각 `SW01_RDKV`, `HW01_PHOTONIC_CXL`이다.
- 저자·제목·발행정보를 확인하지 못하면 임의로 채우지 않고 `unknown`으로 기록한다.
- DOI와 URL이 모두 없으면 해당 이유를 미확인 사항에 기록한다.

## 11. 출력 완결성 및 보고서 전달 규칙

- 실제 출력에는 `<내용>`, `<목록>`, `<정수>` 등의 템플릿 placeholder를 남기지 않는다.
- 값이 없으면 빈칸 대신 의미에 맞는 `unknown`, `없음`, `TBD`, `not_applicable`을 사용한다.
- 모든 Evidence ID와 Reference ID는 문서 내에서 유일해야 한다.
- 모든 Evidence ID는 근거 인덱스에 존재해야 한다.
- 모든 Evidence의 연결 Reference ID는 REFERENCE CANDIDATES에 존재해야 한다.
- 모든 정량 주장은 값, 단위, 기준 시스템, 실험 또는 검증 방식, Evidence ID를 함께 기록한다.
- Markdown 표 안에 긴 서술을 넣지 않고 관점별 평가 블록 형식을 유지한다.
- 보고서 레이아웃용 LaTeX 명령어를 생성하지 않는다. 특히 `\section`, `\input`, `\include`, `\bibliography` 같은 제어 명령을 출력하지 않는다.
- 기술 표현은 일반 텍스트와 Unicode로 작성한다. 원문 수식이 반드시 필요하면 출처와 위치를 연결하고 임의로 변형하지 않는다.
- 평가 종합 Agent는 평가와 근거를 전달하며, LaTeX 변환·특수문자 escape·표 배치·참고문헌 렌더링은 보고서 생성 Agent가 담당한다.

## 12. SELF VALIDATION

### validation_summary

- overall_result: <pass | warn | fail>
- blocking_issue_count: <정수>
- warning_count: <정수>
- explanation: <최종 상태를 그렇게 판정한 이유>

### schema_validation

- result: <pass | warn | fail>
- explanation: <필수 제목·필드·enum 값 검증 결과>
- affected_items: <목록 또는 없음>

### domain_validation

- result: <pass | warn | fail>
- explanation: <단일 도메인인지, 원문과 정규화 내용이 일치하는지>
- affected_items: <목록 또는 없음>

### assessment_coverage_validation

- result: <pass | warn | fail>
- explanation: <두 기술 × 네 관점 8칸과 총 46개 필수 criterion 블록 존재 여부>
- affected_items: <누락 항목 또는 없음>

### rubric_validation

- result: <pass | warn | fail>
- explanation: <모든 평가가 rubric_version의 공통 판정 정의를 사용했는지>
- affected_items: <정의와 다르게 판정된 항목 또는 없음>

### evidence_integrity_validation

- result: <pass | warn | fail>
- explanation: <모든 Evidence ID가 근거 인덱스에 존재하는지>
- affected_items: <잘못된 ID 또는 없음>

### fact_inference_validation

- result: <pass | warn | fail>
- explanation: <사실·추론·unknown 구분 여부>
- affected_items: <목록 또는 없음>

### comparability_validation

- result: <pass | warn | fail>
- explanation: <서로 다른 지표·실험의 직접 비교 여부>
- affected_items: <목록 또는 없음>

### neutrality_validation

- result: <pass | warn | fail>
- explanation: <승자 선정·총점 순위·과장 표현 여부>
- affected_items: <목록 또는 없음>

### reference_validation

- result: <pass | warn | fail>
- explanation: <Evidence의 Reference ID가 후보 목록에 존재하는지>
- affected_items: <목록 또는 없음>

### output_completeness_validation

- result: <pass | warn | fail>
- unresolved_placeholder_count: <정수>
- duplicate_id_count: <정수>
- invalid_citation_key_count: <정수>
- explanation: <placeholder, ID 고유성, Reference 구조 및 LaTeX 제어 명령 검사 결과>
- affected_items: <목록 또는 없음>

### status_consistency_validation

- result: <pass | warn | fail>
- explanation: <검증 결과와 review_status/report_generation의 일치 여부>
- affected_items: <목록 또는 없음>
```

---

# 평가 종합 Agent의 자체 검증 규칙

## `blocked` 처리해야 하는 경우

다음 중 하나라도 발생하면 다음 상태를 사용한다.

```yaml
review_status: failed
report_generation: blocked
```

- 기술 한쪽의 평가 결과 전체가 누락됐다.
- 네 관점 중 하나의 결과 전체가 누락됐다.
- 정규화된 도메인이 누락됐다.
- 한 기술 전체 또는 한 관점 전체의 평가가 누락되거나 모두 `failed`다.
- 핵심 평가 요약, TRL 판정 또는 관점 간 종합의 주요 주장을 뒷받침하는 Evidence ID를 해석할 수 없다.
- 앞 Agent 출력 형식을 읽을 수 없다.
- 핵심 주장에 연결된 Evidence의 Reference ID를 해석할 수 없다.
- 출력 Markdown 필수 구조를 만들 수 없다.
- 실제 출력에 템플릿 placeholder가 남아 있다.
- Evidence ID, Reference ID 또는 citation_key가 중복되어 근거 연결을 확정할 수 없다.

개별 세부 criterion의 Evidence가 없거나 일부 Evidence 연결만 잘못된 경우에는 전체를 `blocked` 처리하지 않는다. 해당 criterion을 `unknown` 또는 `failed`로 표시하고 `allowed_with_gaps` 여부를 판단한다.

## `allowed_with_gaps` 처리해야 하는 경우

```yaml
review_status: partial
report_generation: allowed_with_gaps
```

- 일부 criterion이 `unknown`이다.
- 시장 규모나 채택 사례가 미확인이다.
- 이해관계자 직접 반응이 미확인이다.
- 일부 Agent 또는 웹 검색이 실패했다.
- 도메인 목표값이 `TBD`다.
- TRL 상위 단계 증거가 부족하다.
- 독립 검증 없이 저자 자료만 존재한다.

## `allowed` 처리 조건

```yaml
review_status: complete
report_generation: allowed
```

- 두 기술 × 네 관점 8칸이 존재한다.
- 총 46개 필수 criterion 블록이 모두 존재하고 `failed`가 없다.
- `unknown_count`와 `failed_count`가 모두 0이다.
- 모든 주요 주장에 유효한 Evidence ID가 존재한다.
- 사실과 추론이 구분됐다.
- 직접 비교 불가 지표가 구분됐다.
- 관점 간 종합이 완료됐다.
- 중대한 자료 공백이나 실행 실패가 없다.
- Self Validation의 blocking 항목이 모두 `pass`다.
- `reference_validation`과 `output_completeness_validation`이 모두 `pass`다.
- 실제 출력에 템플릿 placeholder와 보고서 레이아웃용 LaTeX 제어 명령이 없다.
