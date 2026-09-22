from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class LatexCompileError(RuntimeError):
    pass


def compile_latex(tex_path: Path, pdf_path: Path | None = None) -> Path:
    """Compile an Overleaf-compatible XeLaTeX source into a PDF artifact.

    The source and final PDF are kept in separate directories so the repository
    can expose ``output/tex`` and ``output/pdf`` without committing LaTeX build
    by-products. XeLaTeX is preferred because it matches the documented
    Overleaf compiler setting; Tectonic is a compatible local fallback.
    """

    tex_path = tex_path.resolve()
    if not tex_path.exists():
        raise LatexCompileError(f"LaTeX 원본을 찾을 수 없습니다: {tex_path}")

    final_pdf = (pdf_path or tex_path.with_suffix(".pdf")).resolve()
    final_pdf.parent.mkdir(parents=True, exist_ok=True)

    xelatex = shutil.which("xelatex")
    tectonic = shutil.which("tectonic")
    if not xelatex and not tectonic:
        raise LatexCompileError("xelatex 또는 tectonic이 설치되어 있지 않습니다.")

    with tempfile.TemporaryDirectory(prefix="kv-report-latex-") as temp_dir:
        build_dir = Path(temp_dir)
        build_tex = build_dir / tex_path.name
        shutil.copy2(tex_path, build_tex)

        if xelatex:
            command = [
                xelatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                build_tex.name,
            ]
            for _ in range(2):
                result = subprocess.run(
                    command,
                    cwd=build_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    raise LatexCompileError(
                        "XeLaTeX 컴파일 실패:\n"
                        + result.stdout[-4000:]
                        + result.stderr[-2000:]
                    )
        else:
            result = subprocess.run(
                [
                    tectonic,
                    "--untrusted",
                    "--keep-logs",
                    "--outdir",
                    str(build_dir),
                    str(build_tex),
                ],
                cwd=build_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise LatexCompileError(
                    "Tectonic 컴파일 실패:\n"
                    + result.stdout[-4000:]
                    + result.stderr[-2000:]
                )

        compiled_pdf = build_tex.with_suffix(".pdf")
        if not compiled_pdf.exists():
            raise LatexCompileError("컴파일은 종료됐지만 PDF가 생성되지 않았습니다.")
        shutil.copy2(compiled_pdf, final_pdf)

    return final_pdf


def compile_xelatex(tex_path: Path) -> Path:
    """Backward-compatible wrapper for callers using the earlier function."""

    return compile_latex(tex_path)
