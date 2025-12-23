"""Multi-modal retrieval combining semantic, lexical, and symbol search."""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .exceptions import RetrievalError
from .models import CodeChunk, RetrievalResult, Symbol

logger = logging.getLogger(__name__)


class RepoRetriever:
    """Retrieves relevant code using multiple search strategies."""
    
    def __init__(self, embeddings_manager, indexer, llm_client, config: dict):
        """Initialize the retriever.
        
        Args:
            embeddings_manager: EmbeddingsManager instance
            indexer: RepoIndexer instance
            llm_client: LLM client for generating query embeddings
            config: RAG configuration
        """
        self.embeddings_manager = embeddings_manager
        self.indexer = indexer
        self.llm_client = llm_client
        self.config = config
        
        self.max_chunks = config.get("rag", {}).get("max_retrieved_chunks", 20)
        self.semantic_enabled = config.get("rag", {}).get("semantic_search_enabled", True)
        self.symbol_enabled = config.get("rag", {}).get("symbol_search_enabled", True)
    
    async def semantic_search(
        self, query: str, top_k: int = 20, filters: Optional[Dict] = None
    ) -> List[CodeChunk]:
        """Perform semantic search using embeddings.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters (language, file_path, etc.)
            
        Returns:
            List of CodeChunk objects
        """
        if not self.semantic_enabled:
            return []
        
        try:
            # Generate query embedding
            response = await self.llm_client.embed(
                model="nomic-embed-text",
                input=[query]
            )
            query_embedding = response.get("embeddings", [[]])[0]
            
            if not query_embedding:
                raise RetrievalError("Failed to generate query embedding")
            
            # Build where filter
            where = None
            if filters:
                where = {}
                if "language" in filters:
                    where["language"] = filters["language"]
                if "file_path" in filters:
                    where["file_path"] = {"$contains": filters["file_path"]}
                if "chunk_type" in filters:
                    where["chunk_type"] = filters["chunk_type"]
            
            # Query ChromaDB
            results = self.embeddings_manager.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
            )
            
            chunks = []
            if results and results["ids"]:
                for idx, chunk_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][idx]
                    document = results["documents"][0][idx]
                    
                    chunk = CodeChunk(
                        chunk_id=chunk_id,
                        file_path=metadata.get("file_path", ""),
                        content=document,
                        start_line=metadata.get("start_line", 0),
                        end_line=metadata.get("end_line", 0),
                        language=metadata.get("language", ""),
                        chunk_type=metadata.get("chunk_type", "code"),
                        symbols=metadata.get("symbols", "").split(",") if metadata.get("symbols") else [],
                    )
                    chunks.append(chunk)
            
            logger.debug(f"Semantic search returned {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise RetrievalError(
                f"Semantic search failed: {e}", original_exception=e
            )
    
    async def lexical_search(
        self, query: str, file_patterns: Optional[List[str]] = None, max_results: int = 50
    ) -> List[CodeChunk]:
        """Perform lexical search using ripgrep.
        
        Args:
            query: Search query
            file_patterns: Optional file patterns (e.g., ["*.py"])
            max_results: Maximum results to return
            
        Returns:
            List of CodeChunk objects
        """
        try:
            cmd = [
                "rg",
                "--json",
                "--max-count=10",
                "--context=3",
                query,
                str(self.indexer.repo_path)
            ]
            
            if file_patterns:
                for pattern in file_patterns:
                    cmd.extend(["--glob", pattern])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            chunks = []
            chunk_map = {}
            
            for line in result.stdout.splitlines():
                try:
                    data = json.loads(line)
                    
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        path = match_data.get("path", {}).get("text", "")
                        line_number = match_data.get("line_number", 0)
                        text = match_data.get("lines", {}).get("text", "")
                        
                        if path not in chunk_map:
                            chunk_map[path] = []
                        
                        chunk_map[path].append((line_number, text))
                        
                except json.JSONDecodeError:
                    continue
            
            # Build chunks from matches
            for file_path, matches in chunk_map.items():
                matches.sort(key=lambda x: x[0])
                
                # Merge nearby matches
                current_lines = []
                start_line = matches[0][0]
                
                for line_num, text in matches:
                    if current_lines and line_num - start_line > 20:
                        # Create chunk
                        content = "\n".join(current_lines)
                        chunk_id = f"{file_path}::lexical::{start_line}"
                        
                        chunk = CodeChunk(
                            chunk_id=chunk_id,
                            file_path=file_path,
                            content=content,
                            start_line=start_line,
                            end_line=start_line + len(current_lines),
                            language=self.indexer._detect_language(Path(file_path)) or "text",
                            chunk_type="code",
                            symbols=[],
                        )
                        chunks.append(chunk)
                        
                        current_lines = []
                        start_line = line_num
                    
                    current_lines.append(text.rstrip())
                
                # Add final chunk
                if current_lines:
                    content = "\n".join(current_lines)
                    chunk_id = f"{file_path}::lexical::{start_line}"
                    
                    chunk = CodeChunk(
                        chunk_id=chunk_id,
                        file_path=file_path,
                        content=content,
                        start_line=start_line,
                        end_line=start_line + len(current_lines),
                        language=self.indexer._detect_language(Path(file_path)) or "text",
                        chunk_type="code",
                        symbols=[],
                    )
                    chunks.append(chunk)
            
            logger.debug(f"Lexical search returned {len(chunks)} chunks")
            return chunks[:max_results]
            
        except FileNotFoundError:
            logger.warning("ripgrep not installed, lexical search disabled")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("Lexical search timed out")
            return []
        except Exception as e:
            logger.warning(f"Lexical search failed: {e}")
            return []
    
    async def symbol_search(
        self, symbol_name: str, symbol_type: Optional[str] = None
    ) -> List[Symbol]:
        """Search for symbols by name.
        
        Args:
            symbol_name: Symbol name to search for
            symbol_type: Optional symbol type filter
            
        Returns:
            List of Symbol objects
        """
        if not self.symbol_enabled:
            return []
        
        try:
            # Query symbol store from embeddings manager
            symbols = await self.embeddings_manager.query_symbols(symbol_name, symbol_type)
            logger.debug(f"Symbol search returned {len(symbols)} symbols")
            return symbols
        except Exception as e:
            logger.warning(f"Symbol search failed: {e}")
            return []
    
    async def retrieve_context(
        self,
        query: str,
        retrieval_strategy: str = "hybrid",
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """Retrieve relevant context using specified strategy.
        
        Args:
            query: Search query
            retrieval_strategy: Strategy to use (hybrid, semantic, lexical, symbol)
            filters: Optional filters
            
        Returns:
            RetrievalResult object
        """
        chunks = []
        symbols = []
        
        if retrieval_strategy == "semantic":
            chunks = await self.semantic_search(query, top_k=self.max_chunks, filters=filters)
            
        elif retrieval_strategy == "lexical":
            chunks = await self.lexical_search(query, max_results=self.max_chunks)
            
        elif retrieval_strategy == "symbol":
            # Symbol-first search
            symbols = await self.symbol_search(query)
            # Also get chunks for symbol locations
            if symbols:
                file_paths = list(set(s.file_path for s in symbols))
                chunks = await self.retrieve_files_by_path(file_paths[:10])
            
        elif retrieval_strategy == "hybrid":
            # Run both searches in parallel
            semantic_task = self.semantic_search(query, top_k=10, filters=filters)
            lexical_task = self.lexical_search(query, max_results=10)
            symbol_task = self.symbol_search(query)
            
            semantic_chunks, lexical_chunks, symbol_results = await asyncio.gather(
                semantic_task, lexical_task, symbol_task, return_exceptions=True
            )
            
            if isinstance(semantic_chunks, Exception):
                logger.error(f"Semantic search failed in hybrid mode: {semantic_chunks}")
                semantic_chunks = []
            
            if isinstance(lexical_chunks, Exception):
                logger.error(f"Lexical search failed in hybrid mode: {lexical_chunks}")
                lexical_chunks = []
            
            if isinstance(symbol_results, Exception):
                logger.error(f"Symbol search failed in hybrid mode: {symbol_results}")
                symbol_results = []
            else:
                symbols = symbol_results
            
            # Merge and deduplicate
            chunk_map = {}
            for chunk in semantic_chunks + lexical_chunks:
                key = f"{chunk.file_path}:{chunk.start_line}"
                if key not in chunk_map:
                    chunk_map[key] = chunk
            
            chunks = list(chunk_map.values())[:self.max_chunks]
        
        # Estimate tokens
        total_tokens = sum(len(chunk.content) // 4 for chunk in chunks)
        
        return RetrievalResult(
            chunks=chunks,
            symbols=symbols,
            files=[],
            total_tokens=total_tokens,
            retrieval_method=retrieval_strategy,
        )
    
    async def retrieve_files_by_path(self, file_paths: List[str]) -> List[CodeChunk]:
        """Retrieve all chunks for specified files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            List of CodeChunk objects
        """
        chunks = []
        
        for file_path in file_paths:
            results = self.embeddings_manager.collection.get(
                where={"file_path": file_path}
            )
            
            if results and results["ids"]:
                for idx, chunk_id in enumerate(results["ids"]):
                    metadata = results["metadatas"][idx]
                    document = results["documents"][idx]
                    
                    chunk = CodeChunk(
                        chunk_id=chunk_id,
                        file_path=metadata.get("file_path", ""),
                        content=document,
                        start_line=metadata.get("start_line", 0),
                        end_line=metadata.get("end_line", 0),
                        language=metadata.get("language", ""),
                        chunk_type=metadata.get("chunk_type", "code"),
                        symbols=metadata.get("symbols", "").split(",") if metadata.get("symbols") else [],
                    )
                    chunks.append(chunk)
        
        return chunks
    
    async def retrieve_documentation(self, query: str) -> List[CodeChunk]:
        """Retrieve documentation chunks.
        
        Args:
            query: Search query
            
        Returns:
            List of CodeChunk objects
        """
        return await self.semantic_search(
            query,
            top_k=10,
            filters={"chunk_type": "documentation"}
        )
