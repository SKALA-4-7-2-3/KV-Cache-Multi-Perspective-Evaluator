# Orchestrator–Workers 구현과 실행 계약

이 문서는 현재 브랜치의 `pipeline/` 구현을 설명합니다. 공통 설치는 [README](../README.md), RAG 환경은 [RAG 안내](../rag/README.md), PDF 컴파일 환경은 [보고서 안내](../report/README.md)를 참고하세요. 기존 `docs/pipeline.md`의 순차 연결 설명·루트 보고서 경로 대신, OW 실행과 출력 경로는 이 문서를 기준으로 합니다.

## 강의 근거와 선택 이유

참고 자료는 배기주, 「7. AI Agent 설계 및 구축」, 2026.10, **171쪽 강의 PDF**입니다. 아래 번호는 PDF 뷰어의 1부터 시작하는 페이지이며 슬라이드 하단 번호보다 1 큽니다. 예제 코드를 그대로 복사하는 대신 설치된 LangGraph 계약에 맞게 적용했습니다.

| PDF 페이지 | 강의 내용 | 현재 구현에 적용한 요구 |
| --- | --- | --- |
| 64·66·121 | State의 생명주기·scope·ownership·실패 처리 | control과 큰 payload 분리, task별 scope, 오류·시도·종료 상태 |
| 72·77 | OW는 실행 전 동적 작업 분해·State 저장·fan-out·취합 | `create_plan` → `tasks` → `Send`, 필요한 셀만 실행 |
| 123 | 결과 취합과 synthesis 분리, 최종 결과는 참조로 관리 | worker outcome reducer·단일 aggregator·별도 Review/Report |
| 132·133 | reducer·부분 실패·체크포인트·동시성·join·멱등성·관측성 | terminal outcome, 실패 의존성 처리, 완료 캐시, SQLite 재개, branch 기록 |
| 79 | Generator와 Evaluator 분리·피드백·최대 반복 횟수 | Report 이후 Hybrid Quality·수정 루프·시도 상한 |
| 148 | 원본 보존과 보고서의 raw 자료 직접 연결 | `research.bundle.json`·canonical evidence 보존, Judge의 원문 대조 |
| 150 | 결과·trajectory·운영 지표를 구분한 평가 | Quality와 계획/실행 events, usage 기록을 분리 |
| 162·166 | 확률적 Judge와 결정론적 Gate 분리 | Judge는 노드에서 호출, conditional-edge 함수는 저장된 State로 분기 |
| 168·170 | 코드로 종료 강제·과도한 harness 방지 | 반복·호출·토큰·시간·recursion 상한, 기존 역할 재사용 |

도메인·이해관계자·시장 역할은 같은 조사 bundle을 입력으로 받아 각각 평가할 수 있으므로 OW를 선택했습니다. 역할 catalog는 고정하지만, 실행 계획과 재조사 범위는 저장된 결과와 피드백에 따라 달라집니다. RAG 확보는 그래프 이전 경계이며, Review/Report/Quality는 취합 뒤의 처리와 평가 루프입니다.

강의 137쪽의 고정 병렬 edge 예제만으로 동적 OW를 구현한 것으로 보지 않습니다. 실제 fan-out은 `dispatch`가 State의 `tasks`를 읽어 만든 `Send`입니다. 설치 버전에서 `max_concurrency`는 `RunnableConfig` 최상위에 두며, 동시에 쓰는 outcome 키에는 reducer를 지정합니다.

## 동적 계획·scope·terminal join

구현 경계는 [contracts](../pipeline/contracts.py), [planner](../pipeline/planner.py), [graph](../pipeline/graph.py), [worker adapters](../pipeline/worker_adapters.py)입니다.

1. `initial_state`는 채택된 역할 참조를 해시 검증하고, 필요한 `(role, technology_id, criterion_id)` 셀을 계산합니다. `pending_cells`가 주어지면 그 범위를 사용합니다.
2. Planner가 eligible 셀을 역할별 task로 분해합니다. 구조화 결과는 모든 eligible 셀을 정확히 한 번 덮어야 하며, 요청 밖 셀·중복·잘못된 catalog 항목을 거부합니다. 현재 역할은 다른 역할의 결과를 입력으로 소비하지 않으므로 `dependency_roles`는 빈 목록이어야 합니다. 계약 미달 계획은 한 번 수정 요청하고, 다시 미달하면 실패시키며 고정 fan-out으로 대체하지 않습니다. 계획은 State와 `plans/plan-N.json`에 저장합니다.
3. `dispatch`는 미완료이고 의존 조건이 충족된 task만 `Send`합니다. worker는 한 task의 scope와 공통 bundle/request, 해당 역할의 prior를 받습니다.
4. domain은 해당 기술·기준만 평가하고, market은 해당 셀의 조사·보완을 수행하며, stakeholders는 지정 기술의 운영 조직 관점을 평가합니다. worker가 공용 `accepted_refs`를 직접 갱신하지 않습니다.
5. worker의 예외·명시적 실행 실패는 terminal outcome으로 기록합니다. 지정된 연결·시간 초과 계열 오류는 제한적으로 재시도합니다. 실패한 dependency를 가진 task는 `blocked_dependency`로 수렴합니다.
6. aggregator가 현재 계획의 terminal 결과를 확인하고, 성공 결과를 역할별로 병합합니다. **요청한 셀만 교체하고 나머지 prior 셀은 보존**합니다. 요청 셀 누락은 병합 계약 위반입니다.
7. 실패 범위는 제한된 재계획으로 돌리며, 필요한 역할이 끝내 실패하면 `review_required`로 종료합니다. 실패 역할을 성공으로 간주해 보고서로 진행하지 않습니다. 취합 후에 TRL·Review·Report로 진행합니다.

예를 들어 HW-01 시장 `standardization` 보완은 market task 하나, active cell 하나가 됩니다. domain·stakeholders 결과와 다른 시장 셀을 보존합니다. CLI의 역할 재실행은 그 역할의 전체 셀을 선택하며, 자동 피드백은 셀 단위 선택이 가능합니다. 채택된 역할이 모두 유효하면 worker task 없이 후속 단계를 실행합니다.

그래프에는 dependency 성공 확인·실패 전파·deadlock 종료의 방어 계약이 있지만, 현재 기본 planner가 역할 간 의존성을 생성하도록 허용하는 것은 아닙니다. 오프라인 dependency fixture는 이 방어 계약을 검증하기 위한 합성 입력입니다.

## State의 일곱 설계 고려사항

| 고려사항 | 현재 계약과 이유 |
| --- | --- |
| 1. Control / payload 분리 | `phase`, `tasks`, `pending_cells`, outcome과 반복 카운터는 State에 둡니다. 원본·역할 결과·보고서·품질 본문은 외부 JSON/PDF로 저장하고 `input_refs`, `accepted_refs`, `*_ref`로 연결합니다. |
| 2. 관측성의 위치 | 계획 이유는 task에, 계획·scope·재시도·terminal·join·캐시·quality route의 상세 이력은 `events.jsonl`에 둡니다. API 사용량은 `usage.json`에 분리해 State에 로그 본문을 누적하지 않습니다. |
| 3. 큰 데이터·체크포인트 크기 | `ArtifactStore`가 큰 payload를 저장하고 SHA-256·상대 경로·media/schema 정보를 반환합니다. 체크포인트에는 control·참조·Send envelope를 보존합니다. 현재 saver는 전체 내부 이력을 SQLite snapshot에 저장하므로 자동 크기 제한·pruning을 제공하지 않습니다. |
| 4. 실행·trace 식별 | `run_id`를 RAG 이전에 발급하고 State·실행 폴더·`thread_id`와 연결합니다. LangSmith metadata는 `evaluation_run_id`를 사용합니다. 실제 LangSmith trace ID·PNG는 아직 확보하지 않았습니다. |
| 5. 복구·오류·retry | `task_id`, `plan_revision`, `task_attempt`, 상태·오류·retryable 정보를 기록합니다. 실패 API도 사용량에 반영하며, 중단된 예약은 재개 시 미확인 사용량으로 남깁니다. |
| 6. 병렬 reducer·단일 작성자 | `task_outcomes` reducer는 동일 outcome의 중복 반영을 허용하고 같은 키의 충돌을 거부합니다. 채택된 역할 병합은 aggregator 한 곳에서 수행해 완료 순서에 따른 덮어쓰기를 피합니다. |
| 7. 종료 상한 | worker 재시도·재계획·Quality 횟수, 후속 API 예산, graph recursion 상한을 코드로 둡니다. `termination_reason`으로 상한·의존성·검토 필요 이유를 남깁니다. |

`accepted_validity`는 현재 TypedDict의 선택 필드입니다. 실행 중 채택 판단은 outcome, artifact hash와 cache stamp로 이루어지며 별도의 validity map이 채워지는 것으로 설명하지 않습니다. SQLite saver는 **한 로컬 실행 프로세스**용이며 분산 writer용 저장소가 아닙니다.

## TRL 초안과 최종 팀 추정

[trl](../pipeline/trl.py)은 Review-compatible technical 결과를 입력받아 기술별로 단계 초안을 생성합니다. 입력에는 단계 rubric, 기존 기술 분석, 그 기술에 적격한 evidence와 원문 document가 포함됩니다. 초안은 단계별 `met/not_met/unknown`, 이유, evidence ID를 갖습니다. 누락 단계는 `unknown`으로 남기고, 빈 근거·타 기술 ID·잘못된 검증 방식의 충족 주장을 차단합니다.

기술별 성공 초안은 `trl-drafts/<technology>-<stamp>.json`에 원자적으로 저장합니다. stamp는 기술별 입력·모델·프롬프트·스키마·TRL 코드 hash를 포함하므로, 다른 기술의 생성 실패 후 재개할 때 완료된 기술의 같은 초안을 재사용할 수 있습니다. 저장 초안은 스키마를 확인하고 현재 source·대상·검증 방식 검사를 다시 거칩니다. 연결·시간 초과 계열 오류는 최대 한 번 재시도하며, 스키마 오류·일반 API 오류를 무조건 재시도하거나 실패를 `unknown` 성공으로 저장하지 않습니다.

[Review bridge](../pipeline/review_bridge.py)는 논문·웹 결과를 canonical document/evidence와 연결합니다. market·stakeholders가 확보한 자료도 동일 구현의 근거로 검증 가능하면 TRL 입력에 기여할 수 있습니다. 웹 자료에는 수집기가 제공한 `target_technology_id`, `target_version`, `target_identity_verified=true`와 원문 연결이 필요합니다. 통합기가 이 provenance를 자동 발급하지 않습니다. 인접 제품·알고리즘의 성공을 선정 기술의 운용 근거로 승격하지 않습니다.

Review가 별도 의미 감사와 source/대상/방법 검사를 수행하고 **1단계부터 연속으로 확인한 최고 단계**를 `synthesis.trl`로 내보냅니다. 높은 단계를 단독 충족해도 낮은 단계 공백을 건너뛰지 않습니다. 7·9단계의 operational, 8단계의 qualification/operational 조건을 구분하며, 시뮬레이션은 실제 운용 근거가 아닙니다. 1단계부터 확인되지 않으면 `level: null`입니다.

`trl.output.json`은 초안이며, 최종 팀 추정은 `review.output.json`의 `synthesis.trl`입니다. 보고서의 기술 성숙도 절에는 Review의 값·근거·다음 검증 조건을 보존해야 합니다. 이 값은 **공개 정보 기반 팀 추정이며 공식 TRL 인증이 아닙니다**. 모델/API 오류나 감사 미실행을 충족 판정으로 바꾸지 않습니다.

## 보고서 본문 작성 계약

Report는 원문에서 확인한 내용·조건부 해석·실제 자료 공백을 읽는 사람에게 설명합니다. 내부 검사 상태, 근거 ID 연결 오류, 원래 의견 보존 안내를 최종 본문이나 부록에 반복하지 않습니다. 검토 notes는 저장 입력과 Review 기록에 보존하며, 코드가 진단 부록을 강제로 붙이지 않습니다. 이 출력 정책은 불확실성을 제거하거나 반려를 승인으로 바꾸는 절차가 아닙니다.

`UPSTREAM_ANALYSIS_JSON.draft_findings`를 `ParsedReportInput.market_findings`에 그대로 보존합니다. 자료가 두 기술의 여섯 canonical 시장 기준을 모두 덮을 때 생성·수정 프롬프트와 validator의 **시장성 12셀 계약**을 활성화합니다. 각 기준은 시장규모·성장, 사업화, 도입, 생태계 지원, 표준화, 사업가치입니다. 완전한 구조화 자료가 없는 기존 standalone 입력에는 이 추가 계약을 자동 적용하지 않습니다.

각 셀은 `시장성` subsection 안에 정확한 `% BEGIN_MARKET_CELL`/`% END_MARKET_CELL` 경계를 한 번 두고, 보이는 기술·항목 제목과 실제 분석을 작성해야 합니다. 근거 인용 또는 미확인 범위·`판단 영향:`·`다음 확인:`이 필요합니다. 누락 셀·제목뿐인 셀·가짜 marker를 반려하고 모델에 수정을 요청하며, 코드가 분석 문단을 대신 채우지 않습니다. 형식 통과 뒤에도 주장과 인용의 의미는 Quality가 별도로 검사합니다.

숫자·단위를 보존한 범위는 `128K--256K` 또는 `128K부터 256K까지`처럼 표시합니다. 숫자 사이 raw TeX `~`는 PDF에서 공백이 되므로 조판 단계가 산술값·단위·인용을 유지하고 구분기호만 `--`로 표시합니다. URL·수식·주석·`A100~64GB` 같은 모델명 연결은 제외하며, 남은 잘못된 범위 표기는 validator가 반려합니다.

## Hybrid Quality

[report_quality](../pipeline/report_quality.py)는 보고서 생성 이후의 별도 평가 노드입니다. 생성 결과를 검증한 것처럼 표시하는 flag를 Report가 직접 발급하지 않습니다.

### 평가 절차

1. 실제 PDF·TeX를 읽고 hash, 컴파일된 PDF, 전체 10쪽 이하, 텍스트 추출, 보고서 구조·인용·최종 TRL 보존을 검사합니다. `SUMMARY`와 `REFERENCE`를 포함한 기존 구성을 유지합니다.
2. Controller가 **최종 PDF의 모든 페이지와 비어 있지 않은 줄 단위**에 canonical ID를 부여합니다. 실제 provider는 모든 ID를 필수 key로 둔 strict schema로 주장·인용을 추출하며, 각 줄에 하나 이상의 주장 또는 구체적인 비주장 이유를 요구합니다. 표·미인용 사실·문장 줄바꿈도 포함하고, 누락·중복·새 ID·빈 disposition을 반려합니다. 주장에 붙는 `report_quote`는 모델의 재작성 문장 대신 controller가 원래 줄 전체에서 공백·개행까지 그대로 연결합니다. 생성자가 제공한 주장 목록을 평가 분모로 사용하지 않습니다.
3. 인용된 주장은 PDF 문단에 실제 표시된 인용 후보 집합별로 묶고, 그 문서들에 속한 **모든 canonical 원문 기록**을 한 audit prompt에 전달합니다. 복수 문서의 근거가 함께 필요한 주장을 원문 shard로 나누지 않습니다. 주장 배치는 입력 길이에 따라 나누더라도 각 배치는 완전한 후보 문서 집합을 받습니다. `citation_keys=[]`인 미인용 주장은 문단에 후보 인용이 있어도 전체 canonical 원문과 대조합니다. 판정의 source ownership은 각 주장이 실제 선택한 인용과 quote 집합으로 별도 검사합니다.
4. Audit provider도 모든 claim ID를 필수 key로 둔 strict schema를 사용합니다. 각 원문 전체를 최대 800자의 연속 span으로 나누어 전달합니다. `source_reference.anyOf`는 등록 `evidence_id`마다 `span_index`를 0부터 그 원문의 실제 마지막 span까지 허용해 ID와 위치를 함께 제한합니다. Controller가 해당 원문에서 `supporting_quotes`와 evidence ID를 부여하며 모델이 quote를 재작성하거나 구간을 합치지 않습니다. supported/contradicted에는 실제 연속 원문, document hash·locator·기술 ownership·실제 인용 연결이 필요합니다. 원문에 없는 참조, synthetic 자료, 다른 문서·기술의 근거를 거부합니다. 마지막 rubric에는 사용하지 않은 자료·반대 원문까지 **전체 canonical 원문**을 전달해 groundedness, neutrality, bias_control, perspective_coverage를 평가합니다. TRL·시장·이해관계자·도메인 설명과 시장의 기술별 여섯 기준을 확인하고, 근거가 없으면 영향과 다음 확인을 포함한 공백 설명을 요구합니다.
5. 코드가 gate·점수·미해결 중대 finding을 읽고 결과를 확정합니다. 다음 edge를 선택하는 `quality_gate`는 모델을 호출하지 않습니다.

### PDF 문단 인용과 핵심 주장 추적

Controller는 추출된 PDF의 공백·새 들여쓰기·번호가 붙은 제목·목록·참고문헌 항목을 문단 경계로 구분합니다. 같은 본문의 줄바꿈과 인접 페이지의 이어지는 문단은 연결하며, 제목이나 새 항목의 인용을 다른 문단에 넘기지 않습니다. 그 문단에 **실제로 표시된 번호 인용**만 `paragraph_citation_keys` 후보로 연결합니다.

Judge는 후보 안에서 각 주장을 뒷받침하는 `citation_keys`를 선택해야 합니다. 후보 문서 전체를 감사 입력으로 받았다는 사실만으로 그 주장의 출처가 확정되지는 않습니다. **H2는 실제 선택한 인용과 핵심 주장 추적 결과를 검사**합니다. 핵심 사실·저자 보고 주장에 선택 인용이 없으면 문단에 후보가 있어도 미인용으로 처리하며, 원문 의미와 인용 ownership 검사도 생략하지 않습니다.

`supported` 판정은 quote 집합의 기술 ownership 합집합이 주장의 모든 기술을 덮어야 합니다. `contradicted/unsupported/uncertain`에 quote가 있으면 일부 기술의 근거일 수 있지만, 주장에 기술이 지정된 경우 적어도 하나는 일치해야 합니다. 실제 인용된 주장은 quote의 인용 키 중 적어도 하나가 그 주장이 선택한 키와 일치하고, 모든 quote 키가 해당 물리적 문단의 실제 인용 범위 안에 있어야 합니다. document hash·locator·원문 인용 검사도 그대로 적용합니다. 문단에 나열된 모든 참고문헌이 각각 모든 원자 주장을 입증하도록 요구하지는 않습니다. 미인용 주장의 전체 원문 감사는 인용 누락을 치유하지 않으며 H2 판정은 그대로 유지합니다.

공백을 정규화한 독립 줄이 정확히 `공개 정보 기반 팀 추정이며 공식 인증이 아니다.`이면 팀 추정 성격을 밝히는 고정 비주장으로 처리합니다. 각 물리적 페이지의 마지막 비어 있지 않은 줄이 해당 페이지 번호와 같을 때만 페이지 번호로 고정합니다. 두 경우 모두 strict schema와 validator가 빈 주장 목록·정해진 비주장 사유를 요구하며, 전체 줄 분모와 최종 rubric 입력에서 제외하지 않습니다. 기술별 인증이나 검증 실적을 추가로 주장하는 문장은 이 고정 처리 대상이 아닙니다.

### 코드 기준값과 라우팅

다음은 **설정된 채택 기준이며 실제 실행 점수·통과 결과가 아닙니다**. 축 가중치는 groundedness 40%, 나머지 세 축 각 20%이며 각 축 4/5 이상·가중 점수 80 이상을 요구합니다. 형식·원문 identity·핵심 주장 추적·추천/우열 금지·관점 포함·미해결 major/critical finding 등 hard gate도 함께 충족해야 합니다. 낮은 점수나 미검사 항목을 평균으로 덮어 통과시키지 않습니다.

H1은 원문과 모순되는 `contradicted` 판정이나 중대 사실 오류를 차단합니다. H2와 H7은 핵심 주장이 `supported`로 검증되지 않으면 차단하며, H2는 핵심 사실·저자 보고 주장의 실제 인용 누락도 별도로 차단합니다. 일부 기술에 대한 반례를 인정하는 계약이 핵심 주장의 미확인을 승인으로 바꾸지는 않습니다.

| Quality route | 그래프 처리 |
| --- | --- |
| `passed` | `content_quality_pass`로 종료 |
| `report_repair` | 이전 TeX 후보와 구조화 피드백으로 Report를 수정한 뒤 Quality 재평가 |
| `upstream_replan` | 역할·기술·기준 범위를 task로 변환해 재조사. technical 전용 요청은 관점 worker 없이 TRL/Review 경로로 전달 |
| `review_required` | Judge 오류·원문 공백·사람 검토 등 자동 완료할 수 없는 이유를 보존하고 종료 |

기본 재계획 상한은 2회, Quality 평가 상한은 3회입니다. 품질 상한에 도달해 미달이면 `failed_quality`입니다. API·Judge 오류는 성공 판정이 아니며, `failure_type`과 미검사 범위를 남깁니다. `content_quality_pass`도 Judge rubric의 결과이며 공식 인증이나 PDF 시각 검토의 완료를 뜻하지 않습니다.

웹 근거는 등록된 **수집 원문 전체**를 사용합니다. 선택된 인용 발췌가 아닌 전체 excerpt의 SHA-256을 document hash와 대조하고, evidence/reference ID·인용 키·URL·관련 기술을 확인합니다. 전체 source report가 없으면 canonical에 남은 원문 자체가 같은 등록 hash인지 확인하며, 새 hash를 발급해 불일치를 덮지 않습니다. 전체 원문이 없거나 identity가 다르거나 여러 원문이 충돌하면 평가를 중단합니다.

전체 canonical evidence JSON의 기본 한도는 **1,000,000자**입니다. 출처를 필터링하거나 원문을 자르지 않으며, 전체 corpus 또는 완전한 인용 문서 집합이 한도를 넘으면 미검사 상태로 종료합니다. 연속 span으로 나누는 것은 전체 원문을 빠짐없이 전달하고 실제 quote를 연결하기 위한 표현 방식입니다. `quality.input-plan-N.json`에 예정 입력·호출, `quality.evidence-N.json`에 원문 집합, `quality.claims-N.json`에 줄·주장·감사 기록을 보존합니다.

`checked_claims.checked`와 판정별 부분 집계는 현재 validator를 통과해 완료된 audit 배치만 누적합니다. 중간 실패 시 예정 배치나 미완료 주장을 완료 수에 포함하지 않으며, 부분 완료 수를 전체 Quality 통과로 해석하지 않습니다.

통합 CLI는 `--max-judge-calls`로 **각 Quality 시도의 호출 상한**을 설정하며 기본값은 64회입니다. 독립 `evaluate_report` 함수의 기본값은 36회입니다. 이 로컬 상한과 후속 공통 모델 한도는 함께 적용됩니다. Judge·planner·worker·TRL·Review·Report의 실제 API 시도는 모두 `--max-model-calls` 안에 포함되며, Judge 상한만 늘려 공통 예산을 우회할 수 없습니다.

원문 감사의 strict schema는 각 주장에 `technology_references`를 요구합니다. `supported`는 모든 해당 기술에 canonical owner가 일치하는 원문·span을 하나 이상 선택해야 하며, 적격 원문이 없는 기술은 해당 판정 분기를 제공하지 않습니다. 다른 판정은 기술별 참조를 null로 남길 수 있습니다. 기술 ID가 없는 범용 사실은 별도의 원문 참조가 최소 한 개 필요합니다. 참조를 중복 제거해 실제 원문 인용으로 연결한 뒤 기존 hash·locator·문단 인용·ownership 검사를 다시 수행합니다.

### Judge 응답 캐시와 계약 보정

실제 provider의 주장 추출(`atomize`)·원문 감사(`audit`)에서 **현재 normalizer와 validator를 모두 통과한 raw 응답**만 Quality 출력 경로 아래 `quality-responses/`에 원자적으로 저장합니다. 요청의 단계·모델·instructions·실제 prompt·strict schema·버전을 정렬한 JSON의 SHA-256이 키입니다. 로드할 때 envelope의 키·버전·raw 형식·SHA-256을 확인하고, 현재 normalizer와 validator를 다시 실행합니다. 요청·모델·스키마 변경, 손상 또는 현재 계약 위반은 재사용하지 않습니다.

계약 오류에는 **최대 한 번의 수정 호출**을 허용합니다. 원래 원문·PDF 줄·주장 목록은 유지하고 오류와 직전 미신뢰 응답만 추가합니다. 수정 요청의 원인이 된 응답과 오류는 `quality.invalid-*.json`에 남깁니다. 수정 응답도 같은 현재 검사를 통과해야 하며, 임계값을 낮추거나 미검사 주장을 통과로 바꾸지 않습니다.

수정 프롬프트로 검증된 raw 응답은 실제 요청 키에 저장하고, 원래 요청 키에서 이를 가리키는 alias를 발급합니다. alias의 원래 키·대상 키 형식·실제 프롬프트 hash와 대상 envelope의 `verified_base_key`·raw hash·버전을 함께 확인해 보정 provenance를 보존합니다. 기존 원래 요청 캐시 키는 유지하며 손상된 alias는 cache miss입니다. 캐시 재사용도 현재 원문·주장 계약을 통과해야 하고, 최종 rubric과 전체 gate를 다시 평가합니다. 캐시 파일 자체는 보고서의 Quality 승인 기록이 아닙니다.

### 보고서 출처 독해 계약

보고서 작성 전에 `source_analysis`가 각 웹 출처의 실제 excerpt를 읽어 관찰·운영/시장 해석·한계·생략 사유를 생성합니다. 첫 호출의 인용문이 원문 계약을 어기면, 수정 호출에는 원문 전체를 800자 이하의 연속 span으로 나누어 전달하고 모델이 선택한 `supporting_quote_id`를 실제 `supporting_quote`와 위치에 연결합니다. 공백·개행·단어를 고치거나 서로 다른 구절을 합칠 수 없습니다.

계약 미달 또는 파싱되지 않은 결과에는 **최대 한 번의 모델 수정 요청**을 보냅니다. 직전 candidate와 오류를 원문과 함께 전달하며, 다시 실패하면 완료 결과로 저장하지 않습니다. 전송·예산 오류에는 이 모델 재시도를 적용하지 않습니다. `source-readings/<key>.attempt-N.json`에 candidate·raw output·validation error를 남겨 실패 자료도 확인할 수 있게 합니다.

여섯 identity 필드 `source_id`, `title`, `url`, `citation_key`, `role`, `technology_ids`는 코드가 원래 출처에서 부여하고, 저장 독해를 재사용할 때 여섯 값과 인용 계약을 다시 대조합니다. 성공한 독해는 `report.source-analysis.json`과 출처별 완료 캐시에 기록합니다. source task별 호출은 후속 공통 API ledger에 포함됩니다.

## 실행·재개·부분 재실행

공통 설치를 마친 뒤 저장소 루트에서 실행합니다. 기본 입력은 [config/pipeline.json](../config/pipeline.json)의 `saved` bundle입니다. 아래 `--as-of`는 명령 예시의 고정 조사 기준일입니다.

```bash
# 기본: 후속 조사·종합·Report·Quality까지 실제 API 실행
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run

# 같은 입력·모델·날짜·예산으로 재개
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run --resume

# market 역할 전체 셀 재조사; 나머지 역할 결과는 재사용
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run --resume --rerun market

# TRL 이후만 다시 계산
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run --resume --rerun trl

# Report와 Quality 재실행
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run --resume --rerun report

# 보고서는 재사용하고 Quality의 캐시를 무효화
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run --resume --rerun quality

# 평가 호출 상한만 변경: Quality 재평가, 유효한 앞 단계 결과 재사용
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/ow-run --resume --max-judge-calls 96
```

`--rerun`은 `domain`, `stakeholders`, `market`, `trl`, `review`, `report`, `quality`를 받습니다. TRL/Review/Report/Quality의 명시적 재실행은 해당 단계와 이후 캐시를 무효화합니다. 역할 재실행은 그 역할의 task를 새 revision으로 계획하며, 달라진 후속 입력에 맞게 결과를 갱신합니다. 보고서 모델 변경은 Report 이후, `--draft` 변경은 Review 이후를 다시 처리합니다.

`--report-model`과 `--judge-model`은 선택 옵션이며 생략하면 공통 `--model`을 사용합니다. `--judge-model`은 Quality의 주장 추출·원문 감사·최종 rubric에 적용합니다. Quality stage stamp에는 실제 Judge 모델과 `--max-judge-calls`가 포함됩니다. 재개 시 `run.json.quality_settings`의 두 값이 달라지면 Quality 캐시만 무효화하며, 유효한 Research·TRL·Review·Report artifact는 보존합니다. 호출 상한 변경은 공통 모델·토큰 예산의 증액을 뜻하지 않습니다.

`--stop-after` 기본값은 `quality`입니다. `prepare`는 입력 확보까지만, 역할 이름은 해당 역할만 실행하고 종료하며, `trl`, `review`, `report`는 해당 단계 뒤에서 종료합니다. `--draft`는 새 종합 의견 생성·의미 검토를 생략하는 초안 경로이며 TRL 초안·TRL 의미 검사와 최종 Quality를 자동 면제하지 않습니다.

```bash
# 저장 입력 변환만: 외부 API 호출 없음 (--run-rag 사용하지 않음)
uv run --frozen python -m pipeline --output outputs/ow-prepare --stop-after prepare

# 실제 새 RAG를 별도 subprocess에서 실행
uv run --frozen python -m pipeline --run-rag \
  --pdf rag/papers/2605.08317.pdf --pdf rag/papers/2607.27187.pdf \
  --as-of 2026-10-07 --output outputs/ow-live
```

### 재개 계약

- `run.json`과 요청 identity를 RAG 이전에 저장합니다. live RAG에는 같은 run에서 안정적인 job ID를 전달합니다.
- 같은 코드·입력의 미완료 체크포인트는 `invoke(None, config)`로 이어갑니다. 완료된 worker 결과·artifact·캐시를 재사용해 성공한 작업의 중복 호출을 피합니다.
- 완료 실행은 채택된 JSON 참조와 최종 TeX/PDF hash를 확인한 뒤 재사용합니다. 파일이 변경되었으면 명시적 재실행이나 새 출력 경로가 필요합니다.
- PDF 내용·경로, 요청, RAG 모드, 공통 `--model` 또는 조사 기준일을 바꾸면 새 출력 경로를 사용합니다. 보고서·Judge 전용 모델 변경은 위의 단계별 무효화 계약을 따릅니다. 예산 증액은 아래 `--extend-budget` 절차를 따릅니다. 완료 역할은 해당 역할 source fingerprint와 artifact hash로 채택 여부를 판단합니다. 역할 fingerprint에는 `pipeline/governance.py` 전체와 `pyproject.toml`, `uv.lock`이 포함되며, 보고서 생성·Quality만 바뀌면 입력·artifact가 유효한 완료 역할을 재사용할 수 있습니다.
- API를 이미 보냈으나 응답·완료 기록 전에 중단된 경우 완전한 exactly-once 호출을 보장하지 않습니다. ledger는 해당 예약을 미확인 사용량으로 남기고, 완료가 기록된 artifact를 기준으로 재사용합니다.
- SQLite saver는 단일 로컬 실행 프로세스용입니다. 같은 출력 경로에서 여러 프로세스를 동시에 실행하지 않습니다.

TRL·Review·Report·Quality의 완료 캐시는 전체 저장소 hash 대신 **단계별 source fingerprint**와 실제 입력·모델·기준일로 stamp를 계산합니다. 관련 없는 단계 수정으로 완료 API 호출이 반복되는 것을 줄입니다. 단계의 source hash는 `events.jsonl`의 `stage_code_sha256`에 기록합니다.

| 단계 | source fingerprint의 업무 범위 |
| --- | --- |
| TRL | `pipeline/trl.py`와 TRL 판정에 필요한 Review rubric·schema·contract·review 코드 |
| Review | `pipeline/review_bridge.py`와 `agent/review/team_review` |
| Report | `pipeline/reporting.py`, reference metadata, `report/src` |
| Quality | `pipeline/report_quality.py`와 보고서 parser·validator를 포함한 `report/src` |

공통 State·입력·artifact·governance 코드와 dependency lock은 관련 단계 모두에 포함합니다. `.cache`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.git` 등 생성된 캐시 디렉터리는 source fingerprint에서 제외합니다. 따라서 **Quality 코드만 수정하고 입력·모델·공통 의존성·artifact가 같으면 Review와 Report를 재사용**할 수 있습니다. 보고서 parser/validator 수정은 Report와 Quality에 함께 영향을 줍니다. 명시적 `--rerun report`는 이러한 자동 재사용과 별도로 Report 이후 캐시를 무효화합니다.

보고서 위치는 `reports/revision-N/`이며, 현재 최종 파일 경로는 `run.json.artifacts` 또는 `report.output.json`을 확인합니다. 루트의 단일 `report.pdf` 경로를 가정하지 않습니다.

## 예산·사용량 적용 범위

**governance는 saved/live RAG 결과를 확보한 다음 생성되며, 후속 API만 계측합니다.** live RAG는 별도 환경의 subprocess이므로 이 ledger의 호출·토큰·시간에 포함되지 않습니다. RAG 설정과 한도는 별도로 확인해야 합니다.

후속 한도는 기본 모델 시도 160회, 검색 24회, extract/fetch 각 48회, 토큰 5,000,000, 시간 1,800초입니다. 이 값은 코드 기본값이며 실제 사용량이 아닙니다. CLI는 `--max-model-calls`, `--max-search-calls`, `--max-extract-calls`, `--max-fetch-calls`, `--max-tokens`, `--max-seconds`를 지원합니다. 각 역할의 내부 한도와 후속 공통 한도가 함께 적용됩니다.

[governance](../pipeline/governance.py)는 HTTP 전송 전에 호출 수와 보수적 토큰 예약을 잡습니다. 실제 usage를 받으면 반영하고 실패·응답 미확인 시 예약을 무단으로 반환하지 않습니다. 출력 한도가 없는 생성 요청에는 wire limit을 넣고, HTTP timeout은 남은 시간으로 제한합니다. 시간 검사는 후속 요청의 시작과 timeout 경계에 적용되며 RAG subprocess·로컬 PDF 컴파일·모든 계산을 선점 중단하는 전체 실행 deadline은 아닙니다.

`usage.json`에는 call/task ID, 종류, 시도·상태·토큰·오류 종류를 저장하고 API 키나 request 본문을 저장하지 않습니다. 재개는 기존 사용량·미확인 예약을 유지합니다. 같은 한도로 재개하거나, `--resume --extend-budget`과 모든 한도 옵션을 함께 사용해 각 한도를 기존 값 이상으로 늘릴 수 있습니다. 감소 또는 명시하지 않아 기본값으로 낮아진 항목이 있으면 거부합니다. 성공한 증액은 변경 전후 한도와 당시 counts·실제/미확인 토큰·경과 시간을 `budget_extensions`에 기록합니다.

## 관측성과 검증 범위

로컬에서 계획·실행 수·scope·재사용·terminal join·quality route는 `events.jsonl`, API 사용량은 `usage.json`, 종료·모델·입력·코드 identity는 `run.json`에서 확인합니다. 결과의 내용 품질, 계획 대비 실제 worker 경로, 운영 비용·시간을 서로 다른 증거로 확인합니다.

LangGraph의 run name·tags·metadata를 유지하며 실제 `judge_model`과 `report_model`을 metadata에 기록합니다. LangSmith 설정이 있는 환경에서 trace를 수집할 수 있습니다. **현재 키 미설정으로 실제 동적 trace와 PNG는 미검증**입니다. 제출용 trace는 같은 run의 구조화 plan, 실제 Send scope, terminal join, Quality와 repair loop가 보이도록 수집하고 실행 순서가 드러나는 이름으로 저장해야 합니다. 정적 구조 그림이나 오프라인 fixture를 실제 API trace로 표시하지 않습니다.

오프라인 계약 테스트의 실행 명령은 다음과 같습니다. 테스트 성공 수나 실제 보고서 성적은 이 문서에 기록하지 않습니다.

```bash
uv run --frozen python -m unittest \
  pipeline.tests.test_orchestration \
  pipeline.tests.test_trl_pipeline \
  pipeline.tests.test_planner \
  pipeline.tests.test_governance
```

fixture는 worker/provider·보고서 생성·Quality 경계를 가짜로 두고 실제 saved bundle·bridge·Review 계약·Report parser·SQLite 재개를 검증합니다. 실제 원문의 의미 평가, 외부 API 사용량, 컴파일된 PDF 품질과 LangSmith 실증은 별도 확인이 필요합니다. Retrieval Hit Rate@K·MRR, Judge calibration·실제 Quality 점수·최종 보고서 페이지 수의 측정 결과는 아직 기록하지 않았습니다.

보고서 제출 때는 최종 revision의 PDF가 10쪽 이하인지, SUMMARY/REFERENCE와 네 관점·출처가 포함되는지, 표·수식·인용·한글 배치가 읽히는지 시각 확인합니다. `content_quality_pass`, 시각 확인, LangSmith trace 확보를 각각 구분해 기록합니다.
