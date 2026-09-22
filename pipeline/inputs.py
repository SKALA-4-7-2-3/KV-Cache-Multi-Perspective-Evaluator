"""Read the PDF inputs, natural-language request and RAG execution mode together."""

from copy import deepcopy
import json
from pathlib import Path

from . import ROOT


def load_inputs(path: Path, *, instruction=None, pdfs=None, request_path=None,
                research_path=None, run_rag=False):
    settings = json.loads(path.read_text(encoding="utf-8"))
    request = (json.loads(request_path.read_text(encoding="utf-8")) if request_path
               else deepcopy(settings["request"]))
    text = instruction if instruction is not None else (
        request.get("original_request") if request_path else settings["instruction"])
    if not text or not text.strip():
        raise ValueError("보고서 작성 관점을 설명하는 자연어 요청이 필요합니다.")
    request["original_request"] = text
    # Keep the human's exact wording; role adapters receive the same request.
    sources = ([p.expanduser().resolve() for p in pdfs] if pdfs is not None else
               [(ROOT / value).resolve() for value in settings["pdfs"]])
    rag = settings["rag"]
    mode = "live" if run_rag else rag.get("mode", "saved")
    if mode not in {"saved", "live"}:
        raise ValueError("rag.mode는 saved 또는 live여야 합니다.")
    saved = research_path.resolve() if research_path else (ROOT / rag["saved_output"]).resolve()
    return request, sources, saved, mode
