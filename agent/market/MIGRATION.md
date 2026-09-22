# 시장조사 에이전트 이관 기록

- 이관일: 2026-09-22
- 원본 프로젝트: SKALA_RAG_Pipeline
- 원본 브랜치·커밋: `codex/market-agent` · `e64e78d0be9ac3f33f010a5ce7aaf8210a0c6baa`
- 대상 브랜치: `feat/market-agent`
- 대상 폴더: `market-research-agent/`
- 포함 범위: 시장 에이전트 코드·테스트·입력 샘플, 설계·수정 계획·검증 문서, 검토된 최종 전달 MD.
- 처리: 원본 보존 후 복사. Python 코드·테스트·입력 fixture·최종 전달 MD는 원본과 같은 바이트로 보존. 문서의 실행 경로와 링크를 이 폴더 기준으로 정리하고 설치 파일을 추가.
- 제외 범위: 실제 `.env`와 키, 기존 가상환경, 내부 캐시·수집 원문, 과거 출력, 무관한 실습 노트북. 과거 원문과 내부 기록은 원본 작업공간에 보존.
- 주제 확정 전 가이드 검토 문서는 이전 후보 제안임을 표시. 현재 선정 기술은 RDKV와 Photonic-CXL.

## 전달 파일 무결성

`deliverables/market_handoff.md` SHA-256:

```text
ceceece24d9970520083a30d0a0d04604f3bca1a401e0331c5ac2f1198dd1507
```

## 이관 검증

- 별도 Python 3.11.15 가상환경에 런타임 의존성 39개만 설치하고 의존성 호환성 검사를 통과했습니다.
- 최초 설치에서 `langgraph-checkpoint 4.2.0`과 `langchain-core 1.0.1`의 `Reviver(allowed_objects=...)` 호환 오류를 재현했습니다. 기존 정상 환경의 하위 의존성까지 고정한 `requirements.lock.txt`로 해결했습니다. `requirements.txt`가 해당 제약 파일을 자동 적용합니다.
- 고정 버전 환경에서 unittest 58개와 compileall이 통과했습니다.
- parse 모드로 기술 2개·입력 상한 6/10/5를 확인했습니다.
- fixture 전체 실행으로 12개 평가·단일 전달 MD를 확인하고 `--reuse`도 통과했습니다. 실제 API 호출은 0회입니다.
- 실제 환경의 키 값 포함 여부·키 패턴·심볼릭 링크를 검사했으며 전달 폴더에는 포함하지 않았습니다.
- 내부 캐시와 테스트 중 생성 파일은 복사 대상에서 제외합니다. 기존 실제 API 연결 기록은 `market_agent/LIVE_VALIDATION.md`에 보존하며 이번 이관에서 새 라이브 조사는 수행하지 않았습니다.
