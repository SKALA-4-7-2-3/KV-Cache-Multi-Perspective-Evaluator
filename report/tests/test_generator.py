import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from report_agent import ReportAgent
from tests.helpers import sample_input, valid_latex


class GeneratorTests(unittest.TestCase):
    def test_programmatic_handoff_returns_pdf_artifacts(self) -> None:
        agent = ReportAgent(responder=lambda _instructions, _prompt: valid_latex())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tex_path = root / "tex" / "report.tex"
            pdf_path = root / "pdf" / "report.pdf"

            def fake_compile(source: Path, destination: Path) -> Path:
                self.assertEqual(source, tex_path.resolve())
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.5\n")
                return destination.resolve()

            with patch("report_agent.generator.compile_latex", side_effect=fake_compile):
                artifacts = agent.generate_pdf(
                    sample_input(),
                    tex_path=tex_path,
                    pdf_path=pdf_path,
                )

            self.assertTrue(artifacts.generation.validation.valid)
            self.assertEqual(artifacts.tex_path, tex_path.resolve())
            self.assertEqual(artifacts.pdf_path, pdf_path.resolve())
            self.assertTrue(tex_path.exists())
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
