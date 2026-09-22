"""실제 LangGraph에서 병렬 합류·부분 갱신·1회 재평가·체크포인트를 검증한다.

분석 노드는 합성 입력을 반환하는 stub이며 API 호출은 없다.
"""

import importlib.util
import unittest
from copy import deepcopy

from team_review import prepare_repair, review_handoff_node, route_after_review, ReviewState, read_report_input
from team_review.demo import make_input
from team_review.rubric import ROLES



@unittest.skipUnless(importlib.util.find_spec("langgraph"), "팀 LangGraph 환경에서 실행")
class LangGraphIntegrationTests(unittest.TestCase):
    def test_parallel_input_new_synthesis_then_report_receives_same_md(self):
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.graph import END, START, StateGraph
        from team_review import review_agent_node, route_to_report
        from team_review.tests.test_synthesize import fake_generator, fake_auditor

        source = make_input()
        received = []
        builder = StateGraph(ReviewState)
        for role in ROLES:
            def node(state, role=role):
                return {"assessments": {role: deepcopy(source["assessments"][role])},
                        "documents": source["documents"], "evidence": source["evidence"]}
            builder.add_node(role, node)
        builder.add_node("review", lambda state: review_agent_node(state, fake_generator, fake_auditor))
        def report_stub(state):
            read_report_input(state["report_input_md"])
            received.append(state["report_input_md"])
            return {}
        builder.add_node("report", report_stub)
        builder.add_edge(START, "technical")
        for role in ROLES[1:]:
            builder.add_edge("technical", role)
        builder.add_edge(list(ROLES[1:]), "review")
        builder.add_conditional_edges("review", route_to_report, {"report": "report", "repair": END, "diagnostic": END})
        builder.add_edge("report", END)
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "new-opinion-integration"}, "max_concurrency": 3}
        result = graph.invoke({**source, "assessments": {}}, config)
        self.assertEqual(len(received), 1)
        self.assertIn("[DUMMY 종합]", received[0])
        self.assertEqual(result["synthesis"]["integrated"]["status"], "completed")
        self.assertEqual(graph.get_state(config).values["report_input_md"], received[0])

    def test_parallel_join_and_only_dirty_role_repaired_once(self):
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.graph import END, START, StateGraph

        calls = []
        source = make_input("bad_citation")
        fixed = make_input()

        def analyst(role):
            def node(state):
                round_no = state["review"]["round"]
                if round_no == 1 and role not in state["review"]["dirty_roles"]:
                    return {}  # 다른 역할은 기존 State 결과를 재사용한다.
                calls.append((role, round_no))
                result = deepcopy((fixed if round_no else source)["assessments"][role])
                result["round"] = round_no
                return {"assessments": {role: result}, "documents": source["documents"], "evidence": source["evidence"]}
            return node

        builder = StateGraph(ReviewState)
        for role in ROLES:
            builder.add_node(role, analyst(role))
        builder.add_node("review", review_handoff_node)
        builder.add_node("repair", prepare_repair)
        builder.add_node("render", lambda state: (read_report_input(state["report_input_md"], require_allowed=False) and {}))
        builder.add_edge(START, "technical")
        for role in ROLES[1:]:
            builder.add_edge("technical", role)
        builder.add_edge(list(ROLES[1:]), "review")
        builder.add_conditional_edges("review", route_after_review, {"repair": "repair", "render": "render"})
        builder.add_edge("repair", "technical")
        builder.add_edge("render", END)
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "review-test"}, "max_concurrency": 3, "recursion_limit": 20}
        initial = deepcopy(source)
        initial["assessments"] = {}
        output = graph.invoke(initial, config)
        self.assertEqual(output["review"]["status"], "completed")
        self.assertEqual(output["review"]["round"], 1)
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls.count(("market", 1)), 1)
        self.assertEqual(graph.get_state(config).values["synthesis"], output["synthesis"])
        self.assertEqual(graph.get_state(config).next, ())


if __name__ == "__main__":
    unittest.main()
