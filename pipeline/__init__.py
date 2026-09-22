"""Integration boundary; never imports or executes the Research agent."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "domain-agent/src", "stakeholder-agent", "market-research-agent",
    "review-agent", "report-agent/src",
):
    location = str(ROOT / relative)
    if location not in sys.path:
        sys.path.insert(0, location)
