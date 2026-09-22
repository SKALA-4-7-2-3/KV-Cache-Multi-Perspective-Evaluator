"""Adapt real agent outputs to Review without inventing assessments or provenance.

The original run and agent artifacts remain the authoritative records. This
module selects their claims, translates field names, and records any information
that the older Review contract cannot express as explicit limitations.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

TECHS = ("SW-01", "HW-01")
DOMAIN_KEYS = {
    "latency_predictability": "latency",
    "dedicated_hardware_dependency": "hardware_dependency",
    "deployment_complexity": "deployment",
}


def _unique(values):
    return list(dict.fromkeys(str(v).strip() for v in values if v is not None and str(v).strip()))


def _plain(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _claims(value):
    if isinstance(value, dict):
        if isinstance(value.get("text"), str) and isinstance(value.get("evidence_ids"), list):
            yield value
        else:
            for child in value.values():
                yield from _claims(child)
    elif isinstance(value, list):
        for child in value:
            yield from _claims(child)


def _method(observation):
    mode = observation.get("evaluation_mode")
    if mode == "measured":
        return "gpu_experiment" if re.search(r"GPU|[AH][12]00|RTX|CUDA", observation.get("hardware") or "", re.I) else "measurement"
    return {"emulated": "emulation", "simulated": "simulation", "analytical": "analysis"}.get(mode, "unknown")


def _normalize_space(text):
    return " ".join(str(text).split())


class _Bridge:
    def __init__(self, bundle, request, results, run_id, as_of):
        self.bundle, self.request, self.results = bundle, request, results
        self.run_id, self.as_of = run_id, str(as_of)[:10]
        self.documents, self.evidence, self.attribution = {}, {}, {}
        self.collected_sources = []
        self.source_reports = []
        self.aliases, self.notes = {}, []
        self.source_run = bundle["run"].get("run", {})
        self.collected_at = self.source_run.get("finished_at") or self.source_run.get("started_at") or self.as_of
        domains = request.get("domains") or [{"id": "selected-domain", "name": "사용자 지정 도메인", "scenario": ""}]
        self.domain = domains[0]
        self.dossiers = list(bundle["dossiers"].values()) if isinstance(bundle["dossiers"], dict) else bundle["dossiers"]
        self.by_tech = {bundle["technology_map"][d["paper"]["paper_id"]]: d for d in self.dossiers}

    def resolve(self, eid):
        if eid in self.aliases:
            return self.aliases[eid]
        for tech in TECHS:
            if str(eid).startswith(tech + "::"):
                return self.aliases.get(str(eid)[len(tech) + 2:], str(eid)[len(tech) + 2:])
        return eid

    def valid_ids(self, ids, tech):
        from team_review.schema import Document, Evidence, source_is_available
        valid = []
        for original in ids:
            eid = self.resolve(original)
            entry = self.evidence.get(eid)
            if entry and tech in entry["technology_ids"]:
                doc = Document.model_validate(self.documents[entry["doc_id"]])
                if source_is_available(Evidence.model_validate(entry), doc):
                    valid.append(eid)
        return _unique(valid)

    def sources(self):
        methods = {}
        author_metadata = json.loads(Path(__file__).with_name("paper_authors.json").read_text())
        for tech, dossier in self.by_tech.items():
            paper = dossier["paper"]
            arxiv_id = paper.get("arxiv_id")
            url = paper.get("url") or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None)
            if not url:
                raise ValueError(f"{tech}: saved paper metadata has no resolvable source URL")
            self.documents[tech] = {
                "title": paper["title"], "url": url, "version": paper.get("version") or "unknown",
                "pages": paper["page_count"], "sha256": paper["source_hash"], "kind": "paper",
                "published_at": paper.get("published_at"), "retrieved_at": self.collected_at,
                "source_type": "paper", "citation_key": "SW01_RDKV" if tech == "SW-01" else "HW01_PHOTONIC_CXL",
            }
            supplemental = author_metadata.get(str(arxiv_id).split("v")[0], {})
            authors = paper.get("authors") or supplemental.get("authors", [])
            self.attribution[tech] = {"authors": ", ".join(authors) or "unknown", "venue_or_site": "arXiv"}
            if not paper.get("authors") and supplemental:
                self.attribution[tech]["authors_source"] = supplemental["source_url"]
                self.attribution[tech]["authors_checked_at"] = supplemental["checked_at"]
            for observation in dossier.get("experiment_observations", []):
                for eid in observation.get("evidence_ids", []):
                    methods.setdefault(eid, set()).add(_method(observation))
        for eid, raw in self.bundle["evidence"].items():
            tech = self.bundle["technology_map"].get(raw.get("document_id"))
            if not tech:
                continue
            locator = raw.get("locator") or {}
            excerpt = raw.get("snippet") or ""
            if not excerpt or not locator.get("physical_page"):
                continue
            source_hash = locator.get("document_sha256")
            inherited = self.bundle["run"].get("status") == "succeeded" and source_hash == self.documents[tech]["sha256"]
            self.aliases[eid] = eid
            self.evidence[eid] = {
                "id": eid, "doc_id": tech, "technology_ids": [tech], "excerpt": excerpt,
                "page": locator["physical_page"], "location": " / ".join(locator.get("section_path") or []) or locator.get("element_id"),
                "method": next(iter(methods[eid])) if len(methods.get(eid, set())) == 1 else "unspecified",
                "verified_source": False, "synthetic": False, "collected_at": self.collected_at,
                "independence": "author", "technology_relevance": "direct", "conditions": [],
                "source_verification": "inherited_source_record" if inherited else "unverified",
                "provenance": {"source_hash": source_hash, "original_evidence_id": eid,
                    "source_run_status": self.bundle["run"].get("status"),
                    "source_run_id": self.source_run.get("run_id"), "locator": locator,
                    "content_hash": raw.get("content_hash"), "pdf_reverified_this_run": False},
            }
        # Legacy projections may add aliases, but the original evidence IDs are canonical.
        for paper in self.bundle.get("papers", []):
            for entry in paper.get("evidence_registry", []):
                eid = entry.get("evidence_id")
                original = entry.get("original_evidence_id") or eid
                if original in self.evidence:
                    self.aliases[eid] = original

    def web_sources(self, role, raw_sources, supports):
        for key, value in raw_sources.items():
            raw = _plain(value)
            eid = raw.get("id") or key
            upstream = raw.get("upstream") or {}
            original = upstream.get("evidence_id") or eid
            if original in self.evidence:
                self.aliases[eid] = original
                continue
            excerpt = raw.get("excerpt") or ""
            url = raw.get("url") or ""
            techs = [t for t in raw.get("technology_ids", raw.get("tech_ids", [])) if t in TECHS]
            quotes = _unique(supports.get(eid, []))
            matching = [q for q in quotes if _normalize_space(q) in _normalize_space(excerpt)]
            audit = raw.get("audit") or {}
            # Forward every source URL, including uncited/partial collections.
            # Full fetched content remains in the originating agent's output.
            source_metadata = {
                "source_id": f"{role}:{eid}", "evidence_id": eid, "role": role,
                "title": raw.get("title"), "url": url,
                "publisher": raw.get("publisher"), "author": raw.get("author"),
                "published_at": raw.get("published_at"), "retrieved_at": raw.get("retrieved_at"),
                "technology_ids": techs,
                "usage_status": "cited" if matching else "collected_not_cited",
                "collection_status": raw.get("access_status") or ("excerpt_available" if excerpt else "content_unavailable"),
            }
            self.collected_sources.append(source_metadata)
            if not excerpt or not url.startswith(("https://", "http://")) or not techs:
                continue
            acceptable = not audit or audit.get("decision") in {"use", "limited"}
            acquired = raw.get("access_status") == "full_text" or bool(raw.get("collected_content_sha256"))
            available = bool(matching) and acceptable and acquired
            # Hash the actual persisted excerpt, never an invented whole-document hash.
            digest = sha256(excerpt.encode()).hexdigest()
            did = f"{role}-source-{sha256((url + digest).encode()).hexdigest()[:16]}"
            source_type = raw.get("source_type")
            allowed_types = {"paper", "official_product", "standard", "news", "market_report", "community"}
            if source_type not in allowed_types:
                source_type = {"supplier_publication": "official_product", "standard": "standard",
                    "research": "paper", "reporting": "news", "commentary": "community"}.get(audit.get("document_type"), "unknown")
            self.documents[did] = {
                "title": raw.get("title") or url, "url": url, "version": "collected-excerpt",
                "pages": None, "sha256": digest, "kind": "web", "source_type": source_type,
                "published_at": raw.get("published_at"), "retrieved_at": str(raw.get("retrieved_at") or self.as_of),
                "citation_key": "WEB_" + sha256(did.encode()).hexdigest()[:12],
            }
            self.attribution[did] = {"authors": raw.get("author") or raw.get("publisher") or "unknown",
                                     "venue_or_site": raw.get("publisher") or "unknown"}
            canonical = eid if eid not in self.evidence else f"{role}::{eid}"
            self.aliases[eid] = canonical
            retained = "\n[…]\n".join(matching) if matching else excerpt
            scope = raw.get("scope") or audit.get("relevance")
            self.evidence[canonical] = {
                "id": canonical, "doc_id": did, "technology_ids": techs, "excerpt": retained,
                "page": None, "location": raw.get("location") or raw.get("locator") or "수집 본문 내 인용 구절",
                "method": "statement", "verified_source": False, "synthetic": False,
                "collected_at": str(raw.get("retrieved_at") or self.as_of),
                "independence": "unknown", "technology_relevance": "direct" if scope in {"direct", "exact"} else "indirect",
                "conditions": [], "source_verification": "collected_excerpt" if available else "unverified",
                "provenance": {"collector": role, "quote_matched": bool(matching), "original_evidence_id": eid,
                    "collected_excerpt_sha256": digest, "source_audit": audit,
                    "original_source_type": raw.get("source_type"), "pdf_reverified_this_run": False},
            }
            source_metadata.update(evidence_id=canonical, reference_id=did,
                                   citation_key=self.documents[did]["citation_key"])
            # Keep the collector's actual text available for attributed analysis.
            # This does not promote it to verified evidence or a confirmed finding.
            self.source_reports.append({
                **source_metadata,
                "excerpt": re.sub(r"!\[[^\]]*\]\(data:[^\s)]+\)", "", excerpt),
                "source_audit": audit,
                "review_status": "source_report_not_independently_verified",
                "usage_note": "실제 수집 본문에서 관련 내용을 분석해 인용할 수 있습니다. 업체 주장·인접 기술 사례는 해당 출처에 귀속하고, 메뉴·탐색 문구만 있거나 관련 없는 자료는 사용하지 않습니다.",
            })

    def item(self, tech, cid, conclusion, ids=(), *, judgment="conditional", basis="inference",
             conditions=(), gaps=(), findings=(), risks=(), relevance="direct", **extra):
        from team_review.schema import Assessment
        valid = self.valid_ids(ids, tech)
        invalid = set(map(self.resolve, ids)) - set(valid)
        gaps = list(gaps)
        if invalid:
            gaps.append("원문 연결 상태를 확인할 수 없는 인용은 확정 근거에서 제외: " + ", ".join(sorted(invalid)))
        if not valid or judgment in {"unknown", "failed"}:
            judgment, basis = "unknown", "unknown"
            gaps = gaps or ["이 기준의 판정에 필요한 근거가 제공되지 않았습니다."]
        elif judgment in {"favorable", "unfavorable", "met"}:
            # A source's positive/negative result is not a missing user target's pass/fail result.
            gaps.append(f"상위 판정 {judgment}는 보존하되 사용자 요구값 충족을 확정하지 않고 조건부로 전달합니다.")
            judgment = "conditional"
        conditions = _unique(conditions) or ["제공된 출처의 관찰·보고 범위에 한정하며 대상 운영 환경의 요구 충족은 별도 확인이 필요합니다."]
        return Assessment(criterion_id=cid, judgment=judgment, conclusion=conclusion or "판단 보류",
            evidence_ids=valid, basis=basis, conditions=conditions, gaps=_unique(gaps),
            reported_findings=_unique(findings), counter_evidence=_unique(risks),
            technology_relevance=relevance, analysis_scope="selected_domain", domain_relevance="direct",
            **extra).model_dump(mode="json")

    def role(self, cells, status="completed", demo=False):
        status = status if status in {"completed", "unknown", "failed"} else "completed"
        return {"round": 0, "status": status, "demo": demo,
                "results": {tech: {"status": status, "items": items} for tech, items in cells.items()}}

    def technical(self):
        cells = {}
        for tech, dossier in self.by_tech.items():
            overview = dossier.get("analysis", {}).get("technical_overview", {})
            mechanism = list(_claims({k: overview.get(k, []) for k in ("problem_definition", "core_approach", "mechanisms", "novelty")}))[:7]
            if not mechanism:
                mechanism = list(_claims(overview))[:7]
            scope = list(_claims(dossier.get("analysis", {}).get("scope", {})))[:8]
            observations = dossier.get("experiment_observations", [])[:8]
            limitations = list(_claims(dossier.get("analysis", {}).get("limitations", {})))[:6]
            mech_text = " ".join(c["text"] for c in mechanism)
            scope_text = " ".join(c["text"] for c in scope)
            observation_text = [json.dumps({k: o.get(k) for k in ("metric", "value", "value_min", "value_max", "unit", "baseline", "model", "hardware", "context_length", "concurrency", "workload", "evaluation_mode")}, ensure_ascii=False) for o in observations]
            scope_ids = [e for c in scope + limitations for e in c.get("evidence_ids", [])] + [e for o in observations for e in o.get("evidence_ids", [])]
            items = [self.item(tech, "mechanism", mech_text, [e for c in mechanism for e in c.get("evidence_ids", [])],
                              basis="mixed" if any(c.get("claim_type") == "analyst_inference" for c in mechanism) else "fact"),
                     self.item(tech, "validation_scope", scope_text or "논문이 보고한 관찰 조건과 한계를 함께 검토합니다.", scope_ids,
                              basis="mixed", findings=observation_text, risks=[c["text"] for c in limitations],
                              gaps=["기술 조사 저장 결과를 재사용했으며 이번 실행에서 원본 PDF와 실험을 재검증하지 않았습니다."]),
                     self.item(tech, "maturity", "TRL 판단 보류", judgment="unknown",
                              gaps=["저장된 기술 조사 결과에는 TRL 1~9 단계별 판정이 없으므로 숫자를 새로 추정하지 않습니다."])]
            cells[tech] = items
        result = self.role(cells, self.bundle["run"].get("status"))
        for cell in result["results"].values():
            cell["trl_checks"] = {level: {"status": "unknown", "reason": "원본 조사 결과에 단계별 TRL 판정이 제공되지 않음", "evidence_ids": []} for level in range(1, 10)}
        return result

    def domain_result(self):
        from team_review.rubric import CRITERIA
        output = self.results["domain"].get("assessments", {}).get("domain", self.results["domain"])
        by_tech = {r["technology_id"]: r for r in output.get("assessments", [])}
        cells = {}
        for tech in TECHS:
            raw = by_tech.get(tech, {})
            by_key = {DOMAIN_KEYS.get(r["criterion_id"], r["criterion_id"]): r for r in raw.get("criteria", [])}
            cells[tech] = []
            for cid in CRITERIA["domain"]:
                row = by_key.get(cid, {})
                gaps = list(row.get("gaps", [])) + ["추가 확인 질문: " + q for q in row.get("need_more", [])]
                cells[tech].append(self.item(tech, cid, row.get("conclusion", "판단 보류"), row.get("evidence_ids", []),
                    judgment=row.get("judgment", "unknown"), basis={"none": "unknown"}.get(row.get("basis"), row.get("basis", "unknown")),
                    conditions=row.get("conditions", []), gaps=gaps,
                    findings=[row["rationale"]] if row.get("rationale") else [], risks=raw.get("key_tradeoffs", []) if cid == "domain_fit" else []))
        return self.role(cells, output.get("status"))

    def market_result(self):
        from team_review.rubric import CRITERIA
        container = self.results["market"]
        output = _plain(container.get("result", container))
        rows = [_plain(r) for r in output.get("assessments", [])]
        supports = {}
        for row in rows:
            citations = list(row.get("citations", []))
            citations += [c for finding in row.get("context_findings", []) for c in finding.get("citations", [])]
            for cite in citations:
                supports.setdefault(cite["evidence_id"], []).append(cite.get("quote", ""))
        self.web_sources("market", container.get("evidence", {}), supports)
        source_keys = {"ecosystem": {"ecosystem_support", "standardization"}, "cost": {"business_value"}, "customer_value": {"business_value"}}
        cells = {}
        for tech in TECHS:
            cells[tech] = []
            for cid in CRITERIA["market"]:
                selected = [r for r in rows if r.get("tech_id") == tech and r.get("criterion_id") in source_keys.get(cid, {cid})]
                findings = [r["judgment"] for r in selected if r.get("judgment")]
                findings += [f["statement"] for r in selected for f in r.get("context_findings", [])]
                ids = [eid for r in selected for eid in r.get("evidence_ids", [])]
                ids += [c["evidence_id"] for r in selected for f in r.get("context_findings", []) for c in f.get("citations", [])]
                gaps = [g for r in selected for g in r.get("gaps", []) + r.get("unknown_reasons", [])]
                known = [r for r in selected if r.get("verdict") not in {None, "unknown"}]
                verdict = "conditional" if known else "unknown"
                if cid in {"cost", "customer_value"}:
                    gaps.append("상위 business_value 항목을 비용/고객 가치로 연결한 것으로 두 개의 독립 조사 결과가 아닙니다.")
                cells[tech].append(self.item(tech, cid, " / ".join(findings) or "판단 보류", ids, judgment=verdict,
                    basis="mixed" if known else "unknown", findings=findings,
                    conditions=[c for r in selected for c in r.get("conditions", [])], gaps=gaps,
                    relevance="direct" if selected and all(r.get("relation_to_technology") == "exact" for r in selected) else "indirect"))
        status = output.get("status")
        if status == "failed" and container.get("retained_draft_findings"):
            status = "unknown"
        return self.role(cells, status, demo=output.get("mode") not in {None, "live"})

    def stakeholder_result(self):
        from team_review.rubric import OPERATING_ORGANIZATION_CRITERIA
        output = self.results["stakeholders"]
        by_tech = output.get("result", {}).get("by_technology", {})
        supports = {}
        for value in by_tech.values():
            for claim in value.get("claims", []):
                for support in claim.get("supports", []):
                    supports.setdefault(support["evidence_id"], []).append(support["quote"])
        self.web_sources("stakeholders", output.get("evidence", {}), supports)
        cells = {}
        aspects = {"benefits": {"benefit"}, "burdens": {"burden"}, "adoption_conditions": {"adoption_condition"}, "observations": {"reaction", "evaluation"}}
        labels = {"paper_report": "논문 보고", "statement": "당사자 발언", "inference": "조건부 분석 추론"}
        for tech in TECHS:
            source = by_tech.get(tech, {})
            cells[tech] = []
            for cid in OPERATING_ORGANIZATION_CRITERIA:
                claims = [c for c in source.get("claims", []) if c.get("aspect") in aspects[cid]]
                descriptions = [f"[{labels.get(c.get('kind'), '출처 보고')}; 발언 주체: {c.get('actor') or '해당 없음'}] {c['text']}" for c in claims]
                kinds = {c.get("kind") for c in claims}
                basis = "opinion" if kinds == {"statement"} else "fact" if kinds == {"paper_report"} else "inference" if kinds == {"inference"} else "mixed"
                ids = [eid for c in claims for eid in c.get("evidence_ids", [])]
                gaps = list(source.get("gaps", []))
                if not claims:
                    gaps.append("요청한 운영 조직 관점에서 해당 유형의 근거 연결된 결과가 제공되지 않았습니다.")
                gaps.append("출처의 편익·부담 관찰은 사용자 요구조건 충족 판정이나 운영 조직의 실제 도입 결정이 아닙니다.")
                cells[tech].append(self.item(tech, cid, " / ".join(descriptions) or "판단 보류", ids,
                    judgment="conditional" if claims else "unknown", basis=basis,
                    conditions=[c.get("condition", "") for c in claims], gaps=gaps, findings=descriptions,
                    risks=descriptions if cid == "burdens" else [],
                    relevance="direct" if claims and all(c.get("source_scope") == "direct" for c in claims) else "indirect",
                    stakeholder_group="클라우드 데이터센터 LLM 추론 서비스 운영 조직",
                    attributed_to=" / ".join(_unique(c.get("actor") for c in claims)) or None))
        status = output.get("execution_status")
        if status == "failed" and output.get("retained_draft_findings"):
            status = "unknown"
        return self.role(cells, status, demo=output.get("mode") not in {None, "live"})


def build_review_state(bundle, request, results, *, run_id, as_of) -> dict[str, Any]:
    """Create a genuine, provenance-labelled Review input from stored/live results."""
    bridge = _Bridge(bundle, request, results, run_id, as_of)
    bridge.sources()
    assessments = {"technical": bridge.technical(), "market": bridge.market_result(),
                   "stakeholders": bridge.stakeholder_result(), "domain": bridge.domain_result()}
    from team_review.schema import Document, Evidence, RoleResult
    # Boundary parsing is part of making the actual pipeline callable, not a test suite.
    for role, value in assessments.items():
        assessments[role] = RoleResult.model_validate(value).model_dump(mode="json")
    for value in bridge.documents.values():
        Document.model_validate(value)
    for value in bridge.evidence.values():
        Evidence.model_validate(value)
    request_text = "\n".join(str(request.get(k) or "") for k in ("original_request", "objective", "additional_context"))
    requirements = request.get("requirements") or {}
    notice = ("기술 조사 Agent의 저장된 실제 실행 결과와 원문 위치·해시 기록을 재사용했습니다. "
              "이번 실행에서 Research, 원본 PDF 재검증 또는 성능 재현을 수행하지 않았습니다. "
              "inherited_source_record는 저장된 원문 연결 기록의 계승이며 새로운 독립 검증이 아닙니다. "
              "원본 자료에 논문 버전이 없으면 unknown으로 유지합니다. 시장·이해관계자·도메인 결과의 미확인은 그대로 남깁니다.")
    return {
        "config": {"run_id": run_id, "domain": bridge.domain["name"], "demo": False,
            "attribution_first": True, "collected_sources": bridge.collected_sources,
            "usable_source_reports": bridge.source_reports,
            "upstream_draft_findings": [dict(finding, role=role)
                for role in ("market", "stakeholders")
                for finding in results[role].get("retained_draft_findings", [])],
            "upstream_review_notes": [{"role": role, "note": note}
                for role in ("market", "stakeholders")
                for note in results[role].get("review_notes", [])],
            "upstream_statuses": {"stakeholders": results["stakeholders"].get("execution_status"),
                "market": results["market"].get("result", {}).get("status")},
            "raw_domain_input": request_text, "normalized_domain": {"id": bridge.domain["id"], "name": bridge.domain["name"]},
            "evaluation_as_of": bridge.as_of, "requirements": {str(k): str(v) for k, v in requirements.items()},
            "domain_requirements": deepcopy(requirements), "source_attribution": bridge.attribution,
            "stakeholder_rubric": "operating_organization", "source_reuse": True, "source_reuse_notice": notice,
            "upstream_context_manifest": deepcopy(bundle.get("context_manifest", {})),
            "original_research_quality": deepcopy(bundle["run"].get("quality", {}))},
        "documents": bridge.documents, "evidence": bridge.evidence, "assessments": assessments, "errors": {},
        "review": {"round": 0},
    }


def run_review(state, *, model, draft=False) -> dict[str, Any]:
    """Run Review with source attribution and retained draft diagnostics.

Upstream repair requests are returned as diagnostics to the parent. This wrapper
does not claim that a role was rerun, manufacture a passed seal, or call Research.
"""
    from team_review import review_agent_node
    if draft:
        from team_review.markdown import review_handoff_node
        return review_handoff_node(deepcopy(state))
    actual = deepcopy(state)
    actual["config"]["synthesis_model"] = model
    return review_agent_node(actual)
