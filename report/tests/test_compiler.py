import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from report_agent.compiler import LatexCompileError, compile_latex, find_latex_compiler


class CompilerTests(unittest.TestCase):
    def test_app_bundled_tectonic_path_is_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "app-tectonic"
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(0o755)
            with patch.dict("os.environ", {"TECTONIC_BIN": "", "CODEX_TECTONIC_PATH": str(binary)}), \
                    patch("report_agent.compiler.shutil.which", return_value=None):
                self.assertEqual(find_latex_compiler("tectonic"), str(binary.resolve()))

    def test_explicit_tectonic_binary_keeps_priority_over_app_path(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "explicit-tectonic"
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(0o755)
            with patch.dict("os.environ", {"TECTONIC_BIN": str(binary), "CODEX_TECTONIC_PATH": "/missing/app-tectonic"}):
                self.assertEqual(find_latex_compiler("tectonic"), str(binary.resolve()))

    def test_missing_source_fails_before_compiler_lookup(self) -> None:
        with self.assertRaises(LatexCompileError):
            compile_latex(Path("missing-report.tex"))

    @unittest.skipUnless(
        find_latex_compiler("xelatex") or find_latex_compiler("tectonic"),
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


class LocalFontCompilerTests(unittest.TestCase):
    def test_configured_fonts_apply_only_to_compilation_copy(self) -> None:
        source = r"""\documentclass{article}
\usepackage{fontspec}
\usepackage{kotex}
\setmainfont{NanumMyeongjo}
\setsansfont[BoldFont=NanumMyeongjoBold,Scale=0.95]{NanumMyeongjo}
\setmonofont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setmainhangulfont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold]
\setsanshangulfont{NanumMyeongjo}
\setmonohangulfont{NanumMyeongjo}
\begin{document}
원본 본문의 NanumMyeongjo 표기를 보존한다.
\end{document}
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fonts = root / "fonts with spaces #"
            fonts.mkdir()
            for name in ("Regular", "Bold"):
                (fonts / f"NanumMyeongjo-{name}.ttf").write_bytes(name.encode())
            tex_path = root / "report.tex"
            tex_path.write_text(source, encoding="utf-8")
            original = tex_path.read_bytes()

            def fake_compile(command, *, cwd, **kwargs):
                build_dir = Path(cwd)
                copied = (build_dir / tex_path.name).read_text(encoding="utf-8")
                self.assertEqual(copied.count("{NanumMyeongjo-Regular.ttf}"), 6)
                self.assertEqual(copied.count("Path=fonts/"), 6)
                self.assertEqual(copied.count("BoldFont=NanumMyeongjo-Bold.ttf"), 6)
                self.assertIn("Scale=0.95", copied)
                self.assertIn("AutoFakeSlant=0.18", copied)
                self.assertEqual(
                    copied.partition(r"\begin{document}")[2],
                    source.partition(r"\begin{document}")[2],
                )
                for name in ("Regular", "Bold"):
                    self.assertEqual(
                        (build_dir / "fonts" / f"NanumMyeongjo-{name}.ttf").read_bytes(),
                        name.encode(),
                    )
                (build_dir / "report.pdf").write_bytes(b"%PDF-test-double")
                return subprocess.CompletedProcess(command, 0, "", "")

            for engine in ("xelatex", "tectonic"):
                with self.subTest(engine=engine), \
                        patch.dict("os.environ", {"REPORT_FONT_DIR": str(fonts)}), \
                        patch("report_agent.compiler.find_latex_compiler",
                              side_effect=lambda name: f"/fake/{name}" if name == engine else None), \
                        patch("report_agent.compiler.subprocess.run", side_effect=fake_compile):
                    result = compile_latex(tex_path, root / engine / "report.pdf")
                    self.assertTrue(result.read_bytes().startswith(b"%PDF"))
                    self.assertEqual(tex_path.read_bytes(), original)

    def test_missing_configured_font_fails_before_subprocess(self) -> None:
        for missing in ("Regular", "Bold"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                tex_path = root / "report.tex"
                tex_path.write_text(r"\documentclass{article}", encoding="utf-8")
                present = "Bold" if missing == "Regular" else "Regular"
                (root / f"NanumMyeongjo-{present}.ttf").write_bytes(b"test font")
                with patch.dict("os.environ", {"REPORT_FONT_DIR": str(root)}), \
                        patch("report_agent.compiler.find_latex_compiler", return_value="/fake/tectonic"), \
                        patch("report_agent.compiler.subprocess.run") as runner:
                    with self.assertRaisesRegex(
                        LatexCompileError, f"REPORT_FONT_DIR.*NanumMyeongjo-{missing}\\.ttf"
                    ):
                        compile_latex(tex_path)
                    runner.assert_not_called()

    def test_missing_configured_font_directory_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tex_path = Path(directory) / "report.tex"
            tex_path.write_text(r"\documentclass{article}", encoding="utf-8")
            with patch.dict("os.environ", {"REPORT_FONT_DIR": str(Path(directory) / "missing")}), \
                    patch("report_agent.compiler.find_latex_compiler", return_value="/fake/tectonic"), \
                    patch("report_agent.compiler.subprocess.run") as runner:
                with self.assertRaisesRegex(LatexCompileError, "REPORT_FONT_DIR"):
                    compile_latex(tex_path)
                runner.assert_not_called()

    def test_unconfigured_font_declarations_remain_unchanged(self) -> None:
        source = r"\setmainfont{NanumMyeongjo}" + "\n" + r"\begin{document}본문\end{document}"
        with tempfile.TemporaryDirectory() as directory:
            tex_path = Path(directory) / "report.tex"
            tex_path.write_text(source, encoding="utf-8")

            def fake_compile(command, *, cwd, **kwargs):
                build_dir = Path(cwd)
                self.assertEqual((build_dir / "report.tex").read_text(encoding="utf-8"), source)
                (build_dir / "report.pdf").write_bytes(b"%PDF-test-double")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.dict("os.environ", {"REPORT_FONT_DIR": ""}), \
                    patch("report_agent.compiler.find_latex_compiler", return_value="/fake/compiler"), \
                    patch("report_agent.compiler.subprocess.run", side_effect=fake_compile):
                compile_latex(tex_path)


if __name__ == "__main__":
    unittest.main()
