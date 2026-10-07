# KV Cache 기술 평가 — Multi-Agent Orchestration 제출 안내

논문 분석 JSON과 자연어 요청을 받아 **RDKV(SW)**와 **Photonic-CXL(HW)**를 TRL·시장·이해관계자·도메인 관점에서 비교한다. 대상 시나리오는 클라우드 데이터센터의 장문맥 문서 QA다. 예산·SLO·장비 조건이 입력되지 않았으면 임의로 채우지 않는다.

- [제출 브랜치: feat/skala-multi-agent-orchestration](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/tree/feat/skala-multi-agent-orchestration)
- [역할별 커밋과 이후 문서 변경](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commits/feat/skala-multi-agent-orchestration)
- 기준 main 커밋: `a633cc1`. 기존 RAG·관점 에이전트·Review·보고서 생성기를 재사용하고, 이번 과제에서는 **동적 계획·선택적 재조사·State/재개·TRL 전달·보고서 이후 품질 루프**를 추가·보완했다.

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

[실제 LangSmith 제어 테스트](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/47df0864-e944-4660-834c-d64a9c8f6392?poll=true)에서 최초 Worker 3개 → 보고서 수정 → HW 시장 표준화 1셀 재조사 Worker 1개 → 취합·종료를 확인했다. `tracing-1.png`, `tracing-2.png`는 같은 trace를 순서대로 캡처한다. 실제 LangGraph 제어 흐름을 실행했으나 모델·보고서·Quality 경계는 합성 fixture이며 LLM·검색 호출은 0회다. **합성 Quality의 passed는 실제 PDF 내용 승인이나 AI 점수가 아니다.**

## 3. State의 일곱 설계 항목

| 항목 | 적용과 이유 |
| --- | --- |
| 1. Control / payload 분리 | `phase`, `tasks`, `pending_cells`, outcome·반복 카운터는 State에, 큰 원문·결과·PDF는 외부 파일과 `*_ref`에 두어 전송·저장 중복을 줄인다. |
| 2. 관측성 위치 | 결정에 필요한 상태와 계획 이유만 State에 둔다. 상세 흐름은 `events.jsonl`, API 사용량은 `usage.json`, LangSmith에는 실행 metadata를 연결한다. |
| 3. 큰 데이터·체크포인트 비용 | `ArtifactStore`의 상대 경로·SHA-256 참조와 SQLite checkpoint를 사용한다. 현재 saver에는 자동 pruning이 없으므로 무제한 보관을 전제하지 않는다. |
| 4. 상관 ID | RAG 이전에 `run_id`를 발급하고 `thread_id`, `task_id`, `call_id`, artifact hash와 연결한다. LangSmith metadata의 `evaluation_run_id`로 같은 실행을 추적한다. |
| 5. 복구·오류·retry | `plan_revision`, `task_attempt`, 오류·retryable 정보를 기록한다. 완료 결과는 hash 검증 후 재사용하고 실패·응답 미확인 사용량을 초기화하지 않는다. |
| 6. 병렬 reducer·단일 작성자 | outcome reducer는 같은 키의 동일 결과를 중복 반영하지 않고 충돌을 거부한다. 채택 결과 병합은 aggregator만 수행해 완료 순서에 따른 덮어쓰기를 막는다. |
| 7. 종료 보장 | worker retry·재계획·Quality 반복·호출·토큰·시간·graph recursion 상한을 적용하고 `termination_reason`을 남긴다. 예산 소진은 성공과 구별한다. |

## 4. TRL과 보고서 품질 평가

TRL 초안은 1~9단계의 `met/not_met/unknown`, 이유와 근거 ID를 갖는다. Review가 대상 구현·원문·검증 방식을 감사하고 1단계부터 연속 충족한 최고 단계를 확정한다. Report는 이 값과 근거·상위 단계의 공백을 보존한다. **공개 정보 기반 팀 추정이며 공식 TRL 인증이 아니다.** 인접 CXL 제품의 상용 실적을 선정 구현의 TRL로 대입하지 않는다.

평가 방식은 **3안 Hybrid**다. 코드가 실제 PDF·10쪽 제한·구조·인용·TRL·hash를 검사하고, 별도 AI Judge가 최종 PDF의 주장과 원문을 대조한다. 네 축은 근거성 40%, 중립성·편향 통제·관점 커버리지 각 20%다. 설정된 채택 조건은 축별 4/5 이상·총점 80 이상과 모든 필수 gate 통과이며, 이는 실제 통과 점수가 아니다. 생성과 평가의 호출·프롬프트는 분리하고, 미검사·오류를 pass로 처리하지 않는다.

시장 결과는 2개 기술 × 6개 기준의 12항목을 유지한다. 기준은 시장 규모·성장, 사업화, 도입, 생태계 지원, 표준화, 사업 가치다. 자료 부족은 확인한 내용·조건·판단 영향·다음 확인으로 설명하고, 전달 완전성과 사실 확인 수준을 구별한다.

## 5. RAG·오픈 임베딩과 실행 방법

기존 기술 RAG의 문서 풀은 RDKV 28쪽 + Photonic-CXL 12쪽 = **40쪽**이다. `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`, index version `1.2.0`을 사용한 저장 결과를 재사용한다. Dense·Sparse 검색과 ColBERT/MMR를 사용하며, 이번 통합 검증에서 새 retrieval·embedding 실행이나 HitRate@K·MRR 측정은 하지 않았다.

아래 명령은 저장소 루트에서 실행한다. Python 3.12·uv가 필요하며 PDF에는 XeLaTeX+`kotex` 또는 Tectonic과 NanumMyeongjo Regular/Bold가 필요하다. 기본 `config/pipeline.json`은 saved RAG 결과를 읽는다.

```bash
uv sync --frozen
if [ ! -f .env ]; then cp .env.example .env; fi

# 저장 입력 변환만 확인: --run-rag를 함께 쓰지 않으면 외부 API 호출 없음
uv run --frozen python -m pipeline \
  --output outputs/prepare-only --stop-after prepare

# 모델·검색 API가 사용 가능한 환경에서 통합 실행
uv run --frozen python -m pipeline \
  --input config/pipeline.json --as-of 2026-10-07 \
  --output outputs/my-ow-report

# 같은 입력·공통 모델·기준일·예산으로 중단 지점 재개
uv run --frozen python -m pipeline \
  --as-of 2026-10-07 --output outputs/my-ow-report --resume
```

로컬 `.env`에는 `OPENAI_API_KEY`, `TAVILY_API_KEY`를 설정한다. 별도 파일은 `--env-file .env`처럼 지정할 수 있다. 키 값은 저장소·ZIP에 넣지 않는다. 기본 모델 `gpt-4.1-mini`는 코드 기본값이며 현재 사용자 키로 사용 가능하다고 확인된 모델이 아니다. 실제 생성 모델을 바꾸면 해당 실행 identity와 캐시 무효화 조건을 먼저 확인한다.

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

| 검증 | 확인 결과와 범위 |
| --- | --- |
| 역할 재구성 후 회귀 | 오프라인 **470 passed / 0 failed / 14.14초**. pipeline·domain·market·선택 Review·report 테스트이며 전체 저장소 또는 live 검증 결과가 아니다. |
| 실제 Report 7 | 6쪽 PDF, Review 팀 추정 RDKV 6·Photonic-CXL 4. Quality 84점에도 필수 gate 미통과로 `failed_quality`; 수동 원문 대조에서 시장 기간·기술 귀속 오류가 남았다. |
| 실제 Report 8 | OpenAI `model_not_found` 접근 오류로 새 TeX·PDF와 Quality 결과가 생성되지 않았다. |
| 실제 LangSmith PNG | 실제 그래프 제어 테스트의 33개 run 저장 확인. 최초 Worker 3개·선택 재조사 1개·Report/Quality 각 3회. 모델과 판정은 합성 fixture다. |
| 이번 제출 PDF | 기존 기록·코드·원문 근거를 Codex가 근거를 편집하여 정리한 보고서다. pipeline 자동 생성·독립 Quality 통과 결과로 표시하지 않는다. |

실제 후속 run은 `integration-fcb4b36916fd49e6`이다. Report 7의 품질 결과·Report 8의 오류·이번 근거 편집 보고서는 각각 구별한다. 자세한 범위는 [검증 기록](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-multi-agent-orchestration/docs/validation-20261007-quality-fix.md), 구조는 [모델 설명](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/blob/feat/skala-multi-agent-orchestration/docs/model-architecture.md)을 참고한다.

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

## 8. 제출 파일과 남은 증빙

| 제출 항목 | 파일·링크와 상태 |
| --- | --- |
| Git | 상단 최종 브랜치 링크와 `submission.json`의 commit |
| 최종 보고서 | ZIP의 `report.pdf` — 이번 근거 편집 정리본 9쪽, 쪽수·시각 확인 결과는 manifest/receipt에 기록 |
| 실제 LangSmith 캡처 | `tracing-1.png`, `tracing-2.png` — 같은 실제 offline 제어 trace를 순서대로 캡처 |
| 패키징 manifest | ZIP의 `submission.json` — 파일 hash·Git commit·기존 run·편집 보고서 provenance·남은 확인 |

ZIP에는 README·보고서·실제 LangSmith PNG 2개·manifest·평가 상태·제어 테스트 receipt를 담는다. `.env`·API 키·가상환경·cache·`.git`·중간 결과를 포함하지 않는다. ZIP 밖 receipt로 hash·PDF 시각 확인·trace 확인을 남긴다. **파일 3종은 준비했으나 live AI 보고서·독립 Judge 검증은 모델 접근 오류로 미완료다. 제출 상태는 `review_required`로 기록한다.**

기준 자료: [Multi-Agent Orchestration 가이드](https://actually-war-1ea.notion.site/Multi-Agent-Orchestration-3d57f4c866938020a992fcc97e942ee6), [KV-cache 기본 가이드](https://actually-war-1ea.notion.site/KV-cache-3ba7f4c866938099b7a8fdaa1831c07e), 배기주 「7. AI Agent 설계 및 구축」. 이번 작업에서는 Multi-Agent 가이드 본문 전체를 Safari로 확인했다. KV-cache는 기존 전수 검토 기록과 Safari에 표시된 제출·분량 기준을 대조했다.

### LangSmith 제어 테스트 재현

```bash
uv run --frozen python tools/trace_orchestration_smoke.py \
  --env-file .env --project SKALA-7-2-Agent \
  --output outputs/control-smoke
```

`.env`에 `LANGCHAIN_API_KEY` 또는 `LANGSMITH_API_KEY`를 넣는다. helper는 공식 SDK로 노드 이름·연결·시간·offline 태그만 전송하며 원문·State 입력·결과·runtime·오류 본문은 비운다. 서버가 추가한 숫자 run 깊이와 모든 하위 run ID를 확인한다. `trace.receipt.json`에 실제 trace와 합성 평가 여부를 기록한다. 합성 Report의 테스트용 PDF bytes는 제출하지 않는다.
