"""Domain exceptions used to classify public failure results."""


class PaperReviewError(Exception):
    """Base error for the paper analysis package."""


class ConfigurationError(PaperReviewError):
    """Configuration is invalid or violates a safety policy."""


class DependencyError(PaperReviewError):
    """An optional runtime dependency is not installed."""


class IngestionError(PaperReviewError):
    """The source cannot be resolved or parsed reliably."""


class ProviderError(PaperReviewError):
    """A model or embedding provider call failed after retries."""
