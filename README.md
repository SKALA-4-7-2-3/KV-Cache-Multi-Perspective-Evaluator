# Subject

본 프로젝트는 KV cache 최적화 기술을 소프트웨어(SW)·하드웨어(HW) 진영에서 각각 선정하고, 시장·이해관계자·도메인 관점에서 비교 평가하는 **Multi-Agent 기반 Agentic RAG**를 개발하는 프로젝트입니다.

논문 PDF와 사용자의 자연어 요청을 입력받아 기술 근거를 추출하고, 관점별 평가와 종합 검토를 거쳐 한국어 기술 평가 보고서 PDF를 생성합니다.

## Overview

- **Objective** : 각 기술을 복수 관점에서 평가하고, SW·HW 접근의 기대 효과·도입 부담·적용 조건을 비교
- **Method** : 6개 에이전트로 역할을 분리한 Multi-Agent + Agentic RAG — 현재 통합 실행기는 관점별 에이전트를 순차 호출
- **Tools** : 논문 PDF 분석, BGE-M3 기반 검색, Tavily 웹 검색·본문 수집, 구조화 출력 및 근거 검증, LaTeX·PDF 생성
- **Target Domain** : 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙
- **Output** : 관점별 평가 JSON, 종합 Markdown, LaTeX 원본, 최종 보고서 PDF

## Selected Technologies

- **SW : RDKV** — KV cache의 제거(eviction)와 양자화(quantization)를 함께 고려하는 비트 할당 기반 압축 기술입니다. 메모리 사용량을 줄이는 소프트웨어 접근에서 품질·지연 시간·적용 조건의 관계를 평가하기 위해 선정했습니다.
- **HW : Photonic-CXL** — 광 연결과 CXL 기반 공유 메모리 장치를 활용하는 KV cache 관리 기술입니다. 메모리 확장·공유 접근의 기대 효과와 하드웨어 도입·통합 부담을 평가하기 위해 선정했습니다.

두 기술은 같은 KV cache 문제에 서로 다른 방식으로 접근합니다. 논문별 실험 조건과 검증 수준을 함께 비교하며, Photonic-CXL의 서빙 성능 전망은 에뮬레이션·시뮬레이션 근거와 실제 장치 검증을 구분합니다. 입력 논문 정보는 [논문 안내](rag/papers/README.md)에서 확인할 수 있습니다.

## Features

- **PDF 기반 정보 추출** : 논문의 기술 개요·적용 범위·한계·실험 조건을 추출하고, 페이지·문장·표·그림의 원문 근거와 연결
- **Agentic RAG** : 논문 검색·분석·근거 감사를 수행하고, 분석 결과와 검색 기록을 후속 에이전트에 전달
- **다중 관점 평가** : 시장성, 이해관계자의 이익·부담, 도메인 적합성을 같은 논문 근거와 사용자 요청에 따라 평가
- **외부 자료 보강** : 시장·이해관계자 평가에서 웹 자료를 수집하고, 논문 자체의 결과와 시장·운영 배경 자료를 구분
- **확증 편향 방지 전략** : 수집된 근거에서 유리한 결과와 반대 근거·한계·도입 부담을 함께 검토하고, 저자 주장·관찰 결과·분석자의 추론을 구분. 근거가 부족한 항목은 미확인으로 남기며, 종합 의견의 근거 연결과 의미를 별도로 검사
- **보고서 생성** : 관점별 평가와 종합 의견을 한국어 보고서로 작성하고, 본문에서 사용한 출처를 참고문헌에 연결
- **결과 추적·재개** : 단계별 입력·출력과 실행 상태를 저장하고, 중단된 실행을 재개하거나 특정 단계를 다시 실행

## Tech Stack

- **Framework** : LangGraph, LangChain, Pydantic — 에이전트 내부 흐름·구조화 출력·검증에 사용하며 전체 단계는 Python 통합 실행기로 연결
- **LLM/Generator** : 통합 평가·종합·보고서 기본 모델 `gpt-4.1-mini`; 별도 RAG 실행 기본 모델 `gpt-5.6-terra`
- **LLM/Judge** : 종합 의견 의미 검사 기본 모델 `gpt-4.1-mini`; RAG 근거 감사 기본 모델 `gpt-5.6-terra` — 생성과 검증에 별도 프롬프트 사용
- **Retrieval** : Chroma 벡터 저장소 + Dense·Sparse 결합 검색 + ColBERT 재순위화·MMR / **Hit Rate@K, MRR : 측정 결과 미기록**
- **Embedding** : 오픈소스 `BAAI/bge-m3` — 고정 revision의 로컬 모델 사용
- **PDF Parsing** : PyMuPDF, pdfplumber
- **Web Search** : Tavily
- **Report** : Markdown → LaTeX → PDF, XeLaTeX 또는 Tectonic
- **Runtime** : Python 3.12, uv — 통합 실행 환경과 RAG 실행 환경 분리

모델명은 코드의 기본 설정 기준입니다. 통합 실행 모델은 `--model`로 변경할 수 있으며, RAG 모델 설정은 `rag/`에서 별도로 관리합니다.

## Agents

전체 시스템은 **총 6개 에이전트**로 구성됩니다. RDKV와 Photonic-CXL을 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙 관점에서 평가합니다.

| 에이전트 | 역할 | RAG 및 자료 활용 | 주요 내용 |
| --- | --- | --- | --- |
| 기술 조사 에이전트 | 두 논문의 기술 분석·근거 추출 | PDF RAG | RDKV·Photonic-CXL 논문에서 기술 개요, 적용 범위, 실험 조건, 한계를 추출하고 원문 근거와 연결 |
| 시장 평가 에이전트 | 시장성·도입 여건 평가 | 논문 분석 결과 + 웹 검색·본문 수집 | 관련 시장, 제품, 생태계 자료를 조사하여 두 기술의 도입 조건과 시장 관점의 기회·제약 평가 |
| 이해관계자 평가 에이전트 | 운영 조직의 이익·부담 평가 | 논문 분석 결과 + 웹 검색·본문 수집 | 데이터센터·클라우드 서빙 운영 조직의 기대 이익, 도입·운영 부담, 수용 조건 평가 |
| 도메인 평가 에이전트 | 장문맥 문서 QA 서빙 적합성 평가 | 기술 조사 RAG 결과 활용 | 메모리 용량, 품질, 지연 시간, 처리량, GPU 호환성 등 도메인 요구에 대한 적합성 평가 |
| 평가 종합 에이전트 | 관점별 평가 비교·종합 | 관점별 평가 결과 + 수집 근거 | 세 관점의 일치·차이를 비교하고, 근거 기반 기술 성숙도(TRL) 추정, 조건부 종합 의견, 의미 검사 결과와 검토 사항 정리 |
| 보고서 생성 에이전트 | 한국어 기술 평가 보고서 생성 | 종합 결과 + 출처 자료 | 기술 분석과 관점별 평가를 보고서로 연결하고, 본문 인용·참고문헌을 포함한 LaTeX 원본과 PDF 생성 |

기술 조사 에이전트는 PDF에서 직접 근거를 검색하며, 도메인 에이전트는 전달받은 RAG 결과로 평가합니다. 시장·이해관계자 에이전트는 Tavily로 웹 자료를 보강합니다. 기본 실행에서는 기술 조사 에이전트의 저장된 결과를 재사용합니다.

구현 위치는 기술 조사 에이전트가 `rag/`, 시장·이해관계자·도메인·평가 종합 에이전트가 `agent/`, 보고서 생성 에이전트가 `report/`입니다. 세부 구현은 [기술 조사 안내](rag/README.md), [평가·종합 에이전트 안내](agent/README.md), [보고서 생성 안내](report/README.md)를 참고하세요.

## Architecture

![KV cache 다중 관점 평가 아키텍처](docs/images/architecture.svg)

전체 흐름은 **기술 조사 → 도메인 평가 → 이해관계자 평가 → 시장 평가 → 평가 종합 → 보고서 생성**입니다. 세 관점에는 같은 논문 자료와 사용자 요청을 각각 전달합니다. 기본 RAG 모드는 기술 조사 에이전트의 저장 결과 재사용(`saved`)이며, `--run-rag`를 지정하면 입력 PDF를 새로 분석한 뒤 후속 에이전트를 실행합니다.

## Directory Structure

```text
.
├── config/
│   └── pipeline.json         # 논문 경로·사용자 요청·평가 맥락·RAG 모드
├── pipeline/                 # 통합 실행기와 단계별 입력·출력 연결
│   └── __main__.py           # python -m pipeline 실행 진입점
├── rag/                      # Technical Research Agent와 별도 실행 환경
│   ├── papers/               # 입력 논문 PDF
│   ├── src/                  # PDF 분석·검색·근거 감사
│   └── examples/results/     # 재사용 가능한 논문 분석 결과
├── agent/                    # 에이전트 구현과 각 모듈의 프롬프트
│   ├── domain/               # 도메인 적합성 평가
│   ├── stakeholder/          # 이해관계자 평가
│   ├── market/               # 시장성 평가
│   └── review/               # 검증·종합
├── report/                   # 보고서 작성·LaTeX·PDF 생성
├── docs/                     # 상세 실행 안내와 아키텍처 이미지
├── outputs/                  # 실행별 입력·평가 결과·최종 보고서
├── .env.example              # API 키 설정 예시
├── pyproject.toml            # Python 3.12 통합 환경 의존성
└── README.md
```

## Usage

아래 명령은 별도 표시가 없으면 **저장소 루트**에서 실행합니다. 기본 입력은 [config/pipeline.json](config/pipeline.json)이며, 논문 PDF와 자연어 요청을 명령행에서 바꿀 수 있습니다.

### 1. 최초 환경 준비

Python 3.12와 `uv`를 준비한 뒤, 통합 실행 환경과 RAG 실행 환경을 각각 설치합니다.

```bash
uv python install 3.12
uv sync --frozen
uv sync --frozen --project rag

# 기존 .env가 있으면 그대로 유지합니다.
if [ ! -f .env ]; then cp .env.example .env; fi
```

루트 `.env`에 `OPENAI_API_KEY`, `TAVILY_API_KEY` 값을 설정합니다. [.env.example](.env.example)을 참고하세요. 기존 파일의 다른 설정은 유지합니다. 환경변수로도 제공할 수 있지만, 루트 `.env`에 같은 항목이 있으면 파일 값이 우선합니다.

새 논문 분석에는 로컬 BGE-M3 모델이 필요합니다. **반드시 `rag/` 안에서** 내려받습니다. 기본 모델 경로가 현재 폴더 기준 `data/models`이므로, 통합 실행기가 사용하는 `rag/data/models`에 설치하기 위한 명령입니다.

```bash
(cd rag && uv run --frozen paper-review models pull bge-m3)
```

입력 PDF는 Git에 포함되지 않습니다. [논문 다운로드 안내](rag/papers/README.md)의 공식 원문에서 받아 다음 위치에 둡니다.

- `rag/papers/2605.08317.pdf` — RDKV
- `rag/papers/2607.27187.pdf` — Photonic-CXL

최종 PDF 생성에는 **XeLaTeX와 `kotex`, 또는 Tectonic**, 그리고 **NanumMyeongjo Regular/Bold** 글꼴이 필요합니다. 글꼴은 [Google Fonts 배포본](https://github.com/google/fonts/tree/main/ofl/nanummyeongjo)을 사용할 수 있습니다. 컴파일러를 자동으로 찾지 못하면 루트 `.env`의 `XELATEX_BIN` 또는 `TECTONIC_BIN`에 실행 파일의 절대 경로를 지정합니다.

### 2. PDF 2개와 자연어 요청으로 전체 실행

다음 명령은 **RAG → Domain → Stakeholder → Market → Review → Report**를 실행하고 최종 보고서 PDF를 만듭니다. 실제 OpenAI·Tavily API 호출이 발생합니다. `--as-of`는 후속 평가의 조사 기준일이므로 원하는 날짜로 바꾸세요.

```bash
uv run --frozen python -m pipeline \
  --run-rag \
  --pdf rag/papers/2605.08317.pdf \
  --pdf rag/papers/2607.27187.pdf \
  --instruction "장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해." \
  --model gpt-4.1-mini \
  --as-of 2026-09-22 \
  --output outputs/my-live-docqa
```

`--run-rag`를 생략하면 설정 파일의 기본 `saved` 모드로 기존 논문 분석을 읽습니다. 위 명령은 종합 생성과 의미 검토까지 수행하도록 `--draft`를 사용하지 않습니다. RAG 내부에서는 조건이 일치하는 논문 분석·검색 캐시를 재사용할 수 있습니다.

`--model`은 **후속 평가·종합·보고서 모델**을 선택합니다. RAG 생성·감사 모델은 별도 설정인 `PRA_OPENAI_MODEL`, `PRA_AUDIT_MODEL`을 사용하며 기본값은 모두 `gpt-5.6-terra`입니다. 변경하려면 루트 `.env`에 해당 항목을 지정합니다. RAG 세부 설정은 [rag/.env.example](rag/.env.example)을 참고하세요.

### 3. 저장된 논문 분석을 재사용하거나 입력만 확인

RAG 호출 시간과 비용을 줄이려면 같은 요청으로 생성된 최신 저장 예제를 지정할 수 있습니다. 아래 실행도 **후속 평가·웹 검색·종합·보고서 작성 API를 호출**합니다. 자연어 요청을 바꾸면 후속 평가에 적용되며, 저장된 논문 분석 자체를 재생성하지는 않습니다.

```bash
uv run --frozen python -m pipeline \
  --research rag/examples/results/technical-long-context-qa-datacenter \
  --instruction "장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해." \
  --output outputs/my-saved-docqa
```

**외부 API 호출 없이** 저장 결과가 후속 입력으로 변환되는지만 확인하려면 다음 명령을 사용합니다. 이 확인에는 RAG 환경·BGE-M3 모델·PDF 컴파일러가 필요하지 않습니다. `--run-rag`는 함께 지정하지 않습니다.

```bash
uv run --frozen python -m pipeline \
  --research rag/examples/results/technical-long-context-qa-datacenter \
  --instruction "장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해." \
  --output outputs/prepare-only \
  --stop-after prepare
```

### 4. 결과 확인과 중단된 실행 재개

완료된 실행의 `--output` 폴더에서 다음 파일을 확인합니다. 출력을 지정하지 않으면 `outputs/integration/<실행 시각>/`에 저장됩니다.

| 파일 | 내용 |
| --- | --- |
| `report.pdf` | 최종 보고서 PDF |
| `report.tex`, `report.input.md` | 보고서 원본과 입력 |
| `review.output.md` | 종합 의견과 검토 사항 |
| `domain.output.json`, `stakeholders.output.json`, `market.output.json`, `review.output.json` | 단계별 분석 결과 |
| `run.json` | 단계별 실행 상태·모델·조사 기준일 |
| `research.bundle.json`, `research.context_manifest.json` | 전체 논문 분석과 후속 입력에 포함한 근거 기록 |
| `rag/pipeline-*/cli.stdout.json`, `rag/pipeline-*/cli.stderr.log` | 새 RAG 실행의 출력·오류 로그 |
| `rag/pipeline-*/technical/` | 새 RAG의 논문별 분석·감사·실패 기록 |

RAG 근거 검증은 기본적으로 최대 2회 자동 보완 후에도 통과하지 못하면 `failed_quality`로 종료하고 후속 에이전트 실행을 중단합니다. 이 경우 `rag/pipeline-*/technical/failure.json`과 오류 로그를 확인합니다.

**출력 폴더 바로 아래에 `run.json`이 있는 경우**, 기존 실행과 같은 PDF·요청·RAG 모드·모델·조사 기준일에 `--resume`을 붙여 재개합니다. 아래는 2번 명령의 재개 예제입니다. 성공한 RAG와 후속 단계 결과를 조건에 맞게 재사용합니다.

```bash
uv run --frozen python -m pipeline \
  --run-rag \
  --pdf rag/papers/2605.08317.pdf \
  --pdf rag/papers/2607.27187.pdf \
  --instruction "장문맥 문서 QA를 제공하는 데이터센터, 클라우드 서빙입장에서 보고서를 작성하고자해." \
  --model gpt-4.1-mini \
  --as-of 2026-09-22 \
  --output outputs/my-live-docqa \
  --resume
```

RAG 실패 등으로 **출력 폴더 바로 아래의 `run.json`이 아직 없으면**, 새 `--output` 폴더로 전체 명령을 다시 실행합니다. 이때도 RAG 내부의 유효한 캐시는 재사용할 수 있습니다. 입력·모델을 바꿀 때도 새 출력 폴더를 사용합니다. 이미 사용한 출력 경로로 새 실행을 시작하면 충돌하므로, 위 예제를 반복할 때는 출력 경로를 바꾸거나 재개 조건을 맞춥니다.

기본 보고서는 근거와 검토 사항을 포함한 분석 초안이며, 자동 검토 미통과 항목은 검토 사항으로 남습니다.

RAG 환경 준비는 [RAG 안내](rag/README.md), 단계별 실행·재개 옵션은 [파이프라인 안내](docs/pipeline.md)를 참고하세요.

## Contributors

- 김광현 (P210): 이해관계자 평가 에이전트 개발
- 박정빈 (P218): 도메인 평가 에이전트 개발
- 백순철 (P221): 평가 종합 에이전트 개발
- 이지석 (P228): 기술 조사 에이전트 개발
- 이현정 (P230): 보고서 생성 에이전트 개발
- 정회륜 (P237): 시장 평가 에이전트 개발
