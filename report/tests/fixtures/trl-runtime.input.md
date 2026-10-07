---
schema_version: report-input-v1
rubric_version: kv-cache-rubric-v1
reference_schema_version: reference-v1
content_language: ko
run_id: test
generated_at: '2026-09-22T00:00:00+00:00'
evaluation_as_of: '2026-09-21'
review_status: partial
report_generation: allowed_with_gaps
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
### [SW-laboratory]
- 연결 Reference ID: SW-01
### [HW-concept]
- 연결 Reference ID: HW-01
## 10. REFERENCE CANDIDATES
### [SW-01]
- citation_key: SW01_RDKV
### [HW-01]
- citation_key: HW01_PHOTONIC_CXL
## 11. 출력 완결성
## 12. SELF VALIDATION

<!-- REVIEW_TRL_JSON
{"SW-01": {"level": 4, "basis_version": "v1", "evidence_ids": ["SW-laboratory"], "checks": [{"level": 4, "status": "met", "reason": "구성요소 검증", "evidence_ids": ["SW-laboratory"]}], "next_unconfirmed": {"level": 5, "status": "unknown", "required_evidence": "대표 QA 워크로드의 요구 성능 검증", "reason": "목표 서비스의 동시성 조건 미확인", "evidence_ids": []}, "notice": "공개 정보 기반 팀 추정이며 공식 인증이 아니다."}, "HW-01": {"level": null, "basis_version": "v1", "evidence_ids": [], "checks": [], "next_unconfirmed": {"level": 1, "status": "unknown", "evidence_ids": [], "required_evidence": "구현 버전의 단계별 원문 근거", "reason": "제공 자료에서 단계 판정 근거 미확인"}, "notice": "공개 정보 기반 팀 추정이며 공식 인증이 아니다."}}
END_REVIEW_TRL_JSON -->
