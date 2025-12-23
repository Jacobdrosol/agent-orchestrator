"""RAG system for repository knowledge retrieval."""

from .context_builder import ContextBuilder
from .embeddings import EmbeddingsManager
from .exceptions import (
    EmbeddingError,
    GitAnalysisError,
    IndexingError,
    RAGError,
    RetrievalError,
    TreeSitterError,
)
from .indexer import RepoIndexer
from .models import (
    CodeChunk,
    FileMetadata,
    IndexStats,
    RetrievalResult,
    Symbol,
)
from .rag_system import RAGSystem
from .retriever import RepoRetriever

__all__ = [
    # Main system
    "RAGSystem",
    # Components
    "RepoIndexer",
    "EmbeddingsManager",
    "RepoRetriever",
    "ContextBuilder",
    # Models
    "FileMetadata",
    "CodeChunk",
    "Symbol",
    "RetrievalResult",
    "IndexStats",
    # Exceptions
    "RAGError",
    "IndexingError",
    "EmbeddingError",
    "RetrievalError",
    "TreeSitterError",
    "GitAnalysisError",
]

__version__ = "0.1.0"
