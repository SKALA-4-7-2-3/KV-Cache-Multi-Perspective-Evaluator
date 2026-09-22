"""Configuration is read at call time, never at import time."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentConfig:
    model: str = "gpt-4.1"
    openai_api_key: str = field(default="", repr=False)
    tavily_api_key: str = field(default="", repr=False)
    base_url: str | None = None
    search_limit: int = 6
    fetch_limit: int = 10
    llm_limit: int = 5
    repair_limit: int = 1
    model_timeout: float = 60.0
    tool_timeout: float = 20.0
    max_input_chars: int = 100_000
    page_chars: int = 12_000

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(model=os.getenv("STAKEHOLDER_MODEL", "gpt-4.1"),
                   openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                   tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
                   base_url=os.getenv("STAKEHOLDER_OPENAI_BASE_URL") or None)

    def __post_init__(self):
        if any(n < 0 for n in [self.search_limit, self.fetch_limit, self.llm_limit]):
            raise ValueError("호출 한도는 0 이상이어야 합니다.")
        if self.repair_limit not in (0, 1):
            raise ValueError("보완은 최대 1회입니다.")
        if self.model_timeout <= 0 or self.tool_timeout <= 0:
            raise ValueError("시간 제한은 양수여야 합니다.")
