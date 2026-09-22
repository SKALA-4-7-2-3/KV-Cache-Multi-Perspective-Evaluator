"""Connect four perspective/review agents and the report writer.

The default saved-RAG path never imports the heavyweight research runtime.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "agent/domain/src", "agent/stakeholder", "agent/market",
    "agent/review", "report/src",
):
    location = str(ROOT / relative)
    if location not in sys.path:
        sys.path.insert(0, location)
