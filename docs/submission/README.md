# KV Cache 기술 평가 — Multi-Agent Orchestration 제출 안내

논문 분석 JSON과 자연어 요청을 받아 **RDKV(SW)**와 **Photonic-CXL(HW)**를 TRL·시장·이해관계자·도메인 관점에서 비교한다. 대상 시나리오는 클라우드 데이터센터의 장문맥 문서 QA다. 예산·SLO·장비 조건이 입력되지 않았으면 임의로 채우지 않는다.

- [제출 준비 브랜치: feat/skala-final-submission](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/tree/feat/skala-final-submission)
- [역할별 커밋과 이후 문서 변경](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commits/feat/skala-final-submission)
- 기준 main 커밋: `a633cc1`. 기존 RAG·관점 에이전트·Review·보고서 생성기를 재사용하고, 이번 과제에서는 **동적 계획·선택적 재조사·State/재개·TRL 전달·보고서 이후 품질 루프**를 추가·보완했다.
- 기존 기능의 상세 설명은 [main README](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/main/README.md)를 참고한다. 이 문서는 수업 과제에서 추가·보완한 설계와 제출 증빙을 정리한다.

사용자의 Codex 계정 크레딧으로 실제 관점 평가·TRL·보고서 작성을 실행했다. 현재는 전송 형식을 보완하여 기존 실제 **8쪽 PDF**를 재사용한 **Quality만 재실행 중**이다. 새 Report 작성이나 전체 파이프라인 신규 실행으로 표시하지 않는다. 직전 원문 대조는 `judge_timeout`으로 중단됐으며, 현재 점수·H1–H7·내용 승인 결과는 미확정이다. 실행 범위와 상태는 [실행 검증 기록](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-final-submission/docs/validation-20261007-api-credit.md)에서 구분한다.

## 1. SW·HW 선정 이유

| 기술 | 접근과 선정 이유 | 비교할 조건 |
| --- | --- | --- |
| RDKV — SW | KV 제거와 양자화를 함께 제어하여 저장 데이터량을 줄인다. 기존 GPU의 메모리 제약을 소프트웨어로 완화하는 접근을 분석한다. | 품질 손실·혼합 정밀도 처리·커널 호환성 |
| Photonic-CXL — HW | 광 연결과 CXL 기반 외부 공유 메모리로 KV 저장 공간을 확장한다. 인프라 확장이 용량 문제와 데이터 이동에 미치는 영향을 분석한다. | 외부 메모리 경로의 대역폭·지연·인프라 비용·검증 수준 |

같은 KV 메모리 문제에 대한 데이터량 감소와 저장 공간 확장의 차이가 분명하다. GPU 실험과 에뮬레이션·시뮬레이션의 배수를 직접 대결시키지 않으며, 조건·근거·검증 공백으로 비교한다. 최종 보고서는 특정 기술의 도입 추천이나 절대 순위를 제시하지 않는다.

## 2. Pattern과 동적 처리

**LangGraph Orchestrator–Workers(OW)**를 선택했다. Domain·Stakeholders·Market은 같은 연구 자료와 요청을 읽고 독립적으로 평가할 수 있으므로, 실행 전에 필요한 작업을 계획하고 취합하는 구조가 적합하다.

```text
saved/live RAG 확보 → Planner → State에 task 저장 → Send로 선택 Worker 실행
→ 모든 task의 terminal 결과 취합 → TRL 초안 → Review → Report·PDF → Hybrid Quality
Quality 결과: 통과 / 보고서 수정 / 지정 항목 재조사 / 검토 필요·상한 종료
```

- 계획은 미완료·무효화된 평가 셀과 피드백을 기준으로 만든다. 역할 catalog와 실제 실행 task는 구별한다.
- 예: HW 시장 `standardization` 보완은 해당 셀만 재조사하며 다른 성공 결과를 보존한다. 모든 역할이 유효하면 Worker 없이 후속 단계로 진행한다.
- 모든 예정 task가 성공 또는 실패 상태에 도달한 뒤 aggregator 한 곳에서 병합한다. 실패·retry·재개는 기록하고 무제한 반복하지 않는다.
- 기본 재계획 상한은 2회, 완료된 내용 품질 평가 상한은 3회다. Judge가 판단하고 코드 Gate가 저장된 결과로 분기한다.

동적 분기는 [기존 offline 제어 trace](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/47df0864-e944-4660-834c-d64a9c8f6392?poll=true)에서 최초 Worker 3개 → 보고서 수정 → HW 표준화 1셀 재조사를 확인했다. 모델·보고서·Quality 경계가 합성 fixture인 제어 검사이며, 이 판정을 실제 PDF의 품질 점수로 사용하지 않는다. 최신 실제 모델 실행과 원격 trace의 범위는 6절에 기록한다.

## 3. State의 일곱 설계 항목

| 항목 | 적용과 이유 |
| --- | --- |
| 1. Control / payload 분리 | `phase`, `tasks`, `pending_cells`, outcome·반복 카운터는 State에, 큰 원문·결과·PDF는 외부 파일과 `*_ref`에 두어 전송·저장 중복을 줄인다. |
| 2. 관측성 위치 | 결정에 필요한 상태와 계획 이유만 State에 둔다. 상세 흐름은 `events.jsonl`, 모델·검색 사용량은 `usage.json`, Codex 안전한 호출 정보는 `codex.calls.jsonl`에 둔다. LangSmith에는 정제한 trace와 실행 태그를 연결한다. |
| 3. 큰 데이터·체크포인트 비용 | `ArtifactStore`의 상대 경로·SHA-256 참조와 SQLite checkpoint를 사용한다. 현재 saver에는 자동 pruning이 없으므로 무제한 보관을 전제하지 않는다. |
| 4. 상관 ID | RAG 이전에 `run_id`를 발급하고 `thread_id`, `task_id`, `call_id`, artifact hash와 연결한다. LangSmith 실행 태그와 로컬 receipt의 `evaluation_run_id`로 같은 실행을 추적한다. |
| 5. 복구·오류·retry | `plan_revision`, `task_attempt`, 오류·retryable 정보를 기록한다. 완료 결과는 hash 검증 후 재사용하고 실패·응답 미확인 사용량을 초기화하지 않는다. |
| 6. 병렬 reducer·단일 작성자 | outcome reducer는 같은 키의 동일 결과를 중복 반영하지 않고 충돌을 거부한다. 채택 결과 병합은 aggregator만 수행해 완료 순서에 따른 덮어쓰기를 막는다. |
| 7. 종료 보장 | worker retry·재계획·Quality 반복·호출·토큰·시간·graph recursion 상한을 적용하고 `termination_reason`을 남긴다. 예산 소진은 성공과 구별한다. |

## 4. TRL과 보고서 품질 평가

TRL 초안은 1~9단계의 `met/not_met/unknown`, 이유와 근거 ID를 갖는다. Review가 대상 구현·원문·검증 방식을 감사하고 1단계부터 연속 충족한 최고 단계를 확정한다. Report는 이 값과 근거·상위 단계의 공백을 보존한다. **공개 정보 기반 팀 추정이며 공식 TRL 인증이 아니다.** 인접 CXL 제품의 상용 실적을 선정 구현의 TRL로 대입하지 않는다.

현재 Codex 실행의 최신 값은 **RDKV 6·Photonic-CXL 3**, 신뢰도는 모두 **low**다. Photonic-CXL의 에뮬레이션·시뮬레이션을 물리 통합 시제품 검증으로 바꾸지 않는다.

평가 방식은 **3안 Hybrid**다. 코드가 실제 PDF·10쪽 제한·구조·인용·TRL·hash를 검사하고, 별도 AI Judge가 최종 PDF의 주장과 원문을 대조한다. 네 축은 근거성 40%, 중립성·편향 통제·관점 커버리지 각 20%다. 설정된 채택 조건은 축별 4/5 이상·총점 80 이상과 모든 필수 gate 통과이며, 이는 실제 통과 점수가 아니다. 생성과 평가의 호출·프롬프트는 분리하고, 미검사·오류를 pass로 처리하지 않는다.

수업 산출물의 **100점 만점 채점**과 프로젝트의 자동 Quality 점수는 별도 척도다. 프로젝트 채택은 80점 기준만으로 결정하지 않고 축별 기준과 **H1–H7 전체**를 함께 확인한다.

시장 결과는 2개 기술 × 6개 기준의 12항목을 유지한다. 기준은 시장 규모·성장, 사업화, 도입, 생태계 지원, 표준화, 사업 가치다. 자료 부족은 확인한 내용·조건·판단 영향·다음 확인으로 설명하고, 전달 완전성과 사실 확인 수준을 구별한다.

현재 시장 12셀은 **conditional 2개·provisional 10개**로 분석을 제공했다. 조건부 추론과 잠정 평가이며 실제 채택·판매·공식 지원을 12건 확인했다는 의미는 아니다.

### 큰 원문과 모델 입력

원본을 보존하고 모델별 입력을 분리한다. Review는 실제 사용 근거·조건·TRL을 유지한다. Report는 **SourceReader → 출처별 Reducer → Writer**로 작성한다. 원문 전체 window 독해와 출처별 종합을 저장하고, Writer는 모든 출처의 종합 관찰·실제 인용·적용 의미·한계·생략 사유를 읽는다. 웹 독해 41개(활용 38·생략 3)를 모두 보존하며 cache도 identity·원문 인용·전체 coverage를 재검증한다. 작성 입력은 계층적 요약이고 원문·구간별 독해·projection 연결 기록은 별도로 남긴다.

독립 Quality는 **232개 canonical 원문**을 자체 독해하여 실제 원문 span으로 최종 PDF를 감사한다. Report의 종합을 정답으로 사용하거나 등록 원문 hash를 바꾸지 않는다. parser·validator는 원본 handoff를 사용하며 누락·인용 불일치·미검사는 통과시키지 않는다. 상세 입력과 검증 기록은 [실행 검증 기록](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-final-submission/docs/validation-20261007-api-credit.md)을 참고한다.

제출 PDF는 SUMMARY·REFERENCE를 포함해 10쪽 이내로 작성한다. SUMMARY는 핵심 결과·조건을 반쪽 이내로 요약하고 REFERENCE는 실제 인용한 자료를 마지막에 정리한다. 쪽수 코드 검사와 별도로 표·본문·참고문헌 배치는 전체 PDF에서 시각 확인한다.

## 5. RAG·오픈 임베딩과 실행 방법

기존 기술 RAG의 문서 풀은 RDKV 28쪽 + Photonic-CXL 12쪽 = **40쪽**이다. `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`, index version `1.2.0`을 사용한 저장 결과를 재사용한다. Dense·Sparse 검색과 ColBERT/MMR를 사용하며, 이번 통합 검증에서 새 retrieval·embedding 실행이나 HitRate@K·MRR 측정은 하지 않았다.

아래 명령은 저장소 루트에서 실행한다. Python 3.12·uv가 필요하며 PDF에는 XeLaTeX+`kotex` 또는 Tectonic과 NanumMyeongjo Regular/Bold가 필요하다. 기본 `config/pipeline.json`은 saved RAG 결과를 읽는다.

```bash
uv sync --frozen
if [ ! -f .env ]; then cp .env.example .env; fi

# 저장 입력 변환만 확인: --run-rag를 함께 쓰지 않으면 외부 API 호출 없음
uv run --frozen python -m pipeline \
  --output outputs/prepare-only --stop-after prepare

# 기존 Codex CLI의 ChatGPT 로그인 확인
codex login status

# Codex 계정 크레딧으로 새 통합 실행: 종단 검증 전 준비 예시
uv run --frozen python -m pipeline \
  --input config/pipeline.json --env-file .env --as-of 2026-10-07 \
  --model-provider codex_cli_chatgpt --model gpt-6-astra \
  --report-model gpt-6-astra --judge-model gpt-6-astra \
  --max-model-calls 400 \
  --max-tokens 32000000 \
  --max-search-calls 48 \
  --max-extract-calls 96 \
  --max-fetch-calls 96 \
  --max-seconds 10800 \
  --max-judge-calls 160 \
  --output outputs/my-codex-report

# 같은 provider·입력·모델·기준일·예산으로 중단 지점 재개
uv run --frozen python -m pipeline \
  --input config/pipeline.json --env-file .env --as-of 2026-10-07 \
  --model-provider codex_cli_chatgpt --model gpt-6-astra \
  --report-model gpt-6-astra --judge-model gpt-6-astra \
  --max-model-calls 400 \
  --max-tokens 32000000 \
  --max-search-calls 48 \
  --max-extract-calls 96 \
  --max-fetch-calls 96 \
  --max-seconds 10800 \
  --max-judge-calls 160 \
  --output outputs/my-codex-report --resume
```

Codex CLI 0.153.2의 ChatGPT 로그인과 `TAVILY_API_KEY`가 필요하다. 미로그인 상태면 `codex login`을 실행한다. `.env`의 키는 저장소·ZIP에 넣지 않는다. 기본 API provider는 `openai_api`이며 API를 선택할 때만 `OPENAI_API_KEY`도 필요하다. 위 예시는 실제 응답한 `gpt-6-astra`를 고정한다. provider·모델이 바뀌면 기존 checkpoint 대신 새 output을 사용한다.

명령은 유한 예산을 명시하며 재개 시 동일 입력·provider·모델·기준일·예산과 누적 사용량을 유지한다. 기본 모델 160회·Judge 64회보다 큰 모델 400회·Quality 시도별 Judge 160회는 전체 출처 독해와 독립 감사에 필요한 호출 여유다. 실제 호출과 미확인 예약은 `usage.json`에 남긴다. Codex Writer는 요청당 600초, API Report는 300초이며 전체 남은 시간 제한을 함께 적용한다. [전송 정책·시간 제한·이전 실패 기록](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-final-submission/docs/validation-20261007-api-credit.md)

같은 실제 실행의 LangSmith 기록은 다음 helper로 남긴다. 실제 모델·검색 provider를 유지하고 원문·State·프롬프트·응답·runtime payload는 숨긴다.

```bash
uv run --frozen python tools/trace_live_pipeline.py \
  --trace-project SKALA-7-2-Agent \
  --input config/pipeline.json --env-file .env --as-of 2026-10-07 \
  --model-provider codex_cli_chatgpt --model gpt-6-astra \
  --report-model gpt-6-astra --judge-model gpt-6-astra \
  --max-model-calls 400 \
  --max-tokens 32000000 \
  --max-search-calls 48 \
  --max-extract-calls 96 \
  --max-fetch-calls 96 \
  --max-seconds 10800 \
  --max-judge-calls 160 \
  --output outputs/my-codex-trace
```

`.env`에 `LANGSMITH_API_KEY` 또는 `LANGCHAIN_API_KEY`가 필요하다. `live.trace.receipt.json`에서 원격 trace와 실행 ID·새 Report/Quality 호출·최종 파일 hash를 확인한다. 실패하거나 재사용된 결과를 새 live 통과로 표시하지 않는다.

### 마감 전 마지막 Quality 검증

제출 마감은 **00:00 KST**다. 마지막 검증은 **23:48 KST까지** 수행하고 실제 결과로 LangSmith 캡처·ZIP을 정리한다. 기존 실제 Report와 hash가 일치하는 PDF를 재사용하여 Quality만 실행한다. 이전에 검증한 주장 추출 응답 19개는 cache 재사용이며 새 모델 호출로 세지 않는다. 다음 옵션은 완료된 Quality 평가의 상한을 1회로 제한한다.

```bash
uv run --frozen python -m pipeline \
  --input config/pipeline.json --env-file .env --as-of 2026-10-07 \
  --model-provider codex_cli_chatgpt --model gpt-6-astra \
  --report-model gpt-6-astra --judge-model gpt-6-astra \
  --max-model-calls 400 \
  --max-tokens 32000000 \
  --max-search-calls 48 \
  --max-extract-calls 96 \
  --max-fetch-calls 96 \
  --max-seconds 10800 \
  --max-judge-calls 160 \
  --output outputs/codex-submission-20261007 \
  --resume --rerun quality --stop-after quality --max-quality-attempts 1
```

Quality가 끝나지 않으면 미검증 범위와 실제 종료 이유를 첨부하여 제출한다. 자료 패키징 상태 **`pack_ready_materials`**와 내용 평가 승인 **`content_approved`**를 분리하고, 완료된 Judge 결과가 있을 때만 실제 점수를 기록한다.

## 6. 실제 코드와 검증 상태

코드 경로는 저장소 루트 기준이다.

| 책임 | 구현 |
| --- | --- |
| 입력·RAG 경계 | `pipeline/__main__.py`, `pipeline/inputs.py`, `rag/runner.py` |
| State·Planner·동적 Send·취합 | `pipeline/contracts.py`, `pipeline/planner.py`, `pipeline/graph.py` |
| 관점별 scoped 실행 | `pipeline/worker_adapters.py`, `agent/domain/`, `agent/stakeholder/`, `agent/market/` |
| TRL·Review | `pipeline/trl.py`, `pipeline/review_bridge.py`, `agent/review/team_review/` |
| Report·Hybrid Quality | `pipeline/reporting.py`, `pipeline/report_quality.py`, `report/src/report_agent/` |
| artifact·재개·공통 예산 | `pipeline/artifacts.py`, `pipeline/checkpoint.py`, `pipeline/governance.py` |
| Codex 로그인 모델 전송 | `pipeline/codex_provider.py`, `pipeline/tests/test_codex_provider.py` |

| 최신 검증 | 확인 결과와 범위 |
| --- | --- |
| 마지막 로컬 회귀 | `pipeline/tests agent/domain/tests tools/tests report/tests` **371개 통과 / 10.39초**, Pydantic deprecation 경고 2개. 묶음 전송 형식까지의 회귀이며 마지막 Quality 상한 CLI 옵션 추가 전 결과다. live 내용 승인 결과가 아니다. |
| 서지·원문 보존 검사 | 서지 3건의 증빙 7필드를 새 runtime에서 검증·반영했다. 충돌·URL 중복·주원문 hash·정확 좌표를 검사했고 SourceReader 새 호출 0회·기존 원문 cache 162개 파일 불변을 확인했다. |
| 실제 모델·관점 | Codex ChatGPT 로그인·`gpt-6-astra` 사용. 팀 추정 TRL **6·3 / low**, 시장 12셀 **conditional 2·provisional 10**. |
| 최신 실제 PDF | **8쪽**, 전체 페이지 시각 확인에서 레이아웃 문제 없음. 출처 coverage 보완 16건 accepted·remaining 0, 참고문헌 31개와 증빙 기반 서지 3건의 PDF 반영 확인. TRL 6·3 / low와 다음 검증 조건을 보존했다. 독립 Quality 미완료이므로 비최종이다. |
| Quality 기술적 중단 | 실제 Report 2회·주장 추출 성공 19회 이후 원문 대조 1회가 300초 timeout으로 종료했다(exit 2). **점수 없음·H1–H7 미검증**이며 완료나 통과로 표시하지 않는다. |
| 실제 timeout trace | [최신 중단 trace](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/9d261ecc-823f-4d00-a7d4-f7bb13500681?poll=true)의 **14개 정제 노드** 원격 저장 확인(`remote_verified=true`). 실제 호출 22회의 기록이며 원격 저장이 PDF 품질 통과를 뜻하지 않는다. |

현재 output은 `outputs/codex-submission-20261007`, run ID는 `integration-a6c1fd70f71744e4`다. 직전 timeout의 상태는 **`review_required`**다. 482개 주장·원문 구간·사유를 보존하는 묶음 전송 형식을 적용하여 마지막 Quality만 재실행 중이다. 최종 trace는 이번 Quality의 실제 호출과 재사용한 기존 Report/PDF hash를 연결하며 새 Report 호출을 주장하지 않는다. 과거 API 오류·초안·offline 합성 판정은 [실행 검증 기록](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-final-submission/docs/validation-20261007-api-credit.md)에 모았으며 새 결과의 점수로 승계하지 않는다. 구조는 [모델 설명](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-final-submission/docs/model-architecture.md)을 참고한다.

## 7. 팀과 역할별 커밋

| 이름·GitHub | 재구성된 변경 영역 | 커밋 |
| --- | --- | --- |
| 정회륜·superjoung | 시장 범위·호출 관리·팀 문서 | `9bb8450` |
| 김광현·kimgwang-hyeon | 동적 Worker·이해관계자·State·재개·예산 | `d8510ca` |
| 박정빈·jjjjjeong-bin | 도메인 scoped 평가 | `e67a0a4` |
| 백순철·soonchul0408-spec | TRL·Review·종합 전달 | `53b7af3` |
| 이현정·dlkara | 보고서·PDF·출처 감사·Quality | `55e6bf6` |
| 이지석·stellacustodis | RAG job ID·artifact·캐시 검증 | `72d2d80` |

Git author는 사용자가 지정한 역할 담당자이며 코드 구현·수정과 커밋 재구성은 정회륜의 요청으로 Codex가 수행했다. 이 author 표시만으로 각 팀원의 직접 작성·별도 검증을 입증하지 않는다. 원본과 6개 역할 커밋의 완성점은 동일한 Git tree이며 원본 이력은 `archive/skala-pre-role-commits-20261007` 태그에 보존했다. [상세 기여 기록](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-multi-agent-orchestration/docs/role-implementation-history.md)

## 8. 제출 파일

Git 브랜치는 상단 링크로 전달하고, 다음 세 자료를 하나의 ZIP에 정리한다.

| 제출 자료 | 최종 확인 |
| --- | --- |
| README | 필수 설계·재현 명령·팀 역할과 실제 검증 범위 |
| 보고서 PDF | SUMMARY·REFERENCE 포함 10쪽 이내, 최종 revision의 독립 Quality·쪽수·hash·시각 확인 |
| LangSmith 캡처 | 최종 실제 실행과 같은 trace, 한 화면에 담기지 않으면 `tracing-1.png`, `tracing-2.png`로 분할 |

manifest·평가 결과·trace receipt로 Git commit·실행 ID·파일 hash를 연결한다. `.env`·키·가상환경·cache·`.git`·중간 결과는 ZIP에서 제외한다. 현재 8쪽 PDF의 Quality만 재실행 중이며 timeout trace는 새 Quality 실행 trace와 구별한다. 최종 패키지는 실제 검증된 파일·trace·미검증 한계를 포함한다. **패키징 준비와 내용 승인은 별도 상태이며 아직 `pack_ready_materials`·`content_approved` 완료를 확정하지 않았다.**

기준 자료: [Multi-Agent Orchestration 가이드](https://actually-war-1ea.notion.site/Multi-Agent-Orchestration-3d57f4c866938020a992fcc97e942ee6), [KV-cache 기본 가이드](https://actually-war-1ea.notion.site/KV-cache-3ba7f4c866938099b7a8fdaa1831c07e), 배기주 「7. AI Agent 설계 및 구축」. Multi-Agent 가이드는 Safari에서 본문 전체를 확인했고 KV-cache 제출·분량 기준은 기존 전수 검토 기록과 대조했다.
