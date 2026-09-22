# 상위 Agent 입력 (검증 전)

아래 YAML 블록이 실행용 데이터입니다. 자유 본문은 파싱하지 않습니다.
보고서 담당자에게는 review.output.md를 전달하세요. 이 파일은 그 전 단계 입력입니다.

~~~yaml
schema_version: review-input-v1
state:
  config:
    run_id: paper-grounded-simulated-agents-v1
    domain: 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙
    demo: true
    rubric_version: kv-cache-rubric-v1
    requirements: {}
    input_kind: real-paper-evidence / manually-authored simulated-agent-output
    notice: 실제 RAG/Agent/API 호출 없음. 논문 출처는 실제, 평가는 테스트용으로 작성. 목표 SLO 미지정.
    source_attribution:
      SW-01:
        authors: Junkai Zhang, Hang Guo, Luca Benini, Yawei Li
        license: https://creativecommons.org/licenses/by/4.0/
        language: en
      HW-01:
        authors: Jing Ding, Yash Nishant, Chandrish Ambati, Jyothsna Kamati, Trung Diep
        license: https://creativecommons.org/licenses/by-sa/4.0/
        language: en
    evaluation_as_of: '2026-09-21'
    raw_domain_input: '주 도메인: 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙. 대상은 추론 인프라 개발·운영 담당자이며, 온디바이스는 적용 한계를 확인하는
      보조 시나리오로 다룬다.'
    normalized_domain:
      id: cloud-long-context-document-qa
      name: 장문맥 문서 QA를 제공하는 데이터센터·클라우드 서빙
      users: 추론 인프라 개발·운영 담당자
      environment: 데이터센터·클라우드
      workload: 장문맥 문서 QA
      metrics:
      - KV 용량
      - TTFT
      - TPOT
      - 처리량
      - 품질
      - 비용
      scope: SW 압축/HW 확장의 근거·조건·미확인 사항 비교
      excluded: 온디바이스의 성능 우열 검증; 논문 실험 재현; 전용 HW 설치
      assumptions:
      - 논문 v1과 공개 자료를 근거로 평가
      unknowns:
      - 목표 문맥 길이·동시성·품질 허용치·지연·예산 미제공
    domain_requirements: {}
    problem_definition: 장문맥 문서 QA의 KV cache 용량·대역폭 병목을 SW 압축과 HW 확장이 어떻게 완화하는지, 도입 비용·품질·운영 제약과 함께 비교한다.
    technology_selection:
      SW-01:
        method: Human-based
        reason: KV 데이터량 감소와 GPU 통합·품질 손실 조건을 평가하기 위해 선정
      HW-01:
        method: Human-based
        reason: 메모리 확장과 호스트 경로·전용 인프라·검증 수준을 평가하기 위해 선정
  documents:
    SW-01:
      title: 'RDKV: Rate-Distortion Bit Allocation for Joint Eviction and Quantization of the KV Cache'
      url: https://arxiv.org/pdf/2605.08317v1
      version: v1
      pages: 28
      sha256: 25836a419005694122c571121030b89bd7ac634f74ac3b5d4c67bf0a19b10e3d
      kind: paper
      published_at: '2026-05-08'
      retrieved_at: '2026-09-21T10:04:51.666310+00:00'
    HW-01:
      title: A Photonic-CXL Memory Appliance for Scalable KV Cache Management in LLM Inference
      url: https://arxiv.org/pdf/2607.27187v1
      version: v1
      pages: 12
      sha256: d6a67efde2a1ed0e9fb38302708d83e1e43f2c237acd4826ec4daf1bd44e2326
      kind: paper
      published_at: '2026-07-29'
      retrieved_at: '2026-09-21T10:04:51.666310+00:00'
  evidence:
    SW-principle:
      id: SW-principle
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: We formulate KV cache compression as a rate–distortion problem. [...] We realize the resulting
        mixed-bit cache with TriZone, a packed-decode layout that fuses dequantization into the attention
        kernel, turning the mixed-bit allocation into actual memory savings.
      page: 2
      location: §1 Contributions
      method: analysis
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    SW-kernel:
      id: SW-kernel
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: To translate bit-width savings into actual speedup and memory reduction, the cache must
        stay packed in HBM while dequantization is fused into the attention computation.
      page: 6
      location: §3.3 Efficient Packed Decode
      method: documentation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    SW-quality:
      id: SW-quality
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: FullKV 98.58 98.88 96.98 90.33 88.49 79.91 [...] RDKV 98.62 98.61 95.65 88.28 80.07 66.95
        [...] Table 2 reports results on LLaMA-3.1-8B-Instruct under Btotal = 1024L.
      page: 8
      location: Table 2; §4.1 RULER (1024L budget)
      method: gpu_experiment
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    SW-memory:
      id: SW-memory
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: RDKV uses 30.5 GB at 128K (1.9× reduction vs. FullKV) and 44.5 GB at 256K, running on the
        same device where FullKV cannot.
      page: 9
      location: §4.2 Memory
      method: gpu_experiment
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    SW-implementation:
      id: SW-implementation
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: All models up to 8B parameters (LLaMA-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3, Qwen3-4B)
        run on a single NVIDIA A100 64 GB GPU. [...] Calibration is performed once per (ℓ, h) slice and
        cached to disk.
      page: 15
      location: 'Appendix B: Calibration / Hardware'
      method: gpu_experiment
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    SW-limit:
      id: SW-limit
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: RDKV compresses the KV cache once after prefill and does not re-evaluate during decoding.
        [...] The allocation is therefore frozen with respect to attention-pattern shifts that may occur
        during generation.
      page: 28
      location: 'Appendix K: Limitations'
      method: documentation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    SW-impact:
      id: SW-impact
      doc_id: SW-01
      technology_ids:
      - SW-01
      excerpt: RDKV reduces the memory footprint and decoding latency of long-context LLM inference without
        modifying model weights or training procedures.
      page: 28
      location: 'Appendix L: author impact statement'
      method: statement
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    HW-architecture:
      id: HW-architecture
      doc_id: HW-01
      technology_ids:
      - HW-01
      excerpt: The PF Memory Appliance is a memory device built using 16 Photonic Fabric Memory Modules,
        providing 32 TBs of shared DDR5 memory capacity with a unified address space [...] The PF Memory
        Appliance connects to host servers through a Photonic Fabric NIC (PF-NIC), a PCIe Gen6/CXL 3.1
        adapter card [...] An External Laser Source (ELS) is required to produce optical illumination
        for the PF Memory Modules and the PF-NIC.
      page: 5
      location: §III.A System Overview
      method: documentation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    HW-emulation:
      id: HW-emulation
      doc_id: HW-01
      technology_ids:
      - HW-01
      excerpt: The experimental framework is implemented on the Siemens Veloce Strato-M emulation platform
        [...] To emulate the host environment, we use QEMU to model a CPU running a guest Linux operating
        system that functions as the PCIe/CXL host.
      page: 6
      location: §IV.A Emulation Framework
      method: emulation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    HW-host-limit:
      id: HW-host-limit
      doc_id: HW-01
      technology_ids:
      - HW-01
      excerpt: A single CXL host is limited to 128 GB/s due to the PCIe Gen6 interface constraint and
        therefore cannot independently saturate a PF Memory Module.
      page: 6
      location: §IV.B Bandwidth Characterization
      method: emulation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    HW-integration:
      id: HW-integration
      doc_id: HW-01
      technology_ids:
      - HW-01
      excerpt: For vLLM, we will implement a CXL KV connector [...] The appliance supports coherence across
        hosts using a rendezvous-based consistency protocol. [...] Framework-specific connectors (top
        purple tier) implement thin adapters against each engine's pluggable API.
      page: 8
      location: '§V, Fig.7: proposed integration'
      method: documentation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    HW-serving:
      id: HW-serving
      doc_id: HW-01
      technology_ids:
      - HW-01
      excerpt: We evaluate our proposed architecture using LLMServingSim [...] Each conversation consists
        of 10 turns, with each turn comprising 5,120 input tokens and 500 output tokens. [...] all KV
        cache entries are retained in the pooled memory, and subsequent turns benefit from full prefix
        cache hits (82% hit rate).
      page: 9
      location: '§VI.A/B, Fig.8: serving simulation'
      method: simulation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
    HW-pending:
      id: HW-pending
      doc_id: HW-01
      technology_ids:
      - HW-01
      excerpt: validation on the physical PF Memory Appliance hardware [...] inference workloads remains
        pending. [...] Cost-benefit analysis comparing PF Memory Appliance against alternative scaling
        approaches [...] will provide additional deployment guidance.
      page: 10
      location: §VIII Limitations and Future Work
      method: documentation
      verified_source: true
      synthetic: false
      collected_at: '2026-09-21T10:04:51.666310+00:00'
      independence: author
  assessments:
    technical:
      round: 0
      status: completed
      results:
        SW-01:
          status: completed
          items:
          - criterion_id: mechanism
            judgment: conditional
            conclusion: 저자는 제거와 양자화를 비트 배정 문제로 결합하고, TriZone으로 압축 캐시를 어텐션 커널과 연결한다.
            conditions:
            - 선정 논문 v1의 알고리즘·구현 범위
            evidence_ids:
            - SW-principle
            - SW-kernel
            basis: fact
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: global
            domain_relevance: direct
          - criterion_id: validation_scope
            judgment: conditional
            conclusion: GPU 기반 구현과 벤치마크를 보고했으나, 실제 서비스의 품질·동시성·운용 보증과 구분한다.
            conditions:
            - 저자 실험이며 이 실습에서 재현하지 않음
            evidence_ids:
            - SW-implementation
            - SW-quality
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: global
            domain_relevance: direct
          - criterion_id: maturity
            judgment: conditional
            conclusion: 단계별 체크리스트를 통해 논문 v1에서 확인한 범위만 판정한다.
            conditions:
            - 공개 정보 기반 보수적 팀 추정
            evidence_ids:
            - SW-kernel
            - SW-implementation
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: global
            domain_relevance: direct
          trl_checks:
            '1':
              status: met
              reason: 원리와 목적 함수의 문서화된 근거
              evidence_ids:
              - SW-principle
            '2':
              status: met
              reason: 비트 배정 및 TriZone 적용 개념을 구체화
              evidence_ids:
              - SW-principle
            '3':
              status: met
              reason: 벤치마크로 압축 접근의 작동을 검증한 저자 보고
              evidence_ids:
              - SW-quality
            '4':
              status: met
              reason: 핵심 압축·디코드 구성요소의 GPU 통합 실험을 보고
              evidence_ids:
              - SW-implementation
            '5':
              status: unknown
              reason: 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인
              evidence_ids: []
            '6':
              status: unknown
              reason: 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인
              evidence_ids: []
            '7':
              status: unknown
              reason: 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인
              evidence_ids: []
            '8':
              status: unknown
              reason: 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인
              evidence_ids: []
            '9':
              status: unknown
              reason: 보수적 팀 기준의 목표 운영 환경·시스템 검증 증거 미확인
              evidence_ids: []
        HW-01:
          status: completed
          items:
          - criterion_id: mechanism
            judgment: conditional
            conclusion: 저자는 광학 패브릭과 CXL 호스트 인터페이스로 공유 메모리 어플라이언스 구조를 제안한다.
            conditions:
            - 물리 배포 완료가 아닌 제안 구조
            evidence_ids:
            - HW-architecture
            basis: fact
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: global
            domain_relevance: direct
          - criterion_id: validation_scope
            judgment: conditional
            conclusion: PF 경로는 에뮬레이션, 서빙은 시뮬레이션으로 평가했으며 실제 PF 장비의 종단간 검증은 미완료로 명시한다.
            conditions:
            - 기존 GPU/DRAM 실험을 PF 장비의 실측으로 대체하지 않음
            evidence_ids:
            - HW-emulation
            - HW-serving
            - HW-pending
            basis: fact
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: global
            domain_relevance: direct
          - criterion_id: maturity
            judgment: conditional
            conclusion: 하드웨어 구조의 개념 검증과 물리 어플라이언스 실증을 분리한다.
            conditions:
            - 공개 정보 기반 보수적 팀 추정
            evidence_ids:
            - HW-emulation
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: global
            domain_relevance: direct
          trl_checks:
            '1':
              status: met
              reason: 공유 메모리·광학 연결의 구조적 원리 제시
              evidence_ids:
              - HW-architecture
            '2':
              status: met
              reason: PF-NIC·메모리 모듈·호스트 적용 구조 정의
              evidence_ids:
              - HW-architecture
            '3':
              status: met
              reason: PF-NIC 및 메모리 모듈의 에뮬레이션 기반 개념 검증
              evidence_ids:
              - HW-emulation
            '4':
              status: unknown
              reason: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
              evidence_ids: []
            '5':
              status: unknown
              reason: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
              evidence_ids: []
            '6':
              status: unknown
              reason: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
              evidence_ids: []
            '7':
              status: unknown
              reason: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
              evidence_ids: []
            '8':
              status: unknown
              reason: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
              evidence_ids: []
            '9':
              status: unknown
              reason: 물리 PF 어플라이언스의 종단간 검증이 향후 과제여서 상위 단계를 보류
              evidence_ids: []
    market:
      round: 0
      status: completed
      results:
        SW-01:
          status: unknown
          items:
          - criterion_id: market_size_growth
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - RDKV 고유 시장의 규모·성장률·지역·기간은 두 논문 범위에서 확인하지 못했다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: commercialization
            judgment: conditional
            conclusion: 별도 메모리 장비보다 추론 소프트웨어 기능으로 제공하는 사업화 경로를 가정할 수 있다. 판매 제품이 확인된 것은 아니다.
            conditions:
            - 커널 통합과 배포 권한을 별도 확인해야 하는 사업화 가설
            evidence_ids:
            - SW-kernel
            - SW-impact
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: adoption
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - 실제 유료 고객·상용 배포를 증명하는 자료를 이번 입력에 확보하지 않았다. 미채택이라는 뜻은 아니다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: ecosystem
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - 논문에서 비교에 사용한 오픈소스 기준선을 RDKV의 공식 프레임워크 지원으로 간주할 수 없다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: cost
            judgment: conditional
            conclusion: 기존 GPU의 메모리 사용을 줄이면 증설 부담을 완화할 가능성이 있지만, 통합 인건비를 포함한 실제 총비용 절감은 미확인이다.
            conditions:
            - 목표 품질 유지 및 통합 비용이 메모리 절감 편익을 상쇄하지 않을 때
            evidence_ids:
            - SW-memory
            - SW-kernel
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: customer_value
            judgment: conditional
            conclusion: 메모리가 부족한 QA 운영자에게 기존 장비에서 긴 문맥을 처리할 가능성이 고객 가치가 된다.
            conditions:
            - 운영비 절감은 추론이며 품질 허용치 검증 전에는 경제적 이익을 확정하지 않음
            evidence_ids:
            - SW-memory
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          trl_checks: {}
        HW-01:
          status: unknown
          items:
          - criterion_id: market_size_growth
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - Photonic-CXL 어플라이언스 고유 시장의 규모·성장률은 두 논문만으로 확인하지 못했다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: commercialization
            judgment: conditional
            conclusion: 메모리 어플라이언스와 호스트 어댑터를 공급하는 사업화 경로를 가정할 수 있으나, 논문은 실장비 검증을 향후 과제로 남긴다.
            conditions:
            - 제품 구조 제안과 출시·판매 증거를 구분
            evidence_ids:
            - HW-architecture
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: adoption
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - 이 어플라이언스의 실제 고객 도입 증거를 확보하지 않았다. 관련 CXL 제품의 도입을 대신 쓰지 않는다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: ecosystem
            judgment: conditional
            conclusion: vLLM·SGLang·Dynamo 연결 방안을 제시하지만, vLLM 커넥터는 구현 예정 표현이므로 공식 통합 완료로 볼 수 없다.
            conditions:
            - v1에서 제안한 통합 경로만 평가
            evidence_ids:
            - HW-integration
            - HW-pending
            basis: fact
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: cost
            judgment: conditional
            conclusion: 공유 메모리로 증설을 줄일 가능성과 전용 장비·어댑터·광학 인프라 투자 부담을 함께 검토해야 한다. 비용·편익 분석은 논문의 향후 과제다.
            conditions:
            - 장비 가격·전력·유지보수와 서버 추가 구매 대안의 비용을 확보한 뒤 비교
            evidence_ids:
            - HW-architecture
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: customer_value
            judgment: conditional
            conclusion: 반복 문맥의 캐시 축출·재계산이 병목인 운영자에게 응답시간 안정화의 잠재 가치가 있다.
            conditions:
            - 캐시 재사용이 높은 시뮬레이션 조건이며 모든 QA 요청의 효과를 보장하지 않음
            evidence_ids:
            - HW-serving
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          trl_checks: {}
    stakeholders:
      round: 0
      status: completed
      results:
        SW-01:
          status: unknown
          items:
          - criterion_id: competitors
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - 경쟁사의 RDKV 지지·반대 원문을 확보하지 않았다. 비교 벤치마크는 경쟁사의 반응이 아니다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: adopters
            judgment: conditional
            conclusion: 운영자는 메모리 절감을 편익으로 볼 수 있지만, QA 품질 변화와 서비스 검증 비용도 부담할 수 있다.
            conditions:
            - 운영자의 실제 인터뷰가 아닌 논문으로부터 도출한 이해관계 추론
            evidence_ids:
            - SW-memory
            - SW-quality
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: developers
            judgment: conditional
            conclusion: 개발자는 TriZone 커널·캘리브레이션·압축 예산을 통합하고 품질 회귀를 점검해야 할 것으로 해석된다.
            conditions:
            - 실제 개발자 반응이 아닌 구현 요구에 대한 추론
            evidence_ids:
            - SW-kernel
            - SW-implementation
            - SW-limit
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: investors_analysts_media
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - RDKV에 대한 투자·애널리스트·미디어의 직접 평가를 확보하지 않았다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          trl_checks: {}
        HW-01:
          status: unknown
          items:
          - criterion_id: competitors
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - 타 공급자의 Photonic-CXL에 대한 찬반 입장을 확보하지 않았다. 저자의 관련 기술 비교는 직접 반응이 아니다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: adopters
            judgment: conditional
            conclusion: 운영자는 캐시 재사용 편익과 전용 장비의 조달·운용·비용 불확실성을 함께 고려할 수 있다.
            conditions:
            - 실제 고객 도입 의견이 아닌 이해관계 추론
            evidence_ids:
            - HW-serving
            - HW-architecture
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: developers
            judgment: conditional
            conclusion: 개발자는 프레임워크 커넥터와 공유 메모리의 인덱스·일관성 처리를 구현·검증해야 할 것으로 해석된다.
            conditions:
            - 공급자 저자의 설계 설명에서 추론하며 외부 개발자의 지지로 해석하지 않음
            evidence_ids:
            - HW-integration
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          - criterion_id: investors_analysts_media
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - Photonic-CXL에 대한 독립 투자·애널리스트·미디어 평가를 확보하지 않았다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: indirect
          trl_checks: {}
    domain:
      round: 0
      status: completed
      results:
        SW-01:
          status: unknown
          items:
          - criterion_id: capacity
            judgment: conditional
            conclusion: 저자가 보고한 압축 캐시의 메모리 절감은 HBM 부족 완화의 근거가 된다.
            conditions:
            - 원문 모델·장비·문맥·압축 예산 범위에서의 보고이며 목표 서비스에서 재검증
            evidence_ids:
            - SW-memory
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: quality
            judgment: conditional
            conclusion: 압축 방식이므로 FullKV와 동일 품질을 보장하지 않는다. RULER의 긴 문맥 조건에서 FullKV보다 낮은 결과도 확인된다.
            conditions:
            - 문서 QA의 정답률·근거 회수율 허용 손실을 별도 정의해야 함
            evidence_ids:
            - SW-quality
            basis: fact
            counter_evidence:
            - '긴 문맥 조건의 품질 손실: FullKV보다 낮은 RULER 결과가 보고됨'
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: latency
            judgment: conditional
            conclusion: 압축 상태를 유지하는 커널 경로가 지연 개선의 조건이며, 단순 저비트 저장만으로 서비스 지연 개선을 확정할 수 없다.
            conditions:
            - 통합된 커널의 목표 장비 지연 및 상위 백분위 지연을 실측해야 함
            evidence_ids:
            - SW-kernel
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: throughput
            judgment: unknown
            conclusion: 판단 보류
            conditions:
            - 조사 범위는 선정 논문 v1 두 편에 한정
            evidence_ids: []
            basis: inference
            gaps:
            - 목표 QA 서비스의 다중 사용자 동시성·처리량 요구값과 운영 측정 자료를 확보하지 않았다.
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: gpu_compatibility
            judgment: conditional
            conclusion: 기존 NVIDIA GPU에서 구현 실험을 수행한 근거는 있으나 모든 GPU·엔진에서 호환된다는 뜻은 아니다.
            conditions:
            - 원문에 보고된 장비에서 목표 장비·서빙 엔진으로 이식 검증
            evidence_ids:
            - SW-implementation
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: hardware_dependency
            judgment: conditional
            conclusion: 논문의 구현은 별도 광학 메모리 어플라이언스가 아닌 GPU와 압축 커널을 사용한다.
            conditions:
            - 특정 커널·장비 의존성을 무시한 범용 호환성으로 확대하지 않음
            evidence_ids:
            - SW-implementation
            - SW-kernel
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: deployment
            judgment: conditional
            conclusion: TriZone과 캘리브레이션을 기존 서빙 경로에 통합하고 품질·지연 회귀 검사를 수행해야 한다.
            conditions:
            - 실제 엔진 연결 난이도·개발 기간은 미측정
            evidence_ids:
            - SW-kernel
            - SW-implementation
            basis: inference
            counter_evidence:
            - TriZone 통합·캘리브레이션·회귀 검증 부담
            gaps:
            - 실제 통합 인건비와 서비스 환경의 운용 검증 자료 부족
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: maturity
            judgment: conditional
            conclusion: 논문에 구현·실험 근거가 있어도 상용 QA 서비스의 운용 검증과 같지는 않다.
            conditions:
            - TRL 숫자는 technical 체크리스트 결과를 사용
            evidence_ids:
            - SW-implementation
            - SW-limit
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: customer_value
            judgment: conditional
            conclusion: 같은 장비의 문맥 처리 여지를 늘리는 편익은 QA 품질이 허용 범위에 남을 때 유효하다.
            conditions:
            - 시장 관점의 메모리 편익에 QA 품질 조건을 추가
            evidence_ids:
            - SW-memory
            - SW-quality
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: domain_fit
            judgment: conditional
            conclusion: 기존 GPU 기반 장문맥 QA의 메모리 절감 후보이나, 목표 QA 품질과 TriZone 통합 검증이 선행되어야 한다.
            conditions:
            - 긴 입력·상대적으로 짧은 생성이며 품질 손실을 별도 검증하는 환경
            evidence_ids:
            - SW-memory
            - SW-quality
            - SW-kernel
            - SW-limit
            basis: inference
            counter_evidence:
            - prefill 후 비트 배정을 고정하며 생성 중 attention 변화에 따른 재평가를 하지 않음
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          trl_checks: {}
        HW-01:
          status: completed
          items:
          - criterion_id: capacity
            judgment: conditional
            conclusion: 공유 메모리 확장은 KV 수용량 부족을 완화하는 설계이나, 논문 구조의 실제 설치 성능과는 구분한다.
            conditions:
            - 대상 호스트 연결·용량 배분·실장비 준비가 필요
            evidence_ids:
            - HW-architecture
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: quality
            judgment: conditional
            conclusion: KV를 보관·재사용하는 방향은 압축 손실 회피에 의미가 있으나, 문서 QA 정답 정확성을 보장하거나 검증한 것은 아니다.
            conditions:
            - 데이터 보존과 모델 답변 정확성을 분리하고 QA 벤치마크를 별도 수행
            evidence_ids:
            - HW-serving
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: latency
            judgment: conditional
            conclusion: 캐시 재사용에 따른 응답시간 편익은 호스트 대역폭·접근 경로와 워크로드에 의존한다.
            conditions:
            - 서빙 시뮬레이션을 실제 서비스의 지연 SLO 충족으로 간주하지 않음
            evidence_ids:
            - HW-host-limit
            - HW-serving
            basis: inference
            counter_evidence:
            - 단일 CXL 호스트 경로의 대역폭 제약과 캐시 재사용 패턴 의존
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: throughput
            judgment: conditional
            conclusion: 대화 수 증가 시 캐시 축출 완화 결과는 확장 가능성의 근거이나 실제 운영 처리량을 확정하지 못한다.
            conditions:
            - 프리픽스 재사용이 있는 대화 부하와 실제 QA 요청 분포의 차이를 검증
            evidence_ids:
            - HW-serving
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: gpu_compatibility
            judgment: conditional
            conclusion: PF-NIC를 통한 호스트 연결 경로를 제안한다. 모든 GPU를 새로 설계해야 한다는 결론은 이 논문에서 도출하지 않는다.
            conditions:
            - 호스트 PCIe/CXL·DMA·펌웨어·소프트웨어 통합 조건을 별도 확인
            evidence_ids:
            - HW-architecture
            - HW-integration
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: hardware_dependency
            judgment: conditional
            conclusion: 전용 메모리 모듈·PF-NIC·외부 광원 등 추가 인프라가 필요하다.
            conditions:
            - 기존 GPU만으로 소프트웨어 설치 즉시 사용할 수 있는 방식이 아님
            evidence_ids:
            - HW-architecture
            basis: fact
            counter_evidence:
            - 전용 메모리 모듈·PF-NIC·외부 광원 등 인프라 의존
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: deployment
            judgment: conditional
            conclusion: 물리 인프라와 프레임워크 커넥터·공유 인덱스·일관성 프로토콜의 통합 검증이 필요하다.
            conditions:
            - 논문의 통합 설계를 실제 완료된 운영 구성으로 간주하지 않음
            evidence_ids:
            - HW-architecture
            - HW-integration
            - HW-pending
            basis: inference
            counter_evidence:
            - 물리 PF 장비와 프레임워크 커넥터의 종단간 통합 미검증
            gaps:
            - 실배포·장비 가격·운영비·비용 편익 분석 자료 부족
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: maturity
            judgment: conditional
            conclusion: 에뮬레이션·시뮬레이션 근거를 실제 PF 어플라이언스 운용 실증과 구분한다.
            conditions:
            - TRL 숫자는 technical 체크리스트 결과를 사용
            evidence_ids:
            - HW-emulation
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: customer_value
            judgment: conditional
            conclusion: 캐시 재계산 억제의 편익은 재사용 패턴과 실제 투자 비용에 따라 달라진다.
            conditions:
            - 재사용이 적은 QA나 비용 제한이 큰 환경에는 동일 편익을 가정하지 않음
            evidence_ids:
            - HW-serving
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          - criterion_id: domain_fit
            judgment: conditional
            conclusion: 반복 문맥을 재사용하는 고동시성 QA의 메모리 확장 후보이나, 실제 장비 검증·호스트 경로·비용 확인이 선행되어야 한다.
            conditions:
            - 반복 문맥·높은 동시성으로 캐시 수용량이 병목인 환경
            evidence_ids:
            - HW-serving
            - HW-host-limit
            - HW-integration
            - HW-pending
            basis: inference
            gaps: []
            need_more: []
            metrics: []
            analysis_scope: selected_domain
            domain_relevance: direct
          trl_checks: {}
  errors: {}
  review:
    round: 0
    dirty_roles:
    - technical
    - market
    - stakeholders
    - domain
~~~
