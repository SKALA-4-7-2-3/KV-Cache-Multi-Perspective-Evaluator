# 2026-10-07 실제 실행 검증

## 판정

**코드 실행·PDF 생성·TRL 출력은 확인했으나, 현재 PDF의 내용 품질은 제출 기준 미통과다.** 자동 점수만으로 보고서를 채택하지 않았다. 상세 수치와 해시는 [JSON receipt](validation-20261007.json)에 기록했다.

| 확인 항목 | 실제 결과 |
| --- | --- |
| 작업 브랜치 | `codex/pdf-guided-orchestration`; main에 병합하지 않음 |
| 검증한 구현 | `6c3d814` — 구조화된 주장·감사 정보까지 Report 피드백에 전달 |
| 강의 참고 | 171쪽 PDF의 OW, State scope/ownership, reducer/join, checkpoint, 실패·예산 관리, Generator–Evaluator 분리, 원문 보존을 적용; [대응표](orchestration.md#강의-근거와-선택-이유) |
| 입력 | 저장된 두 논문 dossier·comparison·evidence_registry JSON; 새 retrieval/embedding은 미실행 |
| 모델 | 후속 기본 `gpt-4.1-mini`, Report와 별도 Judge 호출은 `gpt-4.1` |
| 실행 | `integration-fcb4b36916fd49e6`, 기준일 `2026-10-07`, 캐시·체크포인트를 사용한 재개 실행 |
| 보고서 | revision 7, **6쪽**, 생성 응답 1회·컴파일 1회, 참고문헌 11개 |
| TRL | RDKV **6**, Photonic-CXL **4**; 공개 정보 기반 팀 추정이며 공식 인증 아님 |
| 시각 확인 | 6쪽 전체 렌더링 검사; 한글·인용·참고문헌에 잘림·겹침 없음 |
| 선택 회귀 테스트 | **454 passed / 0 failed / 12.19초**; 정확한 명령·범위는 JSON에 기록 |
| 최종 자동 Quality | **84점**, 네 축 4·5·4·4; H1/H2/H7·미해결 major gate 실패 |
| 평가 완료 범위 | PDF 6/6 block, 216/216 줄, 169/169 주장, 시장성 12/12 셀 |
| 자동 판정 집계 | supported 141, contradicted 5, unsupported 20, uncertain 3; 실제 선택 인용이 없는 사실 12개 |
| 최종 제어 상태 | `failed_quality`, `quality_attempt_limit` |

`contradicted` 5개는 아래의 수동 Judge 검토에서 판정 enum과 이유의 불일치가 확인됐다. 집계를 실제 사실 오류 5개로 해석하지 않는다.

## 남은 실제 보고서 문제

1. **시장 전망 기간 오류**: pooling 시장 CAGR을 `2025–2034`로 표시했다. 등록 원문의 전망 구간은 **2026–2034**이며, 2025년은 기준 금액의 연도다.
2. **기술 귀속 오류**: 일반 CXL의 지역·파일럿 도입과 CXL 2/3/4 생태계 호환성을 선정 Photonic-CXL 구현의 실적으로 확대하는 문장이 남았다. Marvell PF-NIC 자료의 CXL 3.1·PCIe Gen6와 일반 CXL 생태계 자료를 구분해야 한다.
3. **TRL 내부 진단 노출**: controller의 근거 연결 진단문이 `next_reason`에 전달되고 prompt·validator가 전체 원문 보존을 요구한다. 피드백에서 삭제를 요구해도 작성 계약과 충돌하여 다시 출력된다. 원래 Review reason/checks는 보존하되 공개 미확인 설명과 내부 진단을 구분할 필요가 있다. 검증되지 않은 초안 사유를 원문 사실로 승격해서는 안 된다.
4. 자료 부재는 검토한 출처의 범위 안에서 설명해야 하며, 보편적인 제품·도입 부재로 단정하지 않아야 한다.

수동 원문 검토는 `outputs/ow-validation-20261007/manual-source-review-revision-7.json`에 별도 기록했다. 자동 판정·원문·과거 보고서·사용량은 수정하지 않았다.

## 평가기에서 확인한 문제

- RDKV의 `추정 TRL: 6`은 Review가 확정한 팀 평가인데, Judge는 논문이 TRL 단계를 논의하지 않아 직접 지원되지 않는다는 이유로 uncertain을 반환했다. TRL 값의 권위는 Review와 보존 검사이며, 단계 근거와 환경 설명은 원문 감사 대상이다. 이 두 검증을 구분해야 한다.
- 자동 contradicted 5건은 모두 참고문헌 행이다. 해당 Judge의 설명은 오히려 제목·저자·날짜 등이 원문과 일치해 supported라고 말한다. enum과 이유가 충돌한다. registered source identity 기반의 참고문헌 메타데이터 검증과 판정 계약 보정이 필요하다. 이유만 보고 판정을 supported로 임의 변환하지 않았다.

이 문제들이 있어 자동 판정은 단독 정답으로 취급하지 않았다. 위의 시장 기간·기술 귀속 오류는 이 평가기 문제와 별개로 원문에서 확인된 보고서 결함이다.

## 반복·재개의 provenance

완료 내용 평가 횟수는 Quality3=1, Quality4=2, Quality5=2(시간 초과), Quality6=3이다. 기본 자동 상한 3회 도달 후, 피드백 정보 손실 수정의 효과를 확인하기 위해 **한 번의 명시적 개발 보정으로 Report7/Quality7**을 실행했다. 이전 횟수와 사용량을 그대로 보존하여 최종 controller의 완료 횟수는 4다. 이를 정상 자동 3회 루프의 통과 실적으로 표시하지 않는다.

구조화된 피드백 24개에는 원래 claim·검증 audit·보고서 hash를 보존했다. 이전의 실제 성공 source-reading 캐시 22개는 identity·원문 quote 계약으로 재검증해 사용했다. 범용 사유만 전달하던 이전 문제는 수정됐지만, 이 수정만으로 모든 내용 오류가 해결되지는 않았다.

후속 API 사용량은 **모델 시도 565회·검색 49회·추출 116회**, provider 기록 토큰 29,857,761, 미확인 예약 토큰 2,868,746, 누적 active 시간 8,720.26초다. 개발 중 실패·수정·재개·여러 revision을 모두 포함한다. 새 실행의 비용·시간 성적이나 청구 금액이 아니다. 한도 증액 6회와 그 시점의 사용량은 JSON에 남겼다.

## 검증 한계

- 기존 stakeholder 테스트 8개 실패는 baseline `5117046`에서도 재현됐다. 454개 선택 테스트 통과를 전체 저장소 테스트 무결함으로 확대하지 않는다.
- LangSmith 코드는 유지했으나 키가 없어 실제 동적 trace·제출 PNG는 미확보다.
- 저장 RAG를 사용했으므로 새로운 retrieval/embedding과 Hit Rate@K·MRR은 측정하지 않았다.
- Judge calibration은 수행하지 않았다. TRL 숫자 보존과 PDF 컴파일 통과는 내용 정확도 인증이 아니다.
- 원문 전체는 등록된 논문 근거·수집 웹 excerpt 범위다. 모든 원본 PDF byte와 웹사이트 전체를 수집했다는 뜻이 아니다.
- 실행 출력·키는 새로 커밋하지 않는다. 현재 로컬 PDF 경로는 JSON receipt의 `report.pdf`에서 확인한다.
