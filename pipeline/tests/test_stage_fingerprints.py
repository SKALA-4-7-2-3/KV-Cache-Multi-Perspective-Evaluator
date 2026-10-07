"""Stage caches invalidate only for code that can affect their result."""
from pathlib import Path
import tempfile
import unittest

from pipeline.artifacts import stage_fingerprint


STAGES = ("trl", "review", "report-1", "quality-1")
FILES = (
    "pipeline/__init__.py", "pipeline/artifacts.py", "pipeline/governance.py", "pipeline/contracts.py",
    "pipeline/research_input.py", "pipeline/inputs.py", "pipeline/trl.py",
    "pipeline/review_bridge.py", "pipeline/reporting.py", "pipeline/report_quality.py",
    "pipeline/reference_metadata.json", "agent/review/team_review/rubric.py",
    "agent/review/team_review/schema.py", "agent/review/team_review/contract.py",
    "agent/review/team_review/review.py",
    "agent/review/team_review/markdown.py", "report/src/report_agent/generator.py",
    "report/src/report_agent/parser.py", "report/src/report_agent/validator.py",
    "pyproject.toml", "uv.lock",
)


class StageFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for relative in FILES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"original {relative}\n")

    def changed_stages(self, relative):
        before = {stage: stage_fingerprint(self.root, stage) for stage in STAGES}
        path = self.root / relative
        path.write_text(path.read_text() + "changed\n")
        after = {stage: stage_fingerprint(self.root, stage) for stage in STAGES}
        return {stage.split("-", 1)[0] for stage in STAGES if before[stage] != after[stage]}

    def test_quality_only_change_invalidates_only_quality(self):
        self.assertEqual(self.changed_stages("pipeline/report_quality.py"), {"quality"})

    def test_report_writer_change_invalidates_report_and_quality(self):
        self.assertEqual(self.changed_stages("report/src/report_agent/generator.py"),
                         {"report", "quality"})

    def test_review_eligibility_change_invalidates_trl_and_review(self):
        for relative in ("agent/review/team_review/review.py", "agent/review/team_review/contract.py"):
            with self.subTest(relative=relative):
                original = (self.root / relative).read_text()
                self.assertEqual(self.changed_stages(relative), {"trl", "review"})
                (self.root / relative).write_text(original)

    def test_common_input_or_environment_change_invalidates_every_stage(self):
        for relative in ("pipeline/artifacts.py", "pipeline/governance.py", "pipeline/contracts.py", "pipeline/research_input.py",
                         "pipeline/inputs.py", "pyproject.toml", "uv.lock"):
            with self.subTest(relative=relative):
                original = (self.root / relative).read_text()
                self.assertEqual(self.changed_stages(relative), {"trl", "review", "report", "quality"})
                (self.root / relative).write_text(original)

    def test_numbered_stage_names_share_their_stage_fingerprint(self):
        self.assertEqual(stage_fingerprint(self.root, "report-3"), stage_fingerprint(self.root, "report"))
        self.assertEqual(stage_fingerprint(self.root, "quality-2"), stage_fingerprint(self.root, "quality"))


if __name__ == "__main__":
    unittest.main()
