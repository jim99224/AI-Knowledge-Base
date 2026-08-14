"""Domain-level exceptions."""


class KnowledgeBaseError(Exception):
    """Base exception for expected knowledge-base failures."""


class ConfigurationError(KnowledgeBaseError):
    """Raised when a configured adapter cannot be initialized safely."""


class DimensionMismatchError(KnowledgeBaseError):
    """Raised when an embedding dimension does not match a collection."""


class StoreNotConnectedError(KnowledgeBaseError):
    """Raised when a storage operation is attempted before connecting."""
