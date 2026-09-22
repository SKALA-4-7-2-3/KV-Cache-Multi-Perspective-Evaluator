"""Consistent typography; substantive paragraphs remain agent-authored."""

import re


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
    return preamble.rstrip() + "\n" + REPORT_LAYOUT + "\n" + marker + body
