# RAG 입력 논문

두 PDF를 공식 arXiv PDF 주소에서 준비했다. 저장된 기술조사 결과의
`source_manifest.json`에 있는 SHA-256과 두 파일 모두 일치한다.
다운로드 정보는 `source-downloads.json`에 기록했다. PDF 자체는 Git에 포함하지 않는다.

| 파일 | 논문 | 공식 원문 | SHA-256 |
|---|---|---|---|
| `2605.08317.pdf` | RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache | [arXiv PDF](https://arxiv.org/pdf/2605.08317) | `25836a419005694122c571121030b89bd7ac634f74ac3b5d4c67bf0a19b10e3d` |
| `2607.27187.pdf` | A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference | [arXiv PDF](https://arxiv.org/pdf/2607.27187) | `d6a67efde2a1ed0e9fb38302708d83e1e43f2c237acd4826ec4daf1bd44e2326` |

기본 보고서 실행은 `rag/examples/results/technical-bge-e2e-two-papers`의 기존
조사 결과를 읽는다. 입력 PDF가 준비되어 있어도 RAG를 자동으로 다시 실행하지 않는다.

새 체크아웃에서 PDF가 없다면 위 주소에서 내려받아 이 폴더에 같은 파일명으로 둔다.
원본을 새로 조사하려는 경우에만 `rag` 폴더에서 별도 환경과 모델을 준비한다.

```bash
uv sync --frozen
uv run --frozen paper-review models pull bge-m3
uv run --frozen paper-review research \
  --source papers/2605.08317.pdf \
  --source papers/2607.27187.pdf \
  --instruction '클라우드 데이터센터의 LLM 추론 운영 관점에서 두 기술의 효과와 적용 조건을 비교해줘'
```

연구 CLI는 `outputs/<job-id>/technical/run.json`을 생성한다. 통합 파이프라인의
`--run-rag`도 같은 CLI를 별도 프로세스로 호출하고 그 결과를 후속 에이전트에 전달한다.
이번 폴더 정리에서는 모델 설치나 RAG 재실행을 수행하지 않았다.
