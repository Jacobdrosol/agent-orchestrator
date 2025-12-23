"""Custom exceptions for RAG operations."""


class RAGError(Exception):
    """Base exception for RAG operations."""
    
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception


class IndexingError(RAGError):
    """Raised when file scanning or symbol extraction fails."""
    pass


class EmbeddingError(RAGError):
    """Raised when embedding generation fails."""
    pass


class RetrievalError(RAGError):
    """Raised when search operations fail."""
    pass


class TreeSitterError(RAGError):
    """Raised when parser initialization or parsing fails."""
    pass


class GitAnalysisError(RAGError):
    """Raised when git history analysis fails."""
    pass
