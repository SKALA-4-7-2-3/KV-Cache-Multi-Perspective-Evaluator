"""Role cache fingerprints include every shared worker execution dependency."""
from pathlib import Path
import tempfile
import unittest

from pipeline.artifacts import role_fingerprints


COMMON = (
    "pipeline/__init__.py",
    "pipeline/runtime.py",
    "pipeline/worker_adapters.py",
    "pipeline/contracts.py",
    "pipeline/research_input.py",
    "pipeline/inputs.py",
    "pipeline/governance.py",
    "pyproject.toml",
    "uv.lock",
)


class RoleFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for relative in COMMON:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"original {relative}\n")
        for directory in ("agent/domain", "agent/market", "agent/stakeholder"):
            path = self.root / directory / "worker.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"original {directory}\n")
        report = self.root / "pipeline/report_quality.py"
        report.write_text("original report quality\n")

    def changed_roles(self, relative):
        before = role_fingerprints(self.root)
        path = self.root / relative
        path.write_text(path.read_text() + "changed\n")
        after = role_fingerprints(self.root)
        return {role for role in before if before[role] != after[role]}

    def test_every_common_worker_dependency_invalidates_all_roles(self):
        for relative in COMMON:
            with self.subTest(relative=relative):
                original = (self.root / relative).read_text()
                self.assertEqual(self.changed_roles(relative), {"domain", "market", "stakeholders"})
                (self.root / relative).write_text(original)

    def test_governance_is_hashed_as_the_complete_file(self):
        governance = self.root / "pipeline/governance.py"
        governance.write_text("class BudgetLedger:\n    audit_only = 1\n")
        before = role_fingerprints(self.root)
        governance.write_text("class BudgetLedger:\n    audit_only = 2\n")
        after = role_fingerprints(self.root)
        self.assertTrue(all(before[role] != after[role] for role in before))

    def test_role_source_only_invalidates_its_owner(self):
        self.assertEqual(self.changed_roles("agent/market/worker.py"), {"market"})

    def test_report_quality_change_preserves_worker_fingerprints(self):
        self.assertEqual(self.changed_roles("pipeline/report_quality.py"), set())


if __name__ == "__main__":
    unittest.main()
