import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from market_agent.parser import read_input
from market_agent.providers import FixtureAnalyst, FixtureWeb
from market_agent.node import run_market
from market_agent.report import render_report
from market_agent.cli import cache_path, save_run


ROOT = Path(__file__).parents[2]
INPUT = Path(__file__).parents[1] / "fixtures/input.md"


class CliTests(unittest.TestCase):
    def test_debug_rounds_stay_in_cache_and_do_not_change_handoff(self):
        state = run_market(read_input(INPUT), FixtureWeb(), FixtureAnalyst(), mode='fixture')
        expected = render_report(state)
        state['debug_analyses'] = [state['analysis'].model_dump(mode='json')]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'debug-run'
            save_run(state, output, 'test-fingerprint')
            self.assertEqual((output/'market_handoff.md').read_text(), expected)
            self.assertEqual(len(list(output.iterdir())), 1)
            self.assertTrue((cache_path(output)/'debug.json').exists())

    def invoke(self, *args):
        return subprocess.run([sys.executable, "-m", "market_agent.cli", *args], cwd=ROOT, capture_output=True, text=True)

    def test_parse_mode_needs_no_keys_and_reports_real_values(self):
        done = self.invoke("--input", str(INPUT), "--mode", "parse")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('"search": 6', done.stdout)
        self.assertIn("SW-01", done.stdout)

    def test_json_files_accept_market_options_and_preserve_json_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'json-run'
            args=['--input',str(INPUT.parent/'paper_analysis_sw.json'),str(INPUT.parent/'paper_analysis_hw.json'),
                '--as-of','2026-09-22','--domain','on_device','--search-limit','2','--extract-limit','6','--llm-limit','3']
            parsed=self.invoke(*args,'--mode','parse')
            self.assertEqual(parsed.returncode,0,parsed.stderr)
            config=json.loads(parsed.stdout)
            self.assertEqual(config['input_format'],'paper_analysis_json')
            self.assertEqual(config['limits'],{'search':2,'extract':6,'llm':3})
            run_args=[*args,'--mode','fixture','--output',str(output)]
            done=self.invoke(*run_args)
            self.assertEqual(done.returncode,3,done.stderr)
            cache=cache_path(output)
            self.assertTrue((cache/'input.json').exists())
            self.assertFalse((cache/'input.md').exists())
            self.assertEqual(len(json.loads((cache/'input.json').read_text())),2)
            self.assertIn('failed_snapshot',self.invoke(*run_args,'--reuse').stderr)
            changed=[*run_args,'--as-of','2026-09-23','--reuse']
            self.assertIn('snapshot_mismatch',self.invoke(*changed).stderr)

    def test_repeated_input_flags_and_single_document_work(self):
        sw,hw=[str(INPUT.parent/f'paper_analysis_{x}.json') for x in ['sw','hw']]
        done=self.invoke('--input',sw,'--input',hw,'--mode','parse')
        self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(len(json.loads(done.stdout)['technologies']),2)
        single=self.invoke('--input',hw,'--mode','parse')
        self.assertEqual(single.returncode,0,single.stderr)
        self.assertEqual(json.loads(single.stdout)['technologies'],['HW-01'])

    def test_bad_json_options_fail_without_using_keys(self):
        bad=self.invoke('--input',str(INPUT.parent/'paper_analysis_sw.json'),'--search-limit','-1','--mode','parse')
        self.assertNotEqual(bad.returncode,0)
        self.assertNotIn('Traceback',bad.stderr)

    def test_fixture_writes_report_and_explicit_reuse_skips_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "run"
            args = ["--input", str(INPUT), "--mode", "fixture", "--output", str(output)]
            done = self.invoke(*args)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual([p.name for p in output.iterdir()], ['market_handoff.md'])
            text = (output / "market_handoff.md").read_text()
            self.assertIn("fixture", text)
            self.assertIn("시장 규모·성장", text)
            snapshot = json.loads((cache_path(output) / "run.json").read_text())
            self.assertEqual(snapshot["output_schema_version"],"0.5")
            self.assertIn("claim_pool",snapshot)
            self.assertIn("source_reviews",snapshot)
            self.assertEqual(snapshot["result"]["usage"]["llm"], 2)
            second = self.invoke(*args, "--reuse")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("snapshot reused", second.stdout)
            self.assertEqual(snapshot, json.loads((cache_path(output) / "run.json").read_text()))
            self.assertNotEqual(self.invoke(*args).returncode, 0)

    def test_reuse_rejects_corrupt_output_without_running_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'run'
            args = ['--input', str(INPUT), '--mode', 'fixture', '--output', str(output)]
            self.assertEqual(self.invoke(*args).returncode, 0)
            (output / 'market_handoff.md').write_text('corrupt')
            done = self.invoke(*args, '--reuse')
            self.assertNotEqual(done.returncode, 0)
            self.assertIn('snapshot_integrity', done.stderr)

    def test_changed_input_cannot_reuse_previous_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "input.md", Path(tmp) / "run"
            source.write_text(INPUT.read_text())
            args = ["--input", str(source), "--mode", "fixture", "--output", str(output)]
            self.assertEqual(self.invoke(*args).returncode, 0)
            source.write_text(source.read_text().replace("| run_id | demo |", "| run_id | changed |"))
            done = self.invoke(*args, "--reuse")
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("snapshot_mismatch", done.stderr)

    def test_report_escapes_external_markdown_and_html(self):
        state = run_market(read_input(INPUT), FixtureWeb(), FixtureAnalyst(), mode="fixture", auto_repair=False)
        state["result"].assessments[0].judgment = '<script>alert(1)</script> | [bad](javascript:foo)\n# fake'
        text = render_report(state)
        self.assertNotIn("<script>", text)
        self.assertIn(r"\|", text)
        self.assertNotIn("\n# fake", text)


if __name__ == "__main__":
    unittest.main()
