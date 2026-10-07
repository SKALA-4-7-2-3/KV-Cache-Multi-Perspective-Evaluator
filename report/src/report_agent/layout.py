"""Consistent typography; substantive paragraphs remain agent-authored."""

import re


_NUMERIC_RANGE = re.compile(
    r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?(?:[KMGT]|만|억)?)[ \t]*~[ \t]*"
    r"(\d+(?:\.\d+)?(?:[KMGT]|만|억)?)(?![A-Za-z0-9.])")
_PROTECTED = re.compile(
    r"(?<!\\)%[^\n]*|\\(?:url|href)\{[^{}]*\}|"
    r"\$\$[\s\S]*?\$\$|(?<!\\)\$[^$]*\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|"
    r"\\begin\{(equation\*?|align\*?|verbatim|lstlisting)\}[\s\S]*?\\end\{\1\}")


def normalize_numeric_ranges(latex: str) -> str:
    """Render prose range separators; preserve numbers, units, URLs and math."""
    preamble, marker, body = latex.partition(r"\begin{document}")
    if not marker:
        return latex
    parts, start = [], 0
    for protected in _PROTECTED.finditer(body):
        parts.extend((_NUMERIC_RANGE.sub(r"\1--\2", body[start:protected.start()]), protected.group()))
        start = protected.end()
    parts.append(_NUMERIC_RANGE.sub(r"\1--\2", body[start:]))
    return preamble + marker + "".join(parts)


REPORT_LAYOUT = r"""% BEGIN_REPORT_LAYOUT
\usepackage{fontspec}
\usepackage{indentfirst}
\usepackage{hyperref}
\usepackage{xurl}
\hypersetup{hidelinks}
\defaultfontfeatures{Ligatures=TeX}
\setmainfont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setsansfont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setmonofont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setmainhangulfont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setsanshangulfont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setmonohangulfont{NanumMyeongjo}[BoldFont=NanumMyeongjoBold,AutoFakeSlant=0.18]
\setlength{\parindent}{1em}
\setlength{\parskip}{0pt}
\emergencystretch=3em
% END_REPORT_LAYOUT
"""


def apply_report_layout(latex: str) -> str:
    """Set all text families and indent the first paragraph after headings."""
    latex = re.sub(r"% BEGIN_REPORT_LAYOUT[\s\S]*?% END_REPORT_LAYOUT\n?", "", latex)
    preamble, marker, body = latex.partition(r"\begin{document}")
    if not marker:
        return latex
    return normalize_numeric_ranges(preamble.rstrip() + "\n" + REPORT_LAYOUT + "\n" + marker + body)
