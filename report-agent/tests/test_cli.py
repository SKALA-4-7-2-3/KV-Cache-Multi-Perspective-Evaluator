import contextlib
import io
import unittest

from report_agent.cli import build_parser


class CliTests(unittest.TestCase):
    def test_pdf_output_is_always_configured(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(
            args.pdf_output,
            "output/pdf/kv-cache-technology-evaluation-report.pdf",
        )
        self.assertFalse(hasattr(args, "tex_only"))

    def test_tex_only_escape_hatch_is_rejected(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                build_parser().parse_args(["--tex-only"])


if __name__ == "__main__":
    unittest.main()
