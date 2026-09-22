# Long-context QA datacenter technical research result

다음 자연어 지시와 두 논문을 사용한 별도 기술조사 성공 결과다.

> 장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해.

입력 논문은 `2605.08317`(RDKV)과 `2607.27187`(Photonic-CXL)이며, 최종 상태는
`succeeded`다. 두 기술은 서로 다른 계층에서 같은 KV-cache 병목을 다루는
`complementary` 관계로 분류됐다. 함께 적용하는 구성은 논문에서 직접 검증된 결과가
아니므로 `analyst_inference`와 검증 필요 조건으로 분리했다.

## 품질 결과

- evidence resolution rate: 1.0
- locator resolution rate: 1.0
- critical inventory coverage: 1.0
- unsupported numeric claims: 0
- embedding: BGE-M3 고정 revision `5617a9f61b028005a4858fdac845db406aefb181`

## 파일

- `run.json`: 전체 실행 계약과 진입점
- `dossiers/*.json`: 논문별 기술 개요·범위·한계·실험 관측
- `comparison.json`: 관계, 조건 행렬, 비교 가능성, 결합 가설
- `evidence_registry.json`: 페이지·문장 span·표 cell·visual 근거
- `retrieval_traces.jsonl`: dense·sparse·ColBERT·MMR 검색 추적
- `visuals/*.png`: 선택적으로 분석한 표·그림 crop
- `markdown/README.md`: 사람이 읽기 쉬운 결과 진입점

원본 PDF, API key와 로컬 모델 weight는 포함하지 않았다. 로컬 절대경로는 공개
저장소용 상대경로로 정규화했고 JSON artifact의 SHA-256과 artifact ID도 다시 계산했다.
원본 PDF의 provenance hash와 evidence ID는 분석 당시 값을 유지한다.

원본 PDF를 `source_manifest.json`의 `expected_path`에 놓으면 전체 계약을 검증할 수 있다.

```bash
uv run paper-review validate-technical \
  examples/results/technical-long-context-qa-datacenter/run.json
```
