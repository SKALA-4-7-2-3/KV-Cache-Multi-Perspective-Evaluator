# 팀 역할과 Git 기여 기록

## 확인 기준

2026-10-07 사용자가 제공한 사진의 왼쪽 위부터 행 순서로 이름과 GitHub 계정을 연결했습니다. 담당 범위는 기존 README의 Contributors와 실제 변경 파일·커밋을 대조했습니다. 아래 기록의 기준점은 `codex/report-quality-and-model-visualization`의 [`dcb25a0`](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/dcb25a0)입니다.

이 문서는 이미 기록된 기여를 설명합니다. 최근 통합 수정은 정회륜의 기존 계정으로 기록되어 있으며, 다른 팀원에게 작성자를 이전하거나 새 공동 작성자를 추가하지 않았습니다. 문서 작성은 정회륜의 요청으로 Codex가 수행했습니다.

위 설명은 원본 `dcb25a0`·`8f5b8fa` 이력의 확인 당시 상태입니다. 이후 사용자 요청으로 새 `codex/role-implementation-history` 브랜치에서 같은 코드 변경을 6개의 역할 담당자 커밋으로 재구성했습니다. 기존 이력은 보존했고, 새 author 표시는 담당자 배정이며 Codex 구현·재구성 사실을 함께 명시했습니다. [새 역할별 코드 커밋과 검증](role-implementation-history.md)을 참고하세요.

## 팀원별 역할과 대표 커밋

| 이름 | GitHub 계정 | 기존 Git 작성자 | 확인된 담당 범위 | 현재 코드 위치 | 대표 커밋 |
| --- | --- | --- | --- | --- | --- |
| 정회륜 | [superjoung](https://github.com/superjoung) | `superjoung` | 시장 평가 에이전트, JSON 전달 형식, 이후 TRL·동적 오케스트레이션·보고서 품질 검증 | `agent/market/`, `pipeline/`, `report/` | [시장 에이전트 이관 · 23ea789](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/23ea789), [JSON 출력 · 93281d1](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/93281d1), [TRL 연결 · 5117046](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/5117046), [보고서 수정 범위·TRL 보존 · 66adb09](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/66adb09) |
| 김광현 | [kimgwang-hyeon](https://github.com/kimgwang-hyeon) | `9wan9hyeon` | 이해관계자 평가 에이전트, 전체 에이전트 통합, 출처·보고서 연결 | `agent/stakeholder/`, `pipeline/`, `report/` | [이해관계자 에이전트 · 003ccac](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/003ccac), [저장 조사·평가·PDF 연결 · 0619103](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/0619103), [6개 에이전트 구조 문서화 · 966fea0](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/966fea0) |
| 박정빈 | [jjjjjeong-bin](https://github.com/jjjjjeong-bin) | `jjjjjeong-bin` | 도메인 평가 에이전트, 프로젝트 구조 정리, README·아키텍처 그림 | `agent/domain/`, `README.md`, `docs/images/architecture.svg` | [도메인 에이전트 · a2da7a6](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/a2da7a6), [폴더 구조 정리 · 70f10a5](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/70f10a5), [아키텍처 그림 · 2beaab4](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/2beaab4) |
| 백순철 | [soonchul0408-spec](https://github.com/soonchul0408-spec) | `백순철` | 평가 종합·Review 에이전트, 근거 맥락 보존과 보고서 전달 계약 | `agent/review/` | [Review·종합 에이전트 · 810e1c7](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/810e1c7), [보고서 전달 요건 · 71ed3b6](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/71ed3b6) |
| 이현정 | [dlkara](https://github.com/dlkara) | `이현정` | 보고서 생성 에이전트, LaTeX·PDF 생성·컴파일·검증 | `report/` | [PDF 보고서 에이전트 · 0ea740f](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/0ea740f), [보고서 ignore 범위 · ca905bf](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/ca905bf) |
| 이지석 | [stellacustodis](https://github.com/stellacustodis) | `stellacustodis` | 기술 조사·근거 기반 RAG, 두 논문 분석 결과 | `rag/` | [기술 조사 에이전트 · 56ad0b7](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/56ad0b7), [두 논문 검증 결과 · 3c19ec6](https://github.com/SKALA-4-7-2-3/KV-Cache-Multi-Perspective-Evaluator/commit/3c19ec6) |

기존 커밋 당시의 경로와 현재 경로는 프로젝트 통합·폴더 재구성으로 다를 수 있습니다. 대표 커밋의 변경 파일에서 당시 구현을 확인할 수 있습니다. 계정과 실명의 대응은 사용자가 제공했으며, 이메일은 저장소의 기존 작성자 메타데이터를 사용했습니다. 계정의 비공개 이메일 설정은 확인하지 않았습니다.

## 이력 확인 방법

루트의 [`.mailmap`](../.mailmap)은 기존 이메일에 실명 표시를 연결합니다. 이메일·커밋 객체·해시는 유지됩니다. Git의 이름 매핑 기능 설명은 [공식 문서](https://git-scm.com/docs/gitmailmap)를 참고하세요.

```bash
# 실명으로 전체 작성자 집계
git shortlog -sn HEAD

# 원래 작성자(%an)와 실명 표시(%aN)를 함께 확인
git log --format='%h | %an -> %aN | %s'

# 담당 코드의 변경 이력
git log -- agent/market/
git log -- agent/stakeholder/
git log -- agent/domain/
git log -- agent/review/
git log -- report/
git log -- rag/
```

이 기준점에 도달 가능한 이력에는 6명의 커밋이 모두 있습니다. `git shortlog`의 전체 이력 집계에는 병합 커밋도 포함되므로, 사진의 GitHub Contributors 수치와 같은 집계로 해석하지 않습니다.

추가 연구 브랜치의 `58909db`, `9e427c5`, `5627c72`는 기준점의 조상 커밋이 아닙니다. 일부 추가 연구 산출물은 김광현의 `966fea0`으로 통합되었습니다. 현재 브랜치에 그 세 커밋 자체가 병합된 것으로 기록하지 않습니다.

## 이후 커밋 운영

1. 각자 작업 브랜치에서 실제 담당 수정·테스트·문서화를 수행합니다.
2. 본인 PC의 저장소에서 Git 이름과 GitHub 연결 이메일을 설정합니다.
3. 변경 파일과 해당 범위의 검증 결과를 확인한 뒤 커밋·푸시합니다.
4. 공동 작성은 실제 참여자가 확인된 작업에 `Co-authored-by`를 사용합니다. [GitHub 안내](https://docs.github.com/en/pull-requests/how-tos/commit-changes/creating-a-commit-with-multiple-authors)
5. PR 리뷰로 다른 팀원의 검토 내용을 남깁니다. 커밋별 기록을 보존하려면 저장소 정책이 허용하는 Merge commit 방식을 사용합니다.

GitHub Contributors는 기본 브랜치에 포함된 커밋을 기준으로 하며 병합·빈 커밋은 제외합니다. 작업 브랜치 푸시와 문서 추가만으로 사진의 집계 수치가 즉시 늘어나는 것은 아닙니다. 표시 이름 매핑도 기여 수를 새로 만들지 않습니다. [GitHub 집계 기준](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-a-projects-contributors)

## 현재 실행 상태와의 구분

이 기여 기록 정리는 보고서 실행 상태를 변경하지 않습니다. 최신 검증에서는 선택한 회귀 테스트 470개가 통과했지만, Report 8은 OpenAI 모델 접근 오류로 PDF 생성·최종 Quality 검증을 완료하지 못했습니다. 자세한 내용은 [최신 실행 검증 기록](validation-20261007-quality-fix.md)을 참고하세요.
