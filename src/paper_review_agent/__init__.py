"""Public API for the evidence-grounded technical research agent."""

from paper_review_agent.bge_retrieval import RetrievalFilters
from paper_review_agent.e2e_validation import create_retrieval_e2e_validation_artifact
from paper_review_agent.research_api import (
    build_bge_retrieval_service,
    build_technical_research_graph,
    pull_embedding_model,
    run_technical_research,
)
from paper_review_agent.technical_schemas import (
    TechnicalComparison,
    TechnicalDossier,
    TechnicalEvidence,
    TechnicalResearchEnvelope,
    TechnicalResearchRequest,
)
from paper_review_agent.technical_validation import validate_technical_research

__all__ = [
    "RetrievalFilters",
    "TechnicalComparison",
    "TechnicalDossier",
    "TechnicalEvidence",
    "TechnicalResearchEnvelope",
    "TechnicalResearchRequest",
    "build_bge_retrieval_service",
    "build_technical_research_graph",
    "create_retrieval_e2e_validation_artifact",
    "pull_embedding_model",
    "run_technical_research",
    "validate_technical_research",
]
