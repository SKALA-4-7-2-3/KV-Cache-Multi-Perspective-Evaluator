import unittest


class PlannerTests(unittest.TestCase):
    def test_valid_accepted_roles_require_no_tasks(self):
        from pipeline.planner import create_plan
        self.assertEqual(create_plan([], run_id="test", revision=1, model="offline", responder=lambda *a: self.fail("No model needed")), [])

    def test_one_market_cell_does_not_expand_to_other_roles_or_cells(self):
        from pipeline.planner import create_plan
        cell = {"role": "market", "technology_id": "HW-01", "criterion_id": "standardization"}
        def answer(*args):
            return {"tasks": [{"role": "market", "active_cells": [{k:v for k,v in cell.items() if k != "role"}],
                               "reason": "Repair the single requested cell", "dependency_roles": []}]}
        tasks = create_plan([cell], run_id="test", revision=2, model="offline", responder=answer)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["technology_ids"], ["HW-01"])
        self.assertEqual(tasks[0]["criterion_ids"], ["standardization"])
        self.assertEqual(tasks[0]["plan_revision"], 2)

    def test_model_cannot_add_unrequested_scope_or_omit_missing_cells(self):
        from pipeline.planner import create_plan
        cell = {"role": "market", "technology_id": "HW-01", "criterion_id": "standardization"}
        for tasks in ([], [{"role":"domain", "active_cells":[{"technology_id":"SW-01","criterion_id":"capacity"}],
                            "reason":"expand", "dependency_roles":[]} ]):
            with self.assertRaises(ValueError):
                create_plan([cell], run_id="test", revision=1, model="offline", responder=lambda *a: {"tasks":tasks})

    def test_reducer_is_idempotent_but_rejects_conflicting_same_attempt(self):
        from pipeline.contracts import merge_outcomes
        a = {"key": {"task_id":"a", "plan_revision":1, "task_attempt":1, "status":"finished"}}
        self.assertEqual(merge_outcomes(a,a),a)
        with self.assertRaises(ValueError):
            merge_outcomes(a, {"key":{**a["key"],"status":"failed"}})


if __name__ == "__main__": unittest.main()
