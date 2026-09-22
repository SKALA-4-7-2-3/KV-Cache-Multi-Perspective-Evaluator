# KV Cache Multi-Perspective Evaluator - Report Agent

이 브랜치는 평가 종합 Agent가 전달한 `review.output.md`를 검증하고, 한국어 기술 평가 보고서를 생성하는 보고서 Agent를 담는다.

- 담당 브랜치: `feat/report-agent`
- 입력: UTF-8 Markdown `review.output.md`
- 출력: Overleaf 호환 XeLaTeX 원본과 컴파일된 PDF
- 구조: 독립 실행형 단일 Agent. LangGraph를 사용하지 않는다.

## 처리 흐름

```text
review.output.md
  -> 입력 계약과 생성 상태 검증
  -> 단일 LLM 호출
  -> 목차, 인용, 한계 표현, LaTeX 구조 검증
  -> 실패 시 한 차례 수정 호출
  -> output/tex/kv-cache-technology-evaluation-report.tex
  -> XeLaTeX 또는 Tectonic 컴파일
  -> output/pdf/kv-cache-technology-evaluation-report.pdf
```

최종 산출물은 LaTeX 문자열만이 아니다. Agent는 Overleaf에서 바로 열 수 있는 단일 `.tex` 파일을 보존하고, 같은 원본을 실제로 컴파일한 PDF까지 생성한다.

## 생성 차단 규칙

다음 입력은 보고서를 만들지 않는다.

- `report_generation: blocked`
- `next: repair`
- `semantic_validation_status`가 `passed`가 아닌 입력
- `synthesis_status`가 `completed` 또는 `partial`이 아닌 입력
- 필수 frontmatter 또는 1-12번 입력 섹션 누락
- Reference ID 또는 citation key 중복·손상

`allowed_with_gaps` 입력은 생성할 수 있지만 미확인 사항과 한계를 보고서에 반드시 남긴다. `synthesis_status: partial`이면 관계 분석의 보류 사유도 남긴다. `demo: true`이면 모의 Agent 입력이며 실제 고객 인터뷰, 전체 RAG 실행, 성능 재현 결과가 아니라는 점을 명시한다.

## 설치

팀 Review Agent와 동일하게 Python 3.12 또는 3.13을 사용한다. 시스템 기본
`python3`가 3.14라면 아래처럼 `python3.12`를 명시한다.

```bash
cd report-agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
set -a
source .env
set +a
```

PDF 생성에는 다음 중 하나가 필요하다.

- XeLaTeX와 `kotex`: Overleaf와 동일한 권장 경로
- Tectonic: 로컬 검증용 대체 컴파일러

기본 모델은 `gpt-4.1-mini`이며 `OPENAI_MODEL` 또는 `--model`로 변경할 수 있다.

## 실행

파일 입력:

```bash
python -m report_agent --input ../outputs/review.output.md
```

Review Agent 브랜치가 아직 합쳐지지 않은 단독 테스트에서는
`examples/review.output.mock.md`를 입력으로 사용한다.

표준 입력으로 원격 Markdown 붙여넣기:

```bash
python -m report_agent --input -
```

기본 출력:

```text
output/tex/kv-cache-technology-evaluation-report.tex
output/pdf/kv-cache-technology-evaluation-report.pdf
```

경로 변경:

```bash
python -m report_agent \
  --input review.output.md \
  --output output/tex/report.tex \
  --pdf-output output/pdf/report.pdf
```

PDF 생성은 선택 사항이 아니다. XeLaTeX 또는 Tectonic을 찾을 수 없거나
컴파일에 실패하면 명령은 오류 상태로 종료하며 보고서 생성 완료로 처리하지 않는다.

API 호출 전에 실제 생성 prompt만 확인할 수도 있다.

```bash
python -m report_agent \
  --input review.output.md \
  --prompt-only output/report.prompt.txt
```

## Review Agent에서 직접 연결

Review Agent가 파일 또는 state에 담은 Markdown 전체를 그대로 넘긴다.

```python
from report_agent import ReportAgent

review_output_md = state["report_input_md"]
artifacts = ReportAgent().generate_pdf(review_output_md)

print(artifacts.tex_path)
print(artifacts.pdf_path)
```

팀 통합에서는 내부 LaTeX 단계만 반환하는 `generate()`가 아니라 PDF 생성을
보장하는 `generate_pdf()`를 호출한다. 입력이 `blocked` 또는 `next=repair`이거나
PDF 컴파일에 실패하면 결과 객체를 반환하지 않고 예외로 종료한다.

## Overleaf 사용

1. 생성된 `.tex` 파일을 Overleaf 프로젝트에 업로드한다.
2. Overleaf의 Menu에서 Compiler를 `XeLaTeX`로 선택한다.
3. 별도 이미지, BibTeX 또는 로컬 폰트 없이 단일 파일을 컴파일한다.
4. 로컬 PDF와 Overleaf PDF의 페이지 수, 표, 인용, REFERENCE를 대조한다.

## 고정 보고서 목차

1. SUMMARY
2. 분석 배경 및 KV cache 문제
3. 기술 선정 및 선정 이유
4. RDKV·Photonic-CXL 기술 개요
5. 평가 기준 및 분석 방법
6. 관점별 평가
7. 관점 간 비교 및 시사점
8. 한계점 및 확증편향 방지
9. REFERENCE

SUMMARY가 첫 section이고 REFERENCE가 마지막 section이어야 한다.

## 자동 검증 범위

- 입력 상태 조합과 보고서 생성 가능 여부
- 필수 12개 입력 섹션
- A4 article, `kotex`, 완전한 document 환경
- 고정 목차 제목과 순서
- 허용된 citation key만 사용했는지
- 본문 `\\cite`와 REFERENCE `\\bibitem`의 일치
- RDKV와 Photonic-CXL 원문 인용 존재
- REFERENCE 기본 제목의 중복 방지
- `demo` 및 `allowed_with_gaps` 한계 문구
- 코드 펜스, placeholder, 로컬 경로 및 외부 파일 명령
- LaTeX 중괄호의 기본 완결성
- 실제 PDF 컴파일 성공 여부

의미적 사실 검증과 PDF의 시각 품질은 사람의 최종 확인이 필요하다.

## 테스트

API 키 없이 실행한다.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m unittest discover -s tests -v
```

입력 계약은 [docs/review.output.contract.md](docs/review.output.contract.md), 종합 Agent 연결 안내는 [docs/REPORT-HANDOFF.md](docs/REPORT-HANDOFF.md)를 참고한다.
