import unittest
from pathlib import Path
from market_agent.parser import read_input
from market_agent.search_plan import initial_questions, repair_questions
from market_agent.schemas import CRITERIA, unknown


class SearchPlanTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1]/'fixtures/input.md')

    def test_initial_two_queries_cover_both_technologies_and_explain_scope(self):
        questions = initial_questions(self.data)
        self.assertEqual({q.tech_id for q in questions}, {'SW-01', 'HW-01'})
        self.assertEqual(len(questions), 2)
        self.assertTrue(all(q.criteria and q.source_type and q.reason for q in questions))

    def test_repair_uses_unresolved_rows_and_does_not_repeat_queries(self):
        rows = [unknown(t, c, '미확인') for t in self.data.technologies for c in CRITERIA]
        queries = [q.model_dump() for q in initial_questions(self.data)]
        repair = repair_questions(self.data, rows, [], queries)
        self.assertLessEqual(len(repair), 2)
        self.assertTrue(all(q.query not in {x['query'] for x in queries} for q in repair))
        self.assertEqual(len({q.tech_id for q in repair}), 2)
