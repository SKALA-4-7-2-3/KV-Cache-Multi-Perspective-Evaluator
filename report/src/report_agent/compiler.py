from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class LatexCompileError(RuntimeError):
    pass


def _configured_font_directory() -> Path | None:
    configured = os.environ.get("REPORT_FONT_DIR")
    if not configured:
        return None
    directory = Path(configured).expanduser().resolve()
    if not directory.is_dir():
        raise LatexCompileError(f"REPORT_FONT_DIR 디렉터리를 찾을 수 없습니다: {directory}")
    for style in ("Regular", "Bold"):
        font = directory / f"NanumMyeongjo-{style}.ttf"
        if not font.is_file():
            raise LatexCompileError(f"REPORT_FONT_DIR 글꼴 파일을 찾을 수 없습니다: {font}")
    return directory


def _apply_local_fonts(build_tex: Path, font_directory: Path) -> None:
    """Use fontspec file paths in the temporary preamble without installing fonts."""
    local_fonts = build_tex.parent / "fonts"
    local_fonts.mkdir()
    for style in ("Regular", "Bold"):
        filename = f"NanumMyeongjo-{style}.ttf"
        shutil.copy2(font_directory / filename, local_fonts / filename)

    source = build_tex.read_text(encoding="utf-8")
    preamble, marker, body = source.partition(r"\begin{document}")
    declaration = re.compile(
        r"^([ \t]*\\set(?:main|sans|mono)(?:hangul)?font)\s*"
        r"(?:\[([^\]]*)\]\s*)?\{\s*NanumMyeongjo\s*\}"
        r"(?:[ \t]*\[([^\]]*)\])?",
        re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        options = ",".join(part for part in (match[2], match[3]) if part)
        retained = [
            option.strip()
            for option in options.split(",")
            if option.strip() and option.partition("=")[0].strip() not in {"Path", "BoldFont"}
        ]
        features = ",".join(["Path=fonts/", "BoldFont=NanumMyeongjo-Bold.ttf", *retained])
        return match[1] + "{NanumMyeongjo-Regular.ttf}[" + features + "]"

    build_tex.write_text(declaration.sub(replace, preamble) + marker + body, encoding="utf-8")


def find_latex_compiler(name: str) -> str | None:
    """Find a compiler in PATH, a configured location, or common local installs."""

    configuration_key = f"{name.upper()}_BIN"
    configured = os.environ.get(configuration_key)
    if not configured and name == "tectonic":
        configuration_key = "CODEX_TECTONIC_PATH"
        configured = os.environ.get(configuration_key)
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise LatexCompileError(f"{configuration_key} 실행 파일을 찾을 수 없습니다: {candidate}")
        return str(candidate.resolve())
    found = shutil.which(name)
    if found:
        return found
    locations = [
        Path("/Library/TeX/texbin"),
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path.home() / ".local/bin",
    ]
    if name == "tectonic":
        locations.append(
            Path.home()
            / ".codex/.tmp/bundled-marketplaces/openai-bundled/plugins/latex/bin"
        )
    for location in locations:
        candidate = location / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def compile_latex(tex_path: Path, pdf_path: Path | None = None) -> Path:
    """Compile an Overleaf-compatible XeLaTeX source into a PDF artifact.

    The source and final PDF are kept in separate directories so the repository
    can expose ``output/tex`` and ``output/pdf`` without committing LaTeX build
    by-products. XeLaTeX is preferred because it matches the documented
    Overleaf compiler setting; Tectonic is a compatible local fallback.
    ``REPORT_FONT_DIR`` can supply existing NanumMyeongjo Regular/Bold TTFs;
    font declarations are adjusted only in the temporary compilation copy.
    """

    tex_path = tex_path.resolve()
    if not tex_path.exists():
        raise LatexCompileError(f"LaTeX 원본을 찾을 수 없습니다: {tex_path}")
    font_directory = _configured_font_directory()

    final_pdf = (pdf_path or tex_path.with_suffix(".pdf")).resolve()
    final_pdf.parent.mkdir(parents=True, exist_ok=True)

    xelatex = find_latex_compiler("xelatex")
    tectonic = find_latex_compiler("tectonic")
    if not xelatex and not tectonic:
        raise LatexCompileError("xelatex 또는 tectonic이 설치되어 있지 않습니다.")

    with tempfile.TemporaryDirectory(prefix="kv-report-latex-") as temp_dir:
        build_dir = Path(temp_dir)
        build_tex = build_dir / tex_path.name
        shutil.copy2(tex_path, build_tex)
        if font_directory is not None:
            _apply_local_fonts(build_tex, font_directory)

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
