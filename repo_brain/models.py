"""Pydantic models for RAG data structures."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FileMetadata(BaseModel):
    """Metadata for a repository file."""
    
    model_config = ConfigDict(from_attributes=True)
    
    file_path: str
    language: str
    size_bytes: int
    last_modified: datetime
    git_last_commit: Optional[str] = None
    git_commit_count: int = 0
    is_documentation: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "last_modified": self.last_modified.isoformat(),
            "git_last_commit": self.git_last_commit,
            "git_commit_count": self.git_commit_count,
            "is_documentation": self.is_documentation,
        }


class CodeChunk(BaseModel):
    """A chunk of code with metadata."""
    
    model_config = ConfigDict(from_attributes=True)
    
    chunk_id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    chunk_type: str = "code"
    symbols: List[str] = Field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "symbols": self.symbols,
        }


class Symbol(BaseModel):
    """A code symbol (class, function, method, etc.)."""
    
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    type: str
    file_path: str
    line_number: int
    scope: Optional[str] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "scope": self.scope,
            "signature": self.signature,
        }


class RetrievalResult(BaseModel):
    """Result of a retrieval operation."""
    
    model_config = ConfigDict(from_attributes=True)
    
    chunks: List[CodeChunk] = Field(default_factory=list)
    symbols: List[Symbol] = Field(default_factory=list)
    files: List[FileMetadata] = Field(default_factory=list)
    total_tokens: int = 0
    retrieval_method: str = "hybrid"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "symbols": [symbol.to_dict() for symbol in self.symbols],
            "files": [file.to_dict() for file in self.files],
            "total_tokens": self.total_tokens,
            "retrieval_method": self.retrieval_method,
        }


class IndexStats(BaseModel):
    """Statistics about the index."""
    
    model_config = ConfigDict(from_attributes=True)
    
    total_files: int = 0
    total_chunks: int = 0
    total_symbols: int = 0
    languages: Dict[str, int] = Field(default_factory=dict)
    index_size_mb: float = 0.0
    last_indexed: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_files": self.total_files,
            "total_chunks": self.total_chunks,
            "total_symbols": self.total_symbols,
            "languages": self.languages,
            "index_size_mb": self.index_size_mb,
            "last_indexed": self.last_indexed.isoformat(),
        }
