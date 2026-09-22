# 기술 조사 JSON 입력 안내

기술 조사 에이전트가 만든 `paper_analysis` **schema_version 1.1.0 / status succeeded** 결과를 바로 받는다. JSON 한 파일에 논문 객체 한 개를 넣거나, 두 파일을 함께 지정하거나, 한 파일의 JSON 배열에 두 객체를 넣을 수 있다. 현재 조사 한도에 맞춰 한 번에 최대 두 논문을 처리한다.

## 실행

`market-research-agent` 폴더에서 실행한다. 파일 내용은 MD로 변환할 필요가 없다.

```bash
# 샘플 구조 확인: 실제 논문 내용이 아닌 합성 테스트 파일이며 API 호출 없음
python -m market_agent.cli --input market_agent/fixtures/paper_analysis_sw.json market_agent/fixtures/paper_analysis_hw.json --mode parse

# 실제 기술 조사 결과 파일로 실행
python -m market_agent.cli --input technical_sw.json technical_hw.json --as-of 2026-09-22 --mode live

# 한 논문만 처리: 시장 담당 6개 항목
python -m market_agent.cli --input technical_sw.json --mode live

# 호출 한도와 도메인 지정
python -m market_agent.cli --input technical_sw.json technical_hw.json --domain cloud_datacenter --search-limit 6 --extract-limit 10 --llm-limit 5 --mode live
```

`--input a.json --input b.json` 표기도 지원한다. 공개한 SW/HW fixture는 구조 검사용 합성 자료다. 실제 첨부 JSON과 개인 경로·전체 논문 발췌는 Git에 포함하지 않았다.

## 필드 처리

| 상위 JSON | 시장 에이전트에서의 처리 |
| --- | --- |
| `schema_version`, `status` | 지원 버전 및 성공한 분석인지 먼저 검사 |
| `paper.paper_id`, `title` | 문서 ID·논문명을 보존; 기술별 내부 ID 부여 |
| `paper.arxiv_id` | 값이 있으면 공개 arXiv 주소 구성; 버전이 없으면 동일 버전 확인 필요 경고 |
| `paper.source_path` | 출처 메타데이터로 보존. 해당 경로를 열거나 파일명으로 논문 URL을 추정하지 않음 |
| `analysis.technical_overview/scope/limitations` | 주장 유형·confidence·근거 참조·미보고 항목을 기술 배경으로 정규화 |
| `evidence_registry` | 원래 evidence_id·document_id·페이지·절·snippet 연결 보존 |
| `quality`, `diagnostics`, `run` 및 추가 필드 | 원래 내용을 내부 JSON에 보존. 시장의 실행 설정과 분리 |

기술 추출 모델에는 정규화한 기술 배경을 논문당 최대 6,000자 제공하고 잘림 여부를 표시한다. 원본 전체는 내부 기록에 보존한다. 상위 에이전트의 모델명·로컬 경로는 배경 payload에 넣지 않는다.

### 논문 식별과 누락 정보

- 현재 두 논문은 제목의 RDKV / Photonic-CXL로 SW/HW를 인식한다. 파일 순서로 SW/HW를 추측하지 않는다.
- 다른 논문은 `--approach SW` 또는 두 객체 순서에 맞춘 `--approach SW HW`로 구분을 지정한다. 기술명은 제공된 제목을 사용한다.
- 전달된 HW 예시는 `arxiv_id`가 null이다. URL은 빈 상태와 경고를 유지하고 제목 기반 검색을 진행한다.
- `abstract`, `section`, `arxiv_id`의 null과 빈 authors 목록을 허용한다.
- 상위 실행의 `finished_at`은 논문 발행일이 아니다. 제공되지 않은 발행일은 미확인으로 유지한다.
- 논문·근거 ID 중복, 서로 다른 문서로의 근거 연결, 존재하지 않는 근거 참조, 잘못된 필드 유형·실패 상태는 API 호출 전에 오류로 반환한다.

## 시장 실행 옵션

| 옵션 | JSON의 기본값 |
| --- | --- |
| `--as-of` | 실행하는 컴퓨터의 현재 날짜 |
| `--domain` | `cloud_datacenter` |
| `--search-limit` | 6 |
| `--extract-limit` | 10 |
| `--llm-limit` | 5 |
| `--model` | `gpt-4.1-mini` |

호출 한도는 두 논문을 함께 처리할 때도 **전체 실행 기준**이다. 0을 지정하면 해당 호출을 하지 않는다. 재현 가능한 비교에는 `--as-of`를 명시한다. API 키는 기존 `.env`의 OpenAI·Tavily 키를 사용한다.

## 근거의 성격과 출력

논문 분석 결과와 발췌는 상위 에이전트가 제공한 배경 자료다. 기존 `provided_summary` 신뢰 경계를 적용하여 원문을 직접 조회한 `full_text` 시장 근거로 자동 승격하지 않는다. `quality`의 supported나 높은 confidence는 시장 규모·상용화·실제 고객 채택의 증거를 대신하지 않는다. 시장 조사에서 확보한 웹 원문은 기존 구절 ID·주장·의미 검토를 거친다.

출력은 계속 `market_handoff.md` 한 개다. 입력 논문이 한 개면 6행, 두 개면 12행이며 없는 기술을 추가하지 않는다. 내부 캐시에는 `input.json`과 원래 상위 문서, 정규화한 상태, 검증 기록을 저장한다. 원래 공백·키 순서 대신 JSON의 필드와 값을 보존한다.

입력 내용·기준일·도메인·한도·기술 구분·모델·코드가 달라지면 이전 캐시를 재사용하지 않는다. 기존 MD v0.1 입력도 지원하며 그 경우 `input.md`를 저장한다.

## 검증 기록 — 2026-09-22

- 전체 unittest 92개 통과. 새 입력 파싱, 잘못된 상태/참조 거부, 단일 논문, 복수 `--input`, 옵션, JSON 저장·재사용, 상위 모델 설정 분리, 기존 MD 회귀를 검사했다.
- 실제 첨부 두 파일에서 기술 2개 및 원래 근거 25개를 읽었다(SW 13, HW 12).
- 첨부 파일로 `--mode fixture`에서 입력 → Graph → 12행 MD → JSON 내부 저장을 확인했다. **실제 시장 결과를 생성하는 live 호출은 이번 입력 변경 검증에서 수행하지 않았다.**
- 검증 출력 위치: `market_agent/outputs/20260922_json_input_fixture/market_handoff.md`. 가상 결과이므로 통합 보고서의 시장 근거로 사용하지 않는다.
