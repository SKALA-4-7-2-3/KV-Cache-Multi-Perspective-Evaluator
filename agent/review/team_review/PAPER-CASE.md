# 논문 기반 모의 상위 평가 → 검증·새 의견 → MD

이 실험은 실제 논문에서 보존한 근거 13개를 사용한다.
technical/market/stakeholders/domain 입력 8칸은 어시스턴트가 상위 Agent 결과를 가정해 작성한 fixture다.
실제 상위 Agent/RAG/고객 인터뷰/논문 성능 재현 결과가 아니다.

## 파일

- [실행 입력 MD](examples/paper.input.md)
- [최신 전달 출력 MD](../outputs/review.output.md)
- [보고서 담당자 연결 안내](REPORT-HANDOFF.md)
- [최종 출력 계약](OUTPUT-CONTRACT.md)
- 과거 로컬 실행 기록은 포함하지 않는다. 원문 재대조는 아래 선택 옵션을 사용한다.

## 재생

```bash
python -m team_review.examples.paper_case --output-dir outputs/check-only
python -m team_review.examples.paper_case --synthesize --env-file .env --output-dir outputs
```

첫 명령은 API 없이 원래 평가를 검수한다. 두 번째는 gpt-4.1-mini로 새 종합 의견을 생성한다.
모델/키 접근 가능 여부에 따라 실패할 수 있으며, 실패를 성공으로 바꾸지 않는다.
기본 경로는 PDF를 다시 읽지 않는다. 원문 재대조가 필요할 때만 --verify-sources를 사용한다.
추가 출력 JSON/대형 중복 비교표를 매번 생성하지 않는다. 원문 PDF와 과거 로컬 출력은 이 브랜치에 포함하지 않는다.

## 출처와 모의 데이터 구분

- 논문 버전·URL·쪽수·해시·원문 발췌는 앞선 원문 대조에서 확보했다.
- config.demo=true는 상위 Agent 평가가 모의 입력이라는 뜻이다.
- evidence.synthetic=false는 발췌가 합성 문장이 아닌 실제 원문이라는 뜻이다.
- 실제 종합 모델로 만든 새 의견도 inference이지 추가 조사·독립 검증이 아니다.
- 시장 규모·상용 채택·직접 이해관계자 입장·서비스 목표값은 미확인으로 남긴다.
- TRL 4/3은 모의 technical 단계 체크리스트 기반 팀 추정이며 공식 인증이 아니다.

## 출처 표시

원문 저자·URL·라이선스는 입력 fixture의 documents/config.source_attribution과 출력 Reference에 포함한다.
RDKV 원문: CC BY 4.0. Photonic-CXL 원문: CC BY-SA 4.0.
한국어 해석·발췌 편집 예제 데이터: CC BY-SA 4.0. 원저자가 이 해석을 승인했다는 뜻이 아니다.
