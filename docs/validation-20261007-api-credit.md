# Codex 계정 크레딧 실행 확인 — 2026-10-07

제출 준비 브랜치: `feat/skala-final-submission`. 사용자가 지정한 크레딧은 **Codex 계정의 ChatGPT 로그인 크레딧**이다. OpenAI Platform API 잔액과 구별한다.

| 확인 | 실제 결과 |
| --- | --- |
| 로그인·CLI | Codex CLI **0.153.2**, `Logged in using ChatGPT` 확인. 기존 로그인 사용, API 인증 변환 없음. |
| 실제 구조화 응답 | 명시 모델 **`gpt-6-astra`**에서 Responses와 Chat 각각 성공. 각 input **13,472**·output **15**, 두 호출 합계 **26,974 tokens / unconfirmed 0**. |
| 로컬 계약 검사 | Codex 어댑터 23개·기존 예산 관리 4개, **27개 통과**. 외부 모델 호출 없는 subprocess fixture 검사. |
| 마지막 실제 실행 | `outputs/codex-submission-20261007` / `integration-a6c1fd70f71744e4`. 기존 실제 **8쪽 PDF**를 재사용한 Quality 2 실행이 **300.665초 timeout·exit 2·`judge_timeout`**으로 종료했다. **점수 null·H1–H7 unverified·content_approved=false**. 새 Writer 호출은 없다. |
| 최신 TRL·시장 | Review 팀 추정 **RDKV 6·Photonic-CXL 3 / low**. 공식 인증이 아님. 시장 **12셀 중 conditional 2·provisional 10**은 분석 완전성이며 검증된 상용 도입 건수가 아님. |
| 과거 준비 산출물 | 9쪽 근거 편집 PDF와 실제 offline 제어 trace PNG 2개. 합성 모델·Quality 경계이며 현재 제출 상태는 `review_required`. |

## 마지막 실제 검증과 제출 범위

사용자의 **00:00 KST** 제출 마감에 맞춰 마지막 실제 검증을 **23:29 KST에 종료**했다. 추가 모델 호출은 하지 않는다. 마지막 명령은 `--resume --rerun quality --stop-after quality --max-quality-attempts 1`로 기존 Report/PDF를 재사용하여 Quality만 실행했다. 새로운 전체 파이프라인·새 Writer 실행이 아니다.

| 마지막 Quality 2 실측 | 결과 |
| --- | --- |
| 종료 | **exit 2**, 원문 대조 **300.665초**, `judge_timeout`, route **review_required**. |
| 모델 | `gpt-6-astra`, Codex ChatGPT 로그인 경로. 새 Writer 호출 없음. |
| 주장 추출 | 텍스트 단위 **345/345**, 검증된 atomize 응답 **19개 cache 재사용**. 추출 주장 **482개**. 재사용을 새 모델 호출로 세지 않는다. |
| 독립 평가 범위 | 주장 원문 감사 **0/482**, 최종 PDF block 검사 **0/8**. 시장 12셀의 Quality 평가 미수행. 인용 없는 사실 후보 **10개**는 미판정이며 부정확한 사실 10건으로 확정하지 않는다. |
| 점수·gate | 축별 점수 **{}**, weighted score **null**, **H1–H7 unverified**. compiled·page_limit·structure_citations_trl·rendered_trl은 pass지만 all_checks_completed는 codex_timeout으로 fail. **content_approved=false**. |
| 이번 실제 호출·usage | 원문 대조 **1회 timeout**, 실제 tokens **0**, 미확인 예약 **424,936 tokens**. usage 미확인 때문에 실제 소비가 0이었다고 추정하지 않는다. |
| 전체 누적 usage | **LLM 150·search 31·extract 64·fetch 0**, 실제 **5,901,365 tokens**·미확인 예약 **7,164,291 tokens**, active time **6,093.928초**. Codex CLI usage이며 SDK 계수·금액으로 변환하지 않는다. |
| PDF | **8쪽**, SHA-256 `0680d701795bde4600b917e5351d901e5517587f4cb6e9bea95b851314a51995`. 기존 전체 8쪽 시각 확인 이후 PDF가 바뀌지 않았다. 참고문헌 **31개**, source coverage **remaining 0**, 서지 증빙 3건 반영. |
| Canonical 원문 hash | `16532a927de92d4d4f29947cba37495272bb42ac17e64a90450e04721747899e` — 등록 원문 identity를 유지했다. |
| 마지막 원격 trace | [Quality 2 timeout trace](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/4f8ab728-7e86-4ff8-bf52-64a893c4f93c?poll=true), ID `4f8ab728-7e86-4ff8-bf52-64a893c4f93c`, 예상·저장·확인 **5/5 노드**. 원격 저장은 Quality 통과와 구별한다. |
| 구현 코드 | [d3f4e6342c137cc62d67341ca526c78db7b15f7d](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/d3f4e6342c137cc62d67341ca526c78db7b15f7d) 원격 push 확인. 최종 제출 문서 commit은 패키징 기록으로 연결한다. |

로컬 회귀는 **371 passed / 10.39초**, Pydantic deprecation 경고 2개다. 묶음 전송 형식까지 포함하며 이후 Quality 상한 CLI 옵션의 0값 거부와 실제 manifest 적용은 별도로 확인했다. 전송 형식의 482개 주장·원문 window·사유 보존과 전체 연결·중복/누락 검사는 로컬에서 확인했지만 **실제 원문 대조의 timeout은 지속됐다**. 성능 문제가 해결됐거나 corpus 감사가 완료됐다고 표시하지 않는다.

**content_approved=false**는 확정했다. 자료 패키징 상태 **pack_ready_materials**와 내용 승인은 별도 필드다. 개별 필수 자료 3종은 README·보고서·LangSmith 증빙이며 최종 구성은 8개 파일이다. 각 파일 hash·비밀 제외·캡처 trace 출처를 manifest와 receipt로 연결한다. 자료 준비 상태는 `submission.json`, ZIP SHA·크기·게시와 파일 실측값은 외부 **`submission.receipt.json`**으로 확인한다. 자료 패키지에는 실제 PDF·마지막 Quality trace·미검증 범위를 포함하며 품질 승인과 구별한다.

### LangSmith 동적 실행 증빙과 별도 Quality 보충

[노션 증빙 항목](https://actually-war-1ea.notion.site/Multi-Agent-Orchestration-3d57f4c866938020a992fcc97e942ee6#3d57f4c86693805aae74d10087fee47d)에서 두 장은 긴 trace를 1/2로 나누는 예시다. 고정 필수 장수 대신 **동적 Orchestrator fan-out의 실행 근거**를 제공한다. 기존 Quality-only 2장의 범위로는 Planner·Workers 실행을 보여주지 못하므로 제출 증빙을 다음과 같이 구분한다.

| 캡처 | 실제 trace와 범위 |
| --- | --- |
| `tracing-1.png`, `tracing-2.png` | [이전 실제 역할 실행](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/e6346f48-e8c0-4aaa-9dd6-3b572f9d7eed?poll=true), trace ID **e6346f48-e8c0-4aaa-9dd6-3b572f9d7eed**, remote_verified **40/40**. 같은 trace의 **Planner → 3 Workers → aggregate**를 분할하여 동적 실행을 보여준다. Domain **1회**·Market **6회**·Stakeholders **3회** 실제 모델 호출이 성공했고 후속 **Review·SourceReader에서 실패**했다. 이 trace의 종단 보고서·Quality 성공을 주장하지 않는다. |
| `tracing-quality.png` | [마지막 Quality-only 실행](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/4f8ab728-7e86-4ff8-bf52-64a893c4f93c?poll=true), trace ID **4f8ab728-7e86-4ff8-bf52-64a893c4f93c**, remote_verified **5/5**. 실제 원문 대조 timeout과 기존 Report/PDF lineage를 보여주는 보충 overview다. 새 Writer·Workers 호출은 없다. |

두 trace는 evaluation run **integration-a6c1fd70f71744e4**의 재개 이력에 속하지만 **trace ID가 다른 실행**이다. 하나의 fresh full-pipeline 성공 trace처럼 이어 붙이지 않는다. 원문·State·모델 입력/출력은 privacy 정책으로 비운다. 분할 캡처 1/2는 동일한 이전 역할 trace에서만 구성하고 Quality overview는 다른 이름으로 분리한다. HW 표준화 1셀 선택 재조사의 offline 제어 trace는 별도 학습 기록이며 모델·Report·Quality 경계의 합성 판정을 실제 내용 점수로 적용하지 않는다.

최종 ZIP 구성은 **`README.md`, `report.pdf`, `tracing-1.png`, `tracing-2.png`, `tracing-quality.png`, `quality.json`, `trace.receipt.json`, `submission.json`**의 8개 파일이다. 각 PNG의 trace ID와 역할 실행/Quality 실행 범위, 파일 hash와 크기는 manifest·외부 `submission.receipt.json` 실측으로 연결한다. **content_approved=false·score null**은 유지한다.

## 직전 실제 Report·Quality 이력

서지 증빙 반영 후 실제 재실행에서 **8쪽 PDF**를 생성했다. 출처 coverage 보완 **16건 accepted·remaining 0**, 참고문헌 **31개**와 증빙 기반 서지 **3건**이 PDF에 정상 반영된 것을 확인했다. 전체 8쪽 시각 확인에서 레이아웃 문제를 발견하지 않았다. 공개 근거의 검증 범위와 다음 조건을維持하고 내부 진단 문구를 제거했다. 팀 추정 TRL은 **6·3 / low**다.

독립 Quality는 주장 추출 성공 이후 첫 원문 대조 호출이 **300초 시간 초과**로 중단됐다. 프로세스는 **exit 2**, 종료 이유는 **`judge_timeout`**, route는 **`review_required`**다. weighted score는 `null`이며 **H1–H7 전체가 `unverified`**다. 컴파일·쪽수·구조/인용/TRL의 형식 검사 pass와 최종 독립 품질 승인을 구분한다.

| 직전 중단 실행의 실측 | 결과 |
| --- | --- |
| 호출 | **22회**: Report 성공 2회 + Quality 주장 추출 성공 19회 + 원문 대조 timeout 1회. 해당 구간 search·extract·fetch 0회. |
| 모델 | Report·Judge 모두 **`gpt-6-astra`**, Codex ChatGPT 로그인 경로. |
| 사용량 delta | Codex CLI의 실제 **970,679 tokens**·미확인 예약 **622,344 tokens**. 최종 누적값 또는 API SDK usage가 아니다. |
| PDF SHA-256 | `0680d701795bde4600b917e5351d901e5517587f4cb6e9bea95b851314a51995` — 이번 8쪽 PDF와 연결, 후속 수정 시 다시 확인. |
| 원격 trace | [timeout 실행 trace](https://smith.langchain.com/o/397dd1be-f323-4595-ad35-ee5553ee4bc9/projects/p/726df414-374f-4eac-87ee-7e2915d3126c/r/9d261ecc-823f-4d00-a7d4-f7bb13500681?poll=true), ID `9d261ecc-823f-4d00-a7d4-f7bb13500681`, 예상·저장·확인 **14개 노드**, `remote_verified=true`. 품질 통과 trace가 아니다. |
| 보존 기록 | output의 `corpus-timeout.trace.receipt.json`, `corpus-timeout.codex.calls.jsonl`. 이전 실패와 구분한다. |

직전 timeout 이후 **482개 주장·전체 원문 window·판정 사유를 그대로 보존하는 묶음 전송 형식**을 적용했다. 정규화 후 전체 연결·누락·중복 index 검사와 판정 기준을 유지한다. 마지막 Quality 재실행도 timeout으로 끝났으며 위의 점수 null·미검증 결과를 최종 실제 평가 상태로 기록했다. 자료 패키징 상태만 후속 실측으로 확정한다.

### 직전 초안·중단과 로컬 검사 기록

- 이전 실제 작성 PDF는 **9쪽**, 전체 페이지 시각 확인에서 레이아웃 문제를 발견하지 않았다. 당시에도 출처 coverage 보완 **16건 accepted·remaining 0**, 참고문헌 **31개**와 인용 연결을 확인했다.
- 명확한 원문 서지 메타데이터 **3건 누락**을 정상 입력 재생성 단계에서 보완하기 위해 실행을 **SIGINT로 중단**했다. 따라서 이 초안은 비최종이며 독립 Quality 통과·제출 승인을 주장하지 않는다.
- 중단 구간의 정제된 LangSmith **13개 노드**를 원격에서 확인했다(`remote_verified=true`). 실제 **Report 2회·Quality 주장 추출 10회**를 기록했으나 최종 rubric·gate 통과 trace가 아니다.
- 해당 구간의 추가 사용량은 Codex CLI가 보고한 실제 **754,531 tokens**, 미확인 예약 **121,345 tokens**다. SDK usage 또는 최종 누적값으로 표시하지 않는다. 기존 사용량·미확인 예약은 유지한다.
- 마지막 로컬 회귀는 `pipeline/tests agent/domain/tests tools/tests report/tests` **346 passed / 8.62초**, Pydantic deprecation 경고 2개다. 외부 실행 결과·보고서 내용 승인과 구별한다.
- 수정 후 새 runtime audit에서 서지 3건의 증빙 7필드를 모두 검증·반영했다. `reference_proofs.py`와 기존 metadata JSON의 증빙을 보고서 입력에 연결하고 충돌·URL 중복·주원문 hash·정확 좌표를 검사했다. **SourceReader 새 호출 0회**, 기존 원문 cache **162개 파일 불변**을 확인했으며 TRL·Review는 재사용했다. 이 검사는 새 PDF·독립 Quality 점수를 대신하지 않는다.

위 마지막 실제 실행 결과와 PDF hash·동일 Quality trace·캡처를 제출 자료에 연결했다. 직전 실패 trace나 offline 합성 Quality 점수를 최종 평가 점수로 재사용하지 않는다. 패키징 실측값은 외부 submission receipt로 구분한다.

## 실행 경로와 정책

기본 provider는 `openai_api`로 유지한다. Codex 경로에는 ChatGPT 로그인과 `TAVILY_API_KEY`가 필요하며 `OPENAI_API_KEY`는 불필요하다. 공통 모델을 생략하면 `codex-default`로 CLI `-m`을 생략한다. 아래는 새 output을 사용하는 준비 예시이며 종단 성공 명령으로 기록한 것은 아니다.

```bash
uv run --frozen python -m pipeline \
  --input config/pipeline.json --env-file .env --as-of 2026-10-07 \
  --model-provider codex_cli_chatgpt --model gpt-6-astra \
  --report-model gpt-6-astra --judge-model gpt-6-astra \
  --output outputs/my-codex-report
```

모델마다 새 ephemeral CLI 프로세스와 `forced_login_method="chatgpt"`를 사용한다. 호스트 기능을 끄고 도구 이벤트는 반려하되 모델 도구가 전혀 선언되지 않는다고 보장하지 않는다. `temperature`는 전달하지 않고 출력 토큰 한도는 실행 후 검사한다. 통합 factory의 Codex timeout은 최소 300초다. Report Writer는 초기 실제 작성에 290.2초가 걸려 Codex 경로에만 요청당 600초를 적용했고 API Report의 기본 300초는 유지한다. 모든 호출은 남은 전체 예산 시간 이내로 제한한다. 프롬프트·스키마 byte·CLI 여유분을 먼저 예약하고 시간 초과·사용량 누락은 미확인 예약으로 남긴다. `codex.calls.jsonl`에는 안전한 모델·CLI·사용량·실패 정보만 기록한다.

첫 Codex live 시도는 60·120초 timeout 뒤 중단(exit 130)됐고, 두 번째 시도에서는 Review의 약 309만 자 입력과 SourceReader의 대형 원문 호출이 `turn_incomplete`로 실패했다. `interrupted.trace.receipt.json`과 `failed-large-input.trace.receipt.json`은 두 실패 이력이다. 원격 trace 저장은 Report·Quality의 성공을 뜻하지 않는다.

입력 개선 전 누적 snapshot은 **LLM 43회·search 31회·extract 64회**, 실제 **1,418,427 tokens**·미확인 예약 **5,995,666 tokens**다. 이후 재개는 같은 `usage.json`에 추가 호출을 누적했으며 이 snapshot을 최종 비용·최종 사용량으로 표시하지 않는다. 실패 호출의 미확인 예약을 초기화하지 않는다.

이전 첫 Codex Writer에서는 7쪽 PDF가 생성됐고, coverage 보완의 10pt 규격 변경을 반려하여 초안을 보존했다. 직전 9쪽 초안과 최신 8쪽 PDF는 위 기록에서 구분한다. 이전 회귀 319개는 당시 기존 254개·새 timeout 검사 2개·Report 63개였으며 focused 검사 51개도 앞선 별도 기록이다. 최신 회귀는 위의 371개 결과로 구분한다. 최종 trace 캡처와 자료 패키징 범위는 위 실측 기록을 사용한다.

실제 trace 준비는 [live helper](../tools/trace_live_pipeline.py)의 `--trace-project`와 같은 pipeline 옵션을 사용한다. `LANGSMITH_API_KEY` 또는 `LANGCHAIN_API_KEY`도 필요하다. 원문·State·응답·runtime payload를 숨기고 `live.trace.receipt.json`으로 원격 trace와 실제 Report·Quality·hash를 대조한다.

## 원문 보존과 입력 크기 조정

모델의 전송 크기를 줄이되 원본 자료·평가 조건·검증 기준을 유지했다.

| 단계 | 현재 구현과 확인 범위 |
| --- | --- |
| Review 생성 | 수집 웹 원문 전체를 source ID·URL·기술 귀속·SHA-256·길이 manifest로 대체한다. 실제 used evidence·평가·조건·반대근거·미확인·TRL은 유지하고 응답의 연결 검증은 original payload로 수행한다. 목록만으로 사실을 입증하지 않는다. |
| Review 의미 검사 | 동일 평가와 근거를 공유 registry에 한 번씩 전달하고 item별 ID로 범위를 연결한다. 원래 conservative 검사와 결과 validator의 입력은 바꾸지 않는다. 누락·충돌 ID를 통과시키지 않는다. 외부 호출 없이 전체 Review **127개 테스트 통과**. |
| SourceReader → 출처별 Reducer | 긴 웹 원문은 최대 **60,000자**의 연속 window로 마지막 문자까지 읽는다. Reducer가 출처별 모든 window의 관찰·운영/시장 해석·한계·생략 사유를 종합한다. 원문·window hash·전체 범위와 실제 인용문을 검사하고 전체 구간 독해와 출처별 종합을 보존한다. 실패한 window를 읽은 것으로 표시하지 않는다. |
| Report Writer | 원본 `report.input.md`와 작성용 `report.model-input.md`를 분리한다. Writer에는 source manifest와 모든 출처의 종합 관찰·실제 인용·적용 의미·한계·생략 사유를 전달한다. `window_readings` 전문은 보존 artifact의 hash·개수·coverage manifest로 연결하며 Writer의 읽기 범위는 출처별 종합이다. `report.prompt-projection.json`에 양쪽 hash·길이를 기록하고 parser·validator는 원본 handoff를 사용한다. |
| 독립 Quality | canonical 근거 **232개 레코드 / 원문 2,688,569자**의 전체 목록·등록 identity를 유지한다. 긴 원문은 최대 **80,000자** window·**800자** 경계 중첩으로 독립 독해한 뒤 실제 원문에서 선택한 연속 span과 목록을 주장 감사·최종 rubric에 전달한다. 짧은 원문은 전체를 전달한다. Report의 독해를 정답으로 사용하지 않는다. |

`quality.evidence-N.json`은 전체 원문, `quality.corpus-coverage-N.json`은 독립 독해의 전체 범위·선택 원문 span을 기록한다. 작성용 projection hash는 추가 추적 정보이며 등록 문서 hash를 새로 붙여 불일치를 덮지 않는다. 최종 Judge 입력의 기본 1,000,000자 한도·전체 PDF 줄과 시장 12셀·기술 귀속·원문 인용·미검사 차단은 유지한다. 마지막 Report·Quality 결과는 위에 확정했으며 자료 패키징의 완료 상태만 후속 실측으로 확정한다.

작성은 계층적 요약 방식이다. SourceReader의 전체 window 독해·Reducer 종합·원문은 `source-readings/`, `report.source-analysis.json`, `report.input.md`에 보존한다. Writer는 출처별 종합을 사용하고 독립 Quality는 **232개 canonical 원문**을 자체 독해한다. 종합 과정에서 선택한 내용의 타당성은 이 독립 원문 감사로 확인하며 최종 통과 판정은 아직 없다.

현재 웹 출처 독해 **41개**는 활용 **38개**·생략 사유가 있는 **3개** 모두 보존한다. 출처·모델·독해 지시문으로 만든 cache key가 같은 이전 revision 결과도 재사용 전에 여섯 identity 필드·실제 인용·전체 window coverage를 다시 검사한다. coverage 보완의 중복 종합을 ID 참조로 바꾸는 경우에도 원본 독해·canonical 인용 키·작성 입력의 종합이 정확히 일치하는지 확인한다. 출처 내용을 바꾸거나 등록 hash를 새로 붙이지 않는다.

수업 산출물은 **100점 만점**으로 채점한다. 프로젝트의 자동 Hybrid Quality는 별도 척도로 근거성 40%·나머지 세 축 각 20%, **축별 4/5 이상·80점 이상·모든 H1–H7 통과**를 함께 요구한다. 과거 84점과 실패 gate를 새 PDF의 점수로 승계하지 않는다.

## 과거 API 이력과 checkpoint 경계

등록 API 키의 **이전 목록 조회에서 127개**를 확인했지만 생성 성공은 아니었다. **20:25 KST** 최소 `gpt-4.1-mini` 호출은 **429 `credit_balance_exhausted`**였다. 다른 실습 환경의 중복되지 않는 기존 키는 한 번 최소 호출해 **404 `model_not_found`**를 받았고, 같은 키를 쓰는 환경의 중복 호출은 생략했다. Report 8의 당시 404는 [이전 기록](validation-20261007-quality-fix.md)에 보존한다.

과거 `outputs/ow-validation-20261007`은 `report_repair`·피드백 16개·출처 독해 22개를 보존한다. 같은 API 설정에서의 재사용 가능 기록이며, 새 provider·공통 모델로 그 checkpoint를 재개하거나 이전 Judge 점수를 승계하지 않는다. saved 원본 조사 자료는 새 실행의 입력으로 사용할 수 있다. 마지막 실제 PDF·미검증 gate·쪽수·시각 확인·동일 Quality trace를 위 기록에 연결했으며 자료 준비와 내용 승인 상태를 구분한다. ZIP hash는 외부 submission receipt로 확인한다. 키 값·일부·hash·이메일·결제 정보·로컬 환경 파일 절대경로는 기록하지 않는다.
