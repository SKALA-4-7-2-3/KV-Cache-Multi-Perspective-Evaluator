"""paper_analysis JSON과 기존 input.md v0.1의 입력 경계. 본문은 실행 지시가 아니다."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from .schemas import Evidence, Limits, MarketInput, Technology


class InputError(ValueError):
    pass


SECTIONS = {"실행 정보", "기술 목록", "논문 기반 기술 요약", "근거 목록", "추가 요청 및 정보 공백"}


def sections(text: str, level: int) -> dict[str, tuple[str, int]]:
    result, name, lines, start = {}, None, [], 1
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        mark = re.match(r"^\s*(`{3,}|~{3,})", line)
        if mark:
            token = mark[1][0]
            fence = None if fence == token else (fence or token)
        heading = None if fence else re.match(r"^" + "#" * level + r"\s+(.+?)\s*#*\s*$", line)
        if heading:
            if name is not None:
                result[name] = ("\n".join(lines), start)
            name, lines, start = heading[1], [], number
            if name in result:
                raise InputError(f"{number}줄: 중복 제목 {name}")
        elif name is not None:
            lines.append(line)
    if name is not None:
        result[name] = ("\n".join(lines), start)
    return result


def table(section: tuple[str, int], expected: list[str]) -> list[dict[str, str]]:
    body, offset = section
    rows = []
    for n, line in enumerate(body.splitlines(), offset + 1):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if len(cells) != len(expected):
            raise InputError(f"{n}줄: 표 열 수가 {len(expected)}개여야 합니다")
        rows.append(cells)
    if not rows or rows[0] != expected:
        raise InputError(f"{offset}줄: 표 헤더 누락/불일치: {expected}")
    return [dict(zip(expected, row)) for row in rows[1:]]


def fields(body: str) -> dict[str, str]:
    result = {}
    for line in body.splitlines():
        m = re.match(r"^-\s+([^:]+):\s*(.*)", line)
        if m:
            if m[1] in result:
                raise InputError(f"중복 근거 속성: {m[1]}")
            result[m[1]] = m[2]
    return result


def parse_markdown(text: str) -> MarketInput:
    parts = sections(text, 2)
    missing = SECTIONS - parts.keys()
    if missing:
        raise InputError(f"필수 구역 누락: {', '.join(sorted(missing))}")
    config = {}
    for row in table(parts["실행 정보"], ["항목", "값"]):
        key = row["항목"]
        if key in config:
            raise InputError(f"실행 정보의 중복 키: {key}")
        config[key] = row["값"]
    try:
        limits = Limits(**{key: int(config[label]) for key, label in [
            ("search", "남은 검색 요청 한도"), ("extract", "남은 원문 조회 한도"), ("llm", "남은 LLM 시도 한도")]})
        summaries = sections(parts["논문 기반 기술 요약"][0], 3)
        technologies = {}
        for row in table(parts["기술 목록"], ["기술 ID", "이름", "구분", "논문·버전·URL"]):
            tech_id = row["기술 ID"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", tech_id) or tech_id in technologies:
                raise InputError(f"기술 ID 중복/형식 오류: {tech_id}")
            paper = row["논문·버전·URL"]
            url = re.search(r"https?://[^\s<>]+", paper)
            if not row["이름"] or not url:
                raise InputError(f"{tech_id}: 기술명 또는 논문 URL 누락")
            summary = summaries.get(tech_id, ("", 0))[0].strip()
            technologies[tech_id] = Technology(id=tech_id, name=row["이름"], approach=row["구분"],
                paper=paper, url=url[0], summary=summary, issues=[] if summary else ["기술 요약 누락"])
        if len(technologies) != 2 or {t.approach for t in technologies.values()} != {"SW", "HW"}:
            raise InputError("SW 기술 1개와 HW 기술 1개가 필요합니다")
        evidence = {}
        for evidence_id, (body, _) in sections(parts["근거 목록"][0], 3).items():
            if not re.fullmatch(r"[A-Za-z0-9_-]+", evidence_id):
                raise InputError(f"근거 ID 형식 오류: {evidence_id}")
            f = fields(body)
            tech_id = f["문서 ID"]
            if tech_id not in technologies:
                raise InputError(f"{evidence_id}: 알 수 없는 문서 ID {tech_id}")
            evidence[evidence_id] = Evidence(id=evidence_id, doc_id=tech_id, title=technologies[tech_id].paper,
                url=f["원문"], publisher=f.get("저자", ""), published_at=date.fromisoformat(f["발행일·버전"].split(" / ")[0]),
                locator=f["위치"], excerpt=f["근거 요지(요약)"], source_type=f.get("성격", "입력 요약"),
                access_status="provided_summary", tech_ids=[tech_id])
        warnings = []
        for tech in technologies.values():
            for label, anchor in re.findall(r"\[([^\]]+)\]\(#([^\)]+)\)", tech.summary):
                if label not in evidence or anchor.lower() != label.lower() or evidence[label].doc_id != tech.id:
                    tech.issues.append(f"{tech.id}: 근거 연결 오류 {label} → #{anchor}")
                elif label not in tech.evidence_ids:
                    tech.evidence_ids.append(label)
            warnings.extend(tech.issues)
        if not any(t.summary for t in technologies.values()):
            raise InputError("두 기술의 요약이 모두 누락됐습니다")
        return MarketInput(schema_version=config["schema_version"], run_id=config["run_id"],
            domain=config["domain"], as_of=config["조사 기준일"], language=config["언어"], limits=limits,
            technologies=technologies, evidence=evidence, raw_markdown=text,
            input_hash=hashlib.sha256(text.encode()).hexdigest(), provenance=text.split("## 실행 정보")[0].strip(),
            notes=parts["추가 요청 및 정보 공백"][0].strip(), warnings=warnings)
    except (KeyError, ValueError, ValidationError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"입력 필드 형식 오류 ({type(exc).__name__}): {exc}") from exc


def read_input(path: str | Path | list, *, as_of=None, domain=None, limits=None, approaches=None) -> MarketInput:
    paths=[Path(p) for p in path] if isinstance(path,(list,tuple)) else [Path(path)]
    if not paths:
        raise InputError('missing_input: 입력 파일이 필요합니다')
    if all(p.suffix.lower()=='.json' for p in paths):
        from .json_input import parse_paper_analyses
        documents=[]
        for p in paths:
            try:
                value=json.loads(p.read_text(encoding='utf-8-sig'))
            except json.JSONDecodeError as exc:
                raise InputError(f'invalid_json: {p.name}, {exc.lineno}줄') from None
            documents.append(value)
        if len(documents)==1 and isinstance(documents[0],list) and any(isinstance(d,dict) and 'dossier_version' in d for d in documents[0]):
            documents=documents[0]
        if any(isinstance(d,dict) and ('dossier_version' in d or 'comparison_version' in d) for d in documents):
            from .dossier_input import parse_bundle
            return parse_bundle(documents,as_of=as_of,domain=domain,limits=limits,approaches=approaches)
        documents=[d for value in documents for d in (value if isinstance(value,list) else [value])]
        return parse_paper_analyses(documents,as_of=as_of,domain=domain,limits=limits,approaches=approaches)
    if len(paths)!=1 or paths[0].suffix.lower()=='.json':
        raise InputError('mixed_input_formats: MD는 한 파일, JSON은 1~2개 문서로 입력하세요')
    if approaches:
        raise InputError('approach_json_only: MD의 구분은 기술 목록에서 지정하세요')
    data=parse_markdown(paths[0].read_text(encoding='utf-8-sig'))
    overrides={k:v for k,v in {'as_of':as_of,'domain':domain,'limits':limits}.items() if v is not None}
    try:
        return MarketInput.model_validate({**data.model_dump(),**overrides})
    except ValidationError:
        raise InputError('invalid_market_options: 조사 실행 옵션을 확인하세요') from None
