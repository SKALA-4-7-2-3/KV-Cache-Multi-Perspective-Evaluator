# Two-paper technical research result

`2605.08317`(RDKV)과 `2607.27187`(Photonic-CXL)을 기술적으로 비교한 성공 실행
`technical-bge-e2e-20260922-v22`의 공개 가능한 결과 사본이다.

## 파일

- `run.json`: 실행 metadata, 품질 지표, 전체 dossier와 comparison을 담은 진입점
- `dossiers/*.json`: 논문별 기술 개요·범위·한계·주장·실험 관측
- `comparison.json`: 기술 관계, 비교 행렬, 비교 가능성 및 결합 가설
- `evidence_registry.json`: 주장과 페이지·문장·표 셀·visual을 연결하는 근거
- `retrieval_traces.jsonl`: dense·sparse·ColBERT·MMR 검색 진단 기록
- `visuals/*.png`: 선택적으로 분석한 표·그림 crop
- `markdown/README.md`: JSON 결과를 사람이 검토하기 쉽게 변환한 참고용 진입점

`markdown/` 파일은 검토 편의를 위한 파생본이다. 에이전트 간 전달, 스키마 검증 및
무결성 확인에는 원본 JSON을 기준으로 한다.

원본 PDF, API key와 로컬 모델은 포함하지 않았다. `source_path`와 artifact 경로는 공개 저장소용
상대경로로 정규화했으며, `run.json`의 artifact SHA-256과 ID를 정규화된 파일에 맞게 다시
계산했다. 논문 SHA-256과 evidence ID는 분석 당시 원본과의 provenance를 유지한다.

`source_manifest.json`은 전체 validator가 요구하는 원본 경로와 SHA-256을 기록한다. 원본
PDF를 manifest의 `expected_path`에 놓은 뒤 다음 명령을 실행하면 source hash를 포함한 전체
계약을 검증한다. PDF가 없으면 validator는 의도대로 `source document is missing`을 반환한다.

```bash
uv run paper-review validate-technical \
  examples/results/technical-bge-e2e-two-papers/run.json
```
