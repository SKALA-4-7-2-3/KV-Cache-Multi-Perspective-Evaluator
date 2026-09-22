"""파일 입력의 고정 계약: Markdown 안의 단일 YAML 블록. 자유 문장은 해석하지 않는다."""

import re

import yaml

INPUT_VERSION = "review-input-v1"


class UniqueSafeLoader(yaml.SafeLoader):
    """중복 키를 덮어쓰지 않고 거절한다. Python 객체 생성 태그는 허용하지 않는다."""


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int)) or key in result:
            raise ValueError("YAML 키가 중복되었거나 지원하지 않는 형식입니다.")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def render_input_markdown(state: dict) -> str:
    data = yaml.safe_dump({"schema_version": INPUT_VERSION, "state": state},
                          allow_unicode=True, sort_keys=False, width=100)
    fence = "~" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"~+", data)), default=3))
    return ("# 상위 Agent 입력 (검증 전)\n\n"
            "아래 YAML 블록이 실행용 데이터입니다. 자유 본문은 파싱하지 않습니다.\n"
            "보고서 담당자에게는 review.output.md를 전달하세요. 이 파일은 그 전 단계 입력입니다.\n\n"
            f"{fence}yaml\n{data}{fence}\n")


def parse_input_markdown(markdown: str) -> dict:
    blocks = re.findall(r"^(~{3,}|`{3,})yaml\s*\n(.*?)^\1\s*$", markdown, re.M | re.S)
    if len(blocks) != 1:
        raise ValueError("review-input-v1의 YAML 블록이 정확히 하나 필요합니다.")
    source = blocks[0][1]
    # 앵커/별칭 순환·과도한 확장 방지. 이 계약은 재사용 앵커가 필요하지 않다.
    if any(isinstance(t, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)) for t in yaml.scan(source)):
        raise ValueError("YAML 앵커와 별칭은 지원하지 않습니다.")
    data = yaml.load(source, Loader=UniqueSafeLoader)
    if not isinstance(data, dict) or data.get("schema_version") != INPUT_VERSION:
        raise ValueError("지원하지 않는 Markdown 입력 버전입니다.")
    if not isinstance(data.get("state"), dict):
        raise ValueError("state는 mapping이어야 합니다.")
    return data["state"]
