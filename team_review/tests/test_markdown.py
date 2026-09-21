import unittest
import importlib.util
from copy import deepcopy

from team_review import review_handoff_node, review_node, render_review_markdown, read_report_input
from team_review.demo import make_input, SCENARIOS
from team_review.markdown import render_input_markdown, text


class MarkdownHandoffTests(unittest.TestCase):
    def test_all_scenarios_are_markdown_and_gated(self):
        expected = dict.fromkeys(SCENARIOS, "blocked")  # 규칙만 실행한 MD는 진단용
        for case in SCENARIOS:
            with self.subTest(case=case):
                state = make_input(case)
                md = render_review_markdown(state, review_node(state))
                self.assertIn("report_generation: " + expected[case], md)
                self.assertIn("## 10. REFERENCE CANDIDATES", md)
                self.assertNotIn("invented-id", md)
                self.assertIn("demo: true", md)

    def test_output_contains_only_used_sources_and_excerpts(self):
        state = make_input()
        state["evidence"]["UNUSED"] = {**state["evidence"]["DUMMY-SW-01-p1"], "id": "UNUSED", "excerpt": "UNUSED-TEXT"}
        result = review_node(state)
        md = render_review_markdown(state, result)
        self.assertNotIn("UNUSED-TEXT", md)
        for eid in result["synthesis"]["used_evidence_ids"]:
            self.assertIn(f"### [{eid}]", md)
            self.assertIn(state["evidence"][eid]["excerpt"], md)
        self.assertEqual(md.count("## 10. REFERENCE CANDIDATES"), 1)

    def test_all_eight_cells_and_conditions_survive(self):
        state = make_input()
        output = review_node(state)
        md = render_review_markdown(state, output)
        for row in output["synthesis"]["comparison_matrix"]:
            for tech in ("SW-01", "HW-01"):
                for item in row[tech]["items"]:
                    self.assertIn(text(item["conclusion"]), md)
                    for condition in item["conditions"]:
                        self.assertIn(text(condition), md)
        self.assertIn("빈 결과를 일치·상충 없음의 증거로 쓰지 않는다.", md)

    def test_wrapper_does_not_change_original_or_core_output(self):
        state = make_input()
        before = deepcopy(state)
        wrapped = review_handoff_node(state)
        original = review_node(state)
        self.assertEqual(state, before)
        self.assertEqual(wrapped["review"], original["review"])
        self.assertEqual(wrapped["synthesis"], original["synthesis"])
        self.assertIsInstance(wrapped["report_input_md"], str)

    def test_source_mismatch_is_not_silently_exported(self):
        state = make_input()
        output = review_node(state)
        state["evidence"]["DUMMY-SW-01-p1"]["page"] = 2
        with self.assertRaises(ValueError):
            render_review_markdown(state, output)

    def test_input_is_labeled_unreviewed_and_includes_trl(self):
        md = render_input_markdown(make_input())
        self.assertIn("검증 전", md)
        self.assertIn("보고서 담당자에게는 review.output.md", md)
        self.assertIn("trl_checks:", md)

    def test_malformed_config_still_exports_failed_diagnostic(self):
        state = make_input()
        state["config"] = None
        md = render_review_markdown(state, review_node(state))
        self.assertIn("report_generation: blocked", md)

    def test_attribution_is_preserved_without_fabricated_authors(self):
        state = make_input()
        state["config"]["source_attribution"] = {"SW-01": {"authors": "테스트 저자", "license": "https://creativecommons.org/licenses/by/4.0/"}}
        md = render_review_markdown(state, review_node(state))
        self.assertIn("테스트 저자", md)
        self.assertIn("저자 정보 미제공", md)

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "팀 LangGraph 환경에서 실행")
    def test_markdown_reaches_next_graph_node_and_checkpoint(self):
        from langgraph.graph import StateGraph, START, END
        from langgraph.checkpoint.memory import InMemorySaver
        from team_review.schema import ReviewState

        received = []

        def report_stub(state):
            # 실제 LLM 호출 대신 후단이 받은 본문을 확인한다.
            received.append(state["report_input_md"])
            return {}

        builder = StateGraph(ReviewState)
        builder.add_node("review", review_handoff_node)
        builder.add_node("report", report_stub)
        builder.add_edge(START, "review")
        builder.add_edge("review", "report")
        builder.add_edge("report", END)
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "markdown-handoff-test"}}
        result = graph.invoke(make_input(), config)
        self.assertEqual(received, [result["report_input_md"]])
        self.assertEqual(graph.get_state(config).values["report_input_md"], result["report_input_md"])


if __name__ == "__main__":
    unittest.main()
