import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from team_review import review_handoff_node, review_agent_node
from team_review.tests.test_synthesize import fake_generator, fake_auditor
from team_review.demo import make_input
from team_review.handoff import build_handoff


class PortableHandoffTests(unittest.TestCase):
    def test_bundle_runs_from_separate_directory_without_original_package_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.md"
            source.write_text(review_agent_node(make_input(), fake_generator, fake_auditor)["report_input_md"], encoding="utf-8")
            archive = build_handoff(source, root / "handoff")
            with ZipFile(archive) as bundle:
                names = bundle.namelist()
                self.assertIn("review.output.contract.final.md", names)
                self.assertIn("team_review/markdown.py", names)
                self.assertFalse(any(".env" in n or "__pycache__" in n or n.endswith(".pdf") for n in names))
                bundle.extractall(root / "recipient")
            env = {**os.environ, "PYTHONPATH": ""}
            command = [sys.executable, "check_report_input.py"]
            result = subprocess.run(command, cwd=root / "recipient", env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            final = subprocess.run(command + ["--for-submission"], cwd=root / "recipient", env=env, capture_output=True, text=True)
            self.assertEqual(final.returncode, 2)
            imported = subprocess.run([sys.executable, "-c", "import team_review; print(team_review.__file__)"],
                                      cwd=root / "recipient", env=env, capture_output=True, text=True)
            self.assertIn(str(root / "recipient"), imported.stdout)

    def test_blocked_input_is_not_packaged(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.md"
            source.write_text(review_handoff_node(make_input("fatal_error"))["report_input_md"])
            with self.assertRaises(ValueError):
                build_handoff(source, Path(tmp) / "handoff")
