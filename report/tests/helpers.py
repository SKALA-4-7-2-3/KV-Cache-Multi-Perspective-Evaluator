from report_agent.prompt import REQUIRED_OUTLINE, REQUIRED_SUBSECTIONS


def sample_input(report_generation: str = "allowed_with_gaps") -> str:
    review_status = "partial" if report_generation == "allowed_with_gaps" else "failed"
    return f"""---
schema_version: report-input-v1
rubric_version: kv-cache-rubric-v1
reference_schema_version: reference-v1
content_language: ko
run_id: test
generated_at: '2026-09-22T00:00:00+00:00'
evaluation_as_of: '2026-09-21'
review_status: {review_status}
report_generation: {report_generation}
human_review_required: true
human_review_scope: final_submission_only
semantic_validation_status: passed
sw_technology_id: SW-01
hw_technology_id: HW-01
valid_perspective_cells: 8/8
valid_criterion_blocks: 46/46
unknown_count: 1
failed_count: 0
evidence_count: 2
reference_candidate_count: 2
demo: true
next: render
synthesis_status: completed
---
# 보고서 생성 Agent 입력
## 1. A
## 2. B
## 3. C
## 4. D
## 5. E
## 6. F
## 7. G
## 8. H
## 9. 근거 인덱스
## 10. REFERENCE CANDIDATES
### [SW-01]
- citation_key: SW01_RDKV
### [HW-01]
- citation_key: HW01_PHOTONIC_CXL
## 11. 출력 완결성
## 12. SELF VALIDATION
"""


def valid_latex() -> str:
    subsections_by_section = {
        "RDKV·Photonic-CXL 기술 개요": REQUIRED_SUBSECTIONS[0:2],
        "관점별 평가": REQUIRED_SUBSECTIONS[2:6],
        "관점 간 비교 및 시사점": REQUIRED_SUBSECTIONS[6:10],
        "한계점 및 확증편향 방지": REQUIRED_SUBSECTIONS[10:12],
    }
    sections = []
    for title in REQUIRED_OUTLINE:
        body = "미확인 사항을 보존한다."
        if title == "한계점 및 확증편향 방지":
            body += " 모의 상위 Agent 입력이며 실제 성능 재현 결과가 아니다."
        if title == "관점별 평가":
            body += r" RDKV\cite{SW01_RDKV}, Photonic-CXL\cite{HW01_PHOTONIC_CXL}."
        for subsection in subsections_by_section.get(title, ()):
            body += "\n" + rf"\subsection{{{subsection}}}" + "\n미확인 사항을 보존한다."
        if title == "REFERENCE":
            body = r"""
\renewcommand{\refname}{}
\begin{thebibliography}{9}
\bibitem{SW01_RDKV} RDKV paper.
\bibitem{HW01_PHOTONIC_CXL} Photonic-CXL paper.
\end{thebibliography}
"""
        sections.append(rf"\section{{{title}}}" + "\n" + body)
    return (
        r"\documentclass[11pt,a4paper]{article}"
        "\n"
        r"\usepackage{kotex}"
        "\n"
        r"\usepackage{hyperref}"
        "\n"
        r"\hypersetup{hidelinks}"
        "\n"
        r"\begin{document}"
        "\n"
        + "\n".join(sections)
        + "\n"
        + r"\end{document}"
    )
