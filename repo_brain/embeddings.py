"""Embeddings generation and ChromaDB storage."""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import chromadb
from chromadb.config import Settings
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .exceptions import EmbeddingError
from .models import CodeChunk, FileMetadata, IndexStats, Symbol

logger = logging.getLogger(__name__)


class EmbeddingsManager:
    """Manages code chunking, embedding generation, and vector storage."""
    
    def __init__(self, llm_client, config: dict, vector_store_path: str):
        """Initialize the embeddings manager.
        
        Args:
            llm_client: LLM client for generating embeddings
            config: RAG configuration
            vector_store_path: Path to ChromaDB storage
        """
        self.llm_client = llm_client
        self.config = config
        self.vector_store_path = Path(vector_store_path)
        
        self.chunk_size = config.get("rag", {}).get("chunk_size", 1000)
        self.chunk_overlap = config.get("rag", {}).get("chunk_overlap", 200)
        
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        
        # Symbol store path
        self.symbol_store_path = self.vector_store_path / "symbols.json"
        
        self.client = chromadb.PersistentClient(
            path=str(self.vector_store_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.client.get_collection(name="code_chunks")
            logger.info("Loaded existing ChromaDB collection")
        except Exception:
            self.collection = self.client.create_collection(
                name="code_chunks",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Created new ChromaDB collection")
    
    async def chunk_file(
        self,
        file_path: str,
        content: str,
        language: str,
        symbols: List
    ) -> List[CodeChunk]:
        """Chunk file content intelligently.
        
        Args:
            file_path: Path to the file
            content: File content
            language: Programming language
            symbols: Extracted symbols
            
        Returns:
            List of CodeChunk objects
        """
        lines = content.split("\n")
        chunks = []
        
        # Build symbol line map
        symbol_lines = {}
        for symbol in symbols:
            symbol_lines[symbol.line_number] = symbol.name
        
        chunk_type = "documentation" if language == "markdown" else "code"
        
        # Simple line-based chunking with overlap
        start_line = 0
        chunk_idx = 0
        
        while start_line < len(lines):
            end_line = min(start_line + self.chunk_size, len(lines))
            chunk_lines = lines[start_line:end_line]
            chunk_content = "\n".join(chunk_lines)
            
            # Find symbols in this chunk
            chunk_symbols = []
            for line_num in range(start_line + 1, end_line + 1):
                if line_num in symbol_lines:
                    chunk_symbols.append(symbol_lines[line_num])
            
            chunk_id = f"{file_path}::{chunk_idx}"
            
            chunk = CodeChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                content=chunk_content,
                start_line=start_line + 1,
                end_line=end_line,
                language=language,
                chunk_type=chunk_type,
                symbols=chunk_symbols,
            )
            chunks.append(chunk)
            
            chunk_idx += 1
            start_line = end_line - self.chunk_overlap
            
            if start_line >= len(lines):
                break
        
        logger.debug(f"Created {len(chunks)} chunks for {file_path}")
        return chunks
    
    async def generate_embeddings(
        self, chunks: List[CodeChunk], batch_size: int = 32
    ) -> List[List[float]]:
        """Generate embeddings for chunks.
        
        Args:
            chunks: List of CodeChunk objects
            batch_size: Batch size for embedding generation
            
        Returns:
            List of embedding vectors
        """
        if not chunks:
            return []
        
        embeddings = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(
                "Generating embeddings...", total=len(chunks)
            )
            
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                texts = [chunk.content for chunk in batch]
                
                try:
                    # Use nomic-embed-text model
                    response = await self.llm_client.embed(
                        model="nomic-embed-text",
                        input=texts
                    )
                    
                    batch_embeddings = response.get("embeddings", [])
                    embeddings.extend(batch_embeddings)
                    
                except Exception as e:
                    logger.error(f"Failed to generate embeddings for batch: {e}")
                    raise EmbeddingError(
                        f"Embedding generation failed: {e}", original_exception=e
                    )
                
                progress.update(task, advance=len(batch))
        
        return embeddings
    
    async def store_embeddings(
        self, chunks: List[CodeChunk], embeddings: List[List[float]], file_mtime: float = None, file_hash: str = None
    ):
        """Store chunks and embeddings in ChromaDB.
        
        Args:
            chunks: List of CodeChunk objects
            embeddings: List of embedding vectors
            file_mtime: File modification time
            file_hash: File hash for change detection
        """
        if not chunks or not embeddings:
            return
        
        if len(chunks) != len(embeddings):
            raise EmbeddingError(
                f"Chunk count ({len(chunks)}) != embedding count ({len(embeddings)})"
            )
        
        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "file_path": chunk.file_path,
                "language": chunk.language,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_type": chunk.chunk_type,
                "symbols": ",".join(chunk.symbols),
                "last_modified": datetime.now().isoformat(),
                "file_mtime": file_mtime or 0,
                "file_hash": file_hash or "",
            }
            for chunk in chunks
        ]
        
        try:
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.debug(f"Stored {len(chunks)} chunks in ChromaDB")
            
        except Exception as e:
            logger.error(f"Failed to store embeddings: {e}")
            raise EmbeddingError(
                f"Failed to store embeddings: {e}", original_exception=e
            )
    
    async def store_symbols(self, symbols: List[Symbol]):
        """Store symbols in JSON file.
        
        Args:
            symbols: List of Symbol objects
        """
        if not symbols:
            return
        
        try:
            # Load existing symbols
            existing_symbols = []
            if self.symbol_store_path.exists():
                with open(self.symbol_store_path, "r", encoding="utf-8") as f:
                    existing_symbols = json.load(f)
            
            # Convert to dict and add new symbols
            symbol_dict = {f"{s['file_path']}::{s['name']}": s for s in existing_symbols}
            for symbol in symbols:
                key = f"{symbol.file_path}::{symbol.name}"
                symbol_dict[key] = symbol.to_dict()
            
            # Write back
            with open(self.symbol_store_path, "w", encoding="utf-8") as f:
                json.dump(list(symbol_dict.values()), f, indent=2)
            
            logger.debug(f"Stored {len(symbols)} symbols")
            
        except Exception as e:
            logger.warning(f"Failed to store symbols: {e}")
    
    async def query_symbols(
        self, symbol_name: str, symbol_type: Optional[str] = None
    ) -> List[Symbol]:
        """Query symbols by name.
        
        Args:
            symbol_name: Symbol name to search for
            symbol_type: Optional symbol type filter
            
        Returns:
            List of Symbol objects
        """
        if not self.symbol_store_path.exists():
            return []
        
        try:
            with open(self.symbol_store_path, "r", encoding="utf-8") as f:
                symbols_data = json.load(f)
            
            results = []
            symbol_name_lower = symbol_name.lower()
            
            for symbol_data in symbols_data:
                # Case-insensitive partial match on name
                if symbol_name_lower in symbol_data["name"].lower():
                    # Apply type filter if specified
                    if symbol_type and symbol_data["type"] != symbol_type:
                        continue
                    
                    symbol = Symbol(**symbol_data)
                    results.append(symbol)
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to query symbols: {e}")
            return []
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate hash of file content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MD5 hash of file content
        """
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _should_reindex_file(
        self, file_path: str, current_mtime: float, file_hash: str
    ) -> bool:
        """Check if file needs reindexing.
        
        Args:
            file_path: Relative file path
            current_mtime: Current modification time
            file_hash: Current file hash
            
        Returns:
            True if file needs reindexing
        """
        try:
            # Get existing chunks for this file
            results = self.collection.get(
                where={"file_path": file_path},
                limit=1
            )
            
            if not results or not results["ids"]:
                # File not indexed yet
                return True
            
            # Check metadata
            metadata = results["metadatas"][0]
            stored_mtime = metadata.get("file_mtime", 0)
            stored_hash = metadata.get("file_hash", "")
            
            # Reindex if modification time or hash changed
            if abs(current_mtime - float(stored_mtime)) > 1.0:
                return True
            
            if file_hash and stored_hash and file_hash != stored_hash:
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking if file needs reindex: {e}")
            return True
    
    async def index_repository(
        self,
        file_metadata_list: List[FileMetadata],
        indexer,
        progress_callback: Optional[Callable] = None
    ) -> IndexStats:
        """Index entire repository.
        
        Args:
            file_metadata_list: List of FileMetadata objects
            indexer: RepoIndexer instance
            progress_callback: Optional progress callback
            
        Returns:
            IndexStats object
        """
        logger.info(f"Indexing {len(file_metadata_list)} files")
        
        total_chunks = 0
        total_symbols = 0
        languages = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(
                "Indexing repository...", total=len(file_metadata_list)
            )
            
            for idx, file_metadata in enumerate(file_metadata_list):
                try:
                    file_path = file_metadata.file_path
                    language = file_metadata.language
                    
                    # Read file content
                    full_path = indexer.repo_path / file_path
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    # Skip empty files
                    if not content.strip():
                        continue
                    
                    # Skip very large files
                    if len(content) > 1_000_000:
                        logger.warning(f"Skipping large file: {file_path} ({len(content)} bytes)")
                        continue
                    
                    # Get file metadata for change detection
                    file_stat = full_path.stat()
                    file_mtime = file_stat.st_mtime
                    file_hash = self._get_file_hash(full_path)
                    
                    # Check if file needs reindexing (incremental)
                    if not self._should_reindex_file(file_path, file_mtime, file_hash):
                        logger.debug(f"Skipping unchanged file: {file_path}")
                        # Still count it for stats
                        languages[language] = languages.get(language, 0) + 1
                        progress.update(task, advance=1)
                        continue
                    
                    # Extract symbols
                    symbols = await indexer.extract_symbols(file_path, language)
                    total_symbols += len(symbols)
                    
                    # Store symbols
                    if symbols:
                        await self.store_symbols(symbols)
                    
                    # Chunk file
                    chunks = await self.chunk_file(file_path, content, language, symbols)
                    total_chunks += len(chunks)
                    
                    # Generate embeddings
                    embeddings = await self.generate_embeddings(chunks)
                    
                    # Store in ChromaDB with file metadata
                    await self.store_embeddings(chunks, embeddings, file_mtime, file_hash)
                    
                    # Track languages
                    languages[language] = languages.get(language, 0) + 1
                    
                    if progress_callback:
                        progress_callback(idx + 1, len(file_metadata_list))
                    
                except Exception as e:
                    logger.warning(f"Failed to index file {file_metadata.file_path}: {e}")
                finally:
                    progress.update(task, advance=1)
        
        # Calculate index size
        index_size_mb = sum(
            f.stat().st_size for f in self.vector_store_path.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        
        stats = IndexStats(
            total_files=len(file_metadata_list),
            total_chunks=total_chunks,
            total_symbols=total_symbols,
            languages=languages,
            index_size_mb=round(index_size_mb, 2),
            last_indexed=datetime.now(),
        )
        
        logger.info(f"Indexing complete: {stats.to_dict()}")
        return stats
    
    async def get_index_stats(self) -> IndexStats:
        """Get statistics about the index.
        
        Returns:
            IndexStats object
        """
        try:
            count = self.collection.count()
            
            # Sample metadata to get language distribution
            if count > 0:
                sample = self.collection.get(limit=min(count, 1000))
                languages = {}
                files = set()
                
                for metadata in sample.get("metadatas", []):
                    lang = metadata.get("language", "unknown")
                    languages[lang] = languages.get(lang, 0) + 1
                    files.add(metadata.get("file_path"))
                
                # Estimate total stats
                files_count = len(files) * (count / len(sample["metadatas"]))
            else:
                languages = {}
                files_count = 0
            
            index_size_mb = sum(
                f.stat().st_size for f in self.vector_store_path.rglob("*") if f.is_file()
            ) / (1024 * 1024)
            
            return IndexStats(
                total_files=int(files_count),
                total_chunks=count,
                total_symbols=0,  # Not tracked in ChromaDB
                languages=languages,
                index_size_mb=round(index_size_mb, 2),
                last_indexed=datetime.now(),
            )
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return IndexStats()
