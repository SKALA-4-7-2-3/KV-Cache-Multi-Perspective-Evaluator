"""The standalone entry point should have the same contract as the Python API."""

from pathlib import Path

from stakeholder_agent.legacy_cli import main
from stakeholder_agent.models import OUTPUT_SECTIONS

INPUT = Path(__file__).resolve().parents[1] / "examples" / "input.md"


def test_demo_cli_creates_markdown_with_explicit_fixture_label(tmp_path):
    destination = tmp_path / "reports" / "demo.md"
    assert main(["--input", str(INPUT), "--demo", "--output", str(destination)]) == 0
    result = destination.read_text()
    assert "> DEMO:" in result
    assert "| status | partial |" in result
    for section in OUTPUT_SECTIONS:
        assert f"## {section}\n" in result


def test_invalid_input_cli_returns_failure_report_and_exit_code(tmp_path, capsys):
    invalid = tmp_path / "bad.md"
    invalid.write_text("# unrelated input")
    assert main(["--input", str(invalid), "--demo"]) == 2
    result = capsys.readouterr().out
    assert "| status | failed |" in result
    assert "## REFERENCE" in result


def test_zero_llm_budget_cannot_masquerade_as_success(capsys):
    assert main(["--input", str(INPUT), "--demo", "--llm-limit", "0"]) == 2
    assert "| status | failed |" in capsys.readouterr().out


def test_missing_input_file_is_safe_failure(capsys):
    assert main(["--input", "/does-not-exist/stakeholder-input.md", "--demo"]) == 2
    assert "FileNotFoundError" in capsys.readouterr().err
