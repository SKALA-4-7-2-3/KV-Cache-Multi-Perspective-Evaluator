import shutil
import tempfile
import unittest
from pathlib import Path

from report_agent.compiler import LatexCompileError, compile_latex


class CompilerTests(unittest.TestCase):
    def test_missing_source_fails_before_compiler_lookup(self) -> None:
        with self.assertRaises(LatexCompileError):
            compile_latex(Path("missing-report.tex"))

    @unittest.skipUnless(
        shutil.which("xelatex") or shutil.which("tectonic"),
        "XeLaTeX 또는 Tectonic이 설치된 환경에서만 PDF 통합 테스트를 실행합니다.",
    )
    def test_overleaf_source_compiles_to_requested_pdf_path(self) -> None:
        source = r"""\documentclass[11pt,a4paper]{article}
\usepackage{kotex}
\begin{document}
보고서 PDF 컴파일 검증
\end{document}
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tex_path = root / "tex" / "report.tex"
            pdf_path = root / "pdf" / "report.pdf"
            tex_path.parent.mkdir(parents=True)
            tex_path.write_text(source, encoding="utf-8")

            result = compile_latex(tex_path, pdf_path)

            self.assertEqual(result, pdf_path.resolve())
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
