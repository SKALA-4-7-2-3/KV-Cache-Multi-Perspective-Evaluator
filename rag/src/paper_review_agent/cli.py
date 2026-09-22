"""CLI limited to the technical-research agent."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from paper_review_agent.config import AppConfig
from paper_review_agent.e2e_validation import (
    E2EValidationArtifactError,
    create_retrieval_e2e_validation_artifact,
)
from paper_review_agent.research_api import pull_embedding_model, run_technical_research
from paper_review_agent.technical_markdown import export_technical_markdown
from paper_review_agent.technical_schemas import TechnicalResearchRequest
from paper_review_agent.technical_validation import validate_technical_research


app = typer.Typer(
    name="paper-review",
    no_args_is_help=True,
    help="근거 기반 다중 논문 기술조사 RAG Agent",
)
models_app = typer.Typer(help="고정된 로컬 임베딩 모델 snapshot 관리")
app.add_typer(models_app, name="models")


@models_app.command("pull")
def models_pull_command(
    model: Annotated[str, typer.Argument(help="현재 지원 값: bge-m3")],
    revision: Annotated[
        str | None,
        typer.Option("--revision", help="40자리 immutable Hugging Face commit"),
    ] = None,
) -> None:
    if model != "bge-m3":
        raise typer.BadParameter("현재 지원하는 로컬 임베딩 모델은 bge-m3입니다.")
    config = AppConfig.from_env(Path.cwd())
    report = pull_embedding_model(
        model_id=config.bge_model_id,
        revision=revision or config.bge_model_revision,
        config=config,
    )
    typer.echo(report.model_dump_json(indent=2))


@app.command("research")
def research_command(
    instruction_arg: Annotated[
        str | None, typer.Argument(help="PDF 경로를 포함할 수 있는 기술조사 지시")
    ] = None,
    sources: Annotated[
        list[str] | None,
        typer.Option("--source", help="PDF/TXT/Markdown/arXiv 입력(반복 가능)"),
    ] = None,
    common_sources: Annotated[
        list[str] | None,
        typer.Option(
            "--common-source",
            help="승인된 배경 문맥 PDF/TXT/Markdown/arXiv 입력(반복 가능)",
        ),
    ] = None,
    instruction: Annotated[
        str | None, typer.Option("--instruction", help="기술조사의 비교 관점")
    ] = None,
    language: Annotated[str, typer.Option("--language", help="ko 또는 en")] = "ko",
    job_id: Annotated[str | None, typer.Option("--job-id")] = None,
    force_reindex: Annotated[bool, typer.Option("--force-reindex")] = False,
) -> None:
    text = instruction or instruction_arg
    if not text:
        raise typer.BadParameter("자연어 지시를 인자 또는 --instruction으로 지정하세요.")
    envelope = run_technical_research(
        TechnicalResearchRequest(
            instruction=text,
            sources=sources or [],
            common_sources=common_sources or [],
            output_language=language,
            job_id=job_id,
            force_reindex=force_reindex,
        ),
        AppConfig.from_env(Path.cwd()),
    )
    typer.echo(envelope.model_dump_json(indent=2))
    if envelope.status != "succeeded":
        raise typer.Exit(code=1)


@app.command("create-e2e-validation")
def create_e2e_validation_command(
    golden: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    technical_run: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[
        Path | None,
        typer.Option("--output", dir_okay=False, help="기본값: <golden>.e2e.json"),
    ] = None,
    peak_rss_bytes: Annotated[
        int | None, typer.Option("--peak-rss-bytes", min=1)
    ] = None,
    completed_without_oom: Annotated[
        bool | None, typer.Option("--completed-without-oom/--oom-detected")
    ] = None,
    expected_index_profile: Annotated[
        str | None, typer.Option("--expected-index-profile")
    ] = None,
    expected_paper_ids: Annotated[
        list[str] | None, typer.Option("--expected-paper-id")
    ] = None,
    dossier_expectations: Annotated[
        Path | None,
        typer.Option("--dossier-expectations", exists=True, dir_okay=False),
    ] = None,
) -> None:
    try:
        artifact = create_retrieval_e2e_validation_artifact(
            golden,
            technical_run,
            output,
            peak_rss_bytes=peak_rss_bytes,
            completed_without_oom=completed_without_oom,
            expected_index_profile=expected_index_profile,
            expected_paper_ids=expected_paper_ids,
            dossier_expectations_path=dossier_expectations,
        )
    except (E2EValidationArtifactError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(artifact.model_dump_json(indent=2))


@app.command("validate-technical")
def validate_technical_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    report = validate_technical_research(path)
    typer.echo(report.model_dump_json(indent=2))
    if not report.valid:
        raise typer.Exit(code=1)


@app.command("export-technical-md")
def export_technical_markdown_command(
    path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, help="기술조사 run.json"),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", file_okay=False, help="기본값: <run 디렉터리>/markdown"),
    ] = None,
) -> None:
    try:
        written = export_technical_markdown(path, output)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for item in written:
        typer.echo(item)
