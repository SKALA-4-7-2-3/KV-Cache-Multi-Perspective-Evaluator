import unittest

from report_agent.parser import parse_report_input
from report_agent.validator import validate_latex
from tests.helpers import sample_input, valid_latex


class ValidatorTests(unittest.TestCase):
    def test_valid_document_passes(self) -> None:
        parsed = parse_report_input(sample_input())
        result = validate_latex(valid_latex(), parsed)
        self.assertTrue(result.valid, result.issues)

    def test_unknown_citation_fails(self) -> None:
        parsed = parse_report_input(sample_input())
        latex = valid_latex().replace(
            r"RDKV\cite{SW01_RDKV}", r"RDKV\cite{UNKNOWN_KEY}"
        )
        result = validate_latex(latex, parsed)
        self.assertFalse(result.valid)
        self.assertTrue(
            any("허용되지 않은 citation_key" in issue for issue in result.issues)
        )

    def test_local_asset_path_fails(self) -> None:
        parsed = parse_report_input(sample_input())
        latex = valid_latex().replace(
            r"\begin{document}",
            "\n".join((r"\includegraphics{/Users/me/chart.png}", r"\begin{document}")),
        )
        result = validate_latex(latex, parsed)
        self.assertFalse(result.valid)
        self.assertTrue(
            any("외부 파일" in issue or "로컬 경로" in issue for issue in result.issues)
        )

    def test_missing_kotex_fails(self) -> None:
        parsed = parse_report_input(sample_input())
        result = validate_latex(valid_latex().replace(r"\usepackage{kotex}", ""), parsed)
        self.assertFalse(result.valid)
        self.assertTrue(any("kotex" in issue for issue in result.issues))

    def test_missing_hidelinks_fails(self) -> None:
        parsed = parse_report_input(sample_input())
        result = validate_latex(
            valid_latex().replace(r"\hypersetup{hidelinks}", ""), parsed
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("hypersetup" in issue for issue in result.issues))

    def test_missing_required_subsection_fails(self) -> None:
        parsed = parse_report_input(sample_input())
        latex = valid_latex().replace(r"\subsection{병행 가능성}", "")
        result = validate_latex(latex, parsed)
        self.assertFalse(result.valid)
        self.assertTrue(
            any("필수 subsection이 없습니다: 병행 가능성" in issue for issue in result.issues)
        )

    def test_bibitem_with_optional_label_is_recognized(self) -> None:
        parsed = parse_report_input(sample_input())
        latex = valid_latex().replace(
            r"\bibitem{SW01_RDKV}",
            r"\bibitem[Zhang et al.(2026)]{SW01_RDKV}",
        )
        result = validate_latex(latex, parsed)
        self.assertTrue(result.valid, result.issues)


if __name__ == "__main__":
    unittest.main()
