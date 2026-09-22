import unittest
from pathlib import Path

from market_agent.node import run_market, parent_update
from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.schemas import Limits
from market_agent.tools import Budget, ProviderError


INPUT = Path(__file__).parents[1] / "fixtures/input.md"


class GraphTests(unittest.TestCase):
    def test_execution_status_is_separate_from_unknown_market_verdicts(self):
        result=run_market(read_input(INPUT),FixtureWeb(),FixtureAnalyst(),mode='fixture')['result']
        self.assertEqual(result.status,'unknown')
        self.assertEqual(result.execution_status,'completed')
        self.assertEqual(result.output_schema_version,'0.4')

    def test_unsearched_criteria_make_execution_partial(self):
        result=run_market(read_input(INPUT),FixtureWeb(),FixtureAnalyst(),auto_repair=False,mode='fixture')['result']
        self.assertEqual(result.execution_status,'partial')

    def test_same_acronym_in_video_platform_or_profile_is_not_kv_cache_evidence(self):
        from market_agent.node import relevant_candidate
        tech = read_input(INPUT).technologies['SW-01']
        for row in [dict(title='RDKV development', content='Embedded software Comcast Sky video platform'),
                    dict(title='RDK Video documentation', content='RDKV build and license')]:
            self.assertFalse(relevant_candidate(row, tech))
        self.assertTrue(relevant_candidate(dict(title='RDKV', content='Rate-distortion KV cache quantization'), tech))

    def test_every_unknown_records_research_state_and_zero_budget_reason(self):
        data = read_input(INPUT).model_copy(update={'limits': Limits(search=0, extract=0, llm=0)})
        result = run_market(data, FixtureWeb(), FixtureAnalyst(), mode='fixture')['result']
        for row in result.assessments:
            self.assertEqual(row.research_status, 'not_started')
            self.assertIn('budget_exhausted', row.unknown_reasons)
            self.assertTrue(row.next_action)

    def test_first_round_keeps_extract_budget_for_repair_even_on_retries(self):
        class ManySources(FixtureWeb):
            def search(self, query, as_of):
                return [dict(url=f'https://example.org/{query[:3]}/{i}', title='KV cache CXL implementation',
                    content='KV cache product support', published_at=None) for i in range(3)]
            def extract(self, url):
                raise ProviderError('temporary', retryable=True)
        state = run_market(read_input(INPUT), ManySources(), FixtureAnalyst(), mode='fixture', auto_repair=False)
        self.assertLessEqual(state['result'].usage['extract'], 6)

    def test_repaired_validation_error_is_not_left_as_current_error(self):
        from market_agent.schemas import Claim, Citation, Extraction, SourceReview
        class SupportedWeb(FixtureWeb):
            def extract(self,url):
                return 'RDKV implementation is available under a research license.'
        class RepairedAnalyst(FixtureAnalyst):
            calls=0
            def extract(self,data,evidence,previous=None,issues=None):
                self.calls+=1
                web=[e for e in evidence.values() if e.access_status=='full_text' and e.content_status=='substantive']
                e=web[0]
                claim=Claim(tech_id='SW-01',criterion_id='commercialization',statement='연구 라이선스 구현 공개가 보고됨',
                    basis='fact',relation_to_technology='exact',conditions=['연구용'],metric=None,
                    citation=Citation(evidence_id=e.id,quote=e.excerpt if self.calls>1 else 'invented quote',
                        subject='RDKV',source_character='합성 자료'))
                return Extraction(claims=[claim],reviews=[SourceReview(evidence_id=x.id,
                    outcome='claims_extracted' if x.id==e.id else 'no_market_claim',reason='검토') for x in web])
            def compose(self,data,claims,previous=None,issues=None):
                answer=super().compose(data,claims)
                row=next(r for r in answer.assessments if r.tech_id=='SW-01' and r.criterion_id=='commercialization')
                row.basis,row.verdict,row.claim_ids='fact','conditional',list(claims)
                row.judgment,row.conditions='연구 라이선스 구현 공개가 보고됨',['연구용']
                return answer
        state=run_market(read_input(INPUT),SupportedWeb(),RepairedAnalyst(),mode='fixture')
        row=next(r for r in state['result'].assessments if r.tech_id=='SW-01' and r.criterion_id=='commercialization')
        self.assertEqual(row.basis,'fact')
        self.assertFalse(any(e['stage'] in {'claims','validate'} for e in state['result'].errors))

    def test_parent_evidence_is_not_mutated_when_source_is_shared(self):
        data = read_input(INPUT)
        first = run_market(data, FixtureWeb(), FixtureAnalyst(), auto_repair=False)
        external = {k: e.model_copy(deep=True) for k, e in first['evidence'].items()}
        before = {k: e.model_dump() for k, e in external.items()}
        run_market(data, FixtureWeb(), FixtureAnalyst(), existing_evidence=external, round_number=1)
        self.assertEqual(before, {k: e.model_dump() for k, e in external.items()})

    def test_fixture_runs_full_graph_and_repair_is_bounded(self):
        result = run_market(read_input(INPUT), FixtureWeb(), FixtureAnalyst(), mode="fixture")
        report = result["result"]
        self.assertEqual(len(report.assessments), 12)
        self.assertEqual(report.round, 1)
        self.assertEqual(report.usage["llm"], 2)
        self.assertLessEqual(report.usage["search"], 6)
        self.assertLessEqual(report.usage["extract"], 10)
        self.assertEqual(report.status, "unknown")
        self.assertTrue(result["sources"])
        self.assertEqual(sum(step.startswith('repair_') for step in result['history']), 1)
        self.assertEqual(result['history'][-1], 'finish')

    def test_zero_budget_returns_unknown_without_provider_calls(self):
        data = read_input(INPUT).model_copy(update={"limits": Limits(search=0, extract=0, llm=0)})
        result = run_market(data, FixtureWeb(), FixtureAnalyst(), mode="fixture")
        self.assertEqual(result["result"].usage, {"search": 0, "extract": 0, "llm": 0})
        self.assertEqual(result["result"].status, "unknown")
        self.assertTrue(all(a.basis == "unknown" for a in result["result"].assessments))

    def test_auth_failure_stops_followup_calls(self):
        class Unauthorized(FixtureWeb):
            def search(self, query, as_of):
                raise ProviderError("auth", fatal=True)
        result = run_market(read_input(INPUT), Unauthorized(), FixtureAnalyst(), mode="fixture")
        self.assertEqual(result["result"].status, "failed")
        self.assertEqual(result["result"].usage, {"search": 1, "extract": 0, "llm": 0})

    def test_parent_adapter_returns_only_market_delta(self):
        result = run_market(read_input(INPUT), FixtureWeb(), FixtureAnalyst(), mode="fixture", auto_repair=False)
        update = parent_update(result)
        self.assertEqual(set(update), {"assessments", "documents", "evidence", "errors"})
        self.assertEqual(set(update["assessments"]), {"market"})
        self.assertEqual(result["result"].round, 0)
        self.assertEqual(result["result"].usage["llm"], 1)

    def test_parent_round_and_limits_are_preserved(self):
        result = run_market(read_input(INPUT), FixtureWeb(), FixtureAnalyst(), mode="fixture", round_number=1)
        self.assertEqual(result["result"].round, 1)
        self.assertEqual(result["result"].usage["llm"], 1)

    def test_invalid_model_response_returns_failure_instead_of_crashing(self):
        class InvalidAnalyst(FixtureAnalyst):
            def extract(self, *args, **kwargs):
                return {"wrong": "shape"}
        result = run_market(read_input(INPUT), FixtureWeb(), InvalidAnalyst(), mode="fixture")
        self.assertEqual(result["result"].status, "failed")
        self.assertEqual(len(result["result"].assessments), 12)
        self.assertTrue(any(e["stage"].startswith("llm") for e in result["result"].errors))

    def test_injected_role_budget_cannot_exceed_input_and_is_not_reset(self):
        data = read_input(INPUT).model_copy(update={"limits": Limits(search=1, extract=1, llm=1)})
        budget = Budget(Limits(search=100, extract=100, llm=100))
        first = run_market(data, FixtureWeb(), FixtureAnalyst(), budget=budget, auto_repair=False)
        second = run_market(data, FixtureWeb(), FixtureAnalyst(), budget=budget, round_number=1,
            previous=first["analysis"], existing_evidence=first["evidence"])
        self.assertEqual(first["result"].usage, {"search": 1, "extract": 1, "llm": 1})
        self.assertEqual(second["result"].usage, first["result"].usage)

    def test_search_snippets_alone_cannot_trigger_market_facts(self):
        data = read_input(INPUT).model_copy(update={"limits": Limits(search=6, extract=0, llm=5)})
        result = run_market(data, FixtureWeb(), FixtureAnalyst())
        self.assertEqual(result["result"].usage["llm"], 0)
        self.assertEqual(result["result"].status, "unknown")
        self.assertTrue(any(e.access_status == "snippet" for e in result["evidence"].values()))

    def test_unrelated_product_pages_are_not_extracted_or_sent_to_model(self):
        class MixedSearch(FixtureWeb):
            def search(self, query, as_of):
                return [
                    {"title": "Product (business)", "url": "https://example.org/product",
                     "content": "A product is an item offered for sale.", "published_at": None},
                    {"title": "KV cache quantization and CXL memory", "url": "https://example.org/relevant",
                     "content": "Research on LLM memory.", "published_at": None},
                ]
        result = run_market(read_input(INPUT), MixedSearch(), FixtureAnalyst(), mode="fixture", auto_repair=False)
        # 선정 논문 2개를 직접 확인하고 관련 검색 후보 1개만 추가 조회한다.
        self.assertEqual(result["result"].usage["extract"], 3)
        self.assertTrue(all(t.url in [e.url for e in result['evidence'].values()] for t in result['data'].technologies.values()))
        self.assertNotIn("https://example.org/product", [e.url for e in result["evidence"].values()])
        self.assertTrue(any(not c["selected"] for q in result["queries"] for c in q["candidates"]))


if __name__ == "__main__":
    unittest.main()
