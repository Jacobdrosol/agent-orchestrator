"""High-level RAG system orchestration."""

import logging
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console

from .context_builder import ContextBuilder
from .embeddings import EmbeddingsManager
from .indexer import RepoIndexer
from .models import IndexStats, RetrievalResult
from .retriever import RepoRetriever

logger = logging.getLogger(__name__)
console = Console()


class RAGSystem:
    """High-level RAG system orchestrator."""
    
    def __init__(self, repo_path: str, config: dict, llm_client):
        """Initialize the RAG system.
        
        Args:
            repo_path: Path to the repository
            config: Configuration dictionary
            llm_client: LLM client instance
        """
        self.repo_path = Path(repo_path)
        self.config = config
        self.llm_client = llm_client
        
        # Set up vector store path
        repo_name = self.repo_path.name
        self.vector_store_path = Path("data") / "index" / repo_name
        
        # Initialize components
        self.indexer = RepoIndexer(repo_path, config, llm_client)
        self.embeddings_manager = EmbeddingsManager(
            llm_client, config, str(self.vector_store_path)
        )
        self.retriever = RepoRetriever(
            self.embeddings_manager, self.indexer, llm_client, config
        )
        self.context_builder = ContextBuilder(self.retriever, config)
        
        self._initialized = False
    
    async def initialize(self, force_reindex: bool = False) -> IndexStats:
        """Initialize the RAG system and index repository.
        
        Args:
            force_reindex: Force re-indexing even if index exists
            
        Returns:
            IndexStats object
        """
        logger.info("Initializing RAG system")
        
        # Check if index exists
        index_exists = self.vector_store_path.exists() and any(
            self.vector_store_path.iterdir()
        )
        
        if index_exists and not force_reindex:
            logger.info("Loading existing index")
            stats = await self.embeddings_manager.get_index_stats()
            self._initialized = True
            return stats
        
        if force_reindex:
            logger.info("Force re-indexing repository")
        else:
            logger.info("Index not found, creating new index")
        
        # Scan repository
        console.print("[bold blue]Scanning repository...[/bold blue]")
        file_metadata_list = await self.indexer.scan_repository()
        
        # Index repository
        console.print("[bold blue]Indexing repository...[/bold blue]")
        stats = await self.embeddings_manager.index_repository(
            file_metadata_list, self.indexer
        )
        
        self._initialized = True
        
        console.print(
            f"[bold green]✓[/bold green] Indexed {stats.total_files} files, "
            f"{stats.total_chunks} chunks, {stats.total_symbols} symbols"
        )
        
        return stats
    
    async def get_phase_planning_context(self, issue_documentation: str) -> Dict:
        """Get context for phase planning.
        
        Args:
            issue_documentation: Issue documentation text
            
        Returns:
            Structured context dictionary
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.context_builder.build_phase_planning_context(
            issue_documentation, str(self.repo_path)
        )
    
    async def get_spec_generation_context(self, phase_plan: Dict) -> Dict:
        """Get context for spec generation.
        
        Args:
            phase_plan: Phase plan dictionary
            
        Returns:
            Structured context dictionary
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.context_builder.build_spec_generation_context(
            phase_plan, str(self.repo_path)
        )
    
    async def get_verification_context(
        self, original_spec: Dict, changes_summary: str
    ) -> Dict:
        """Get context for verification.
        
        Args:
            original_spec: Original specification
            changes_summary: Summary of changes made
            
        Returns:
            Structured context dictionary
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.context_builder.build_verification_context(
            original_spec, changes_summary, str(self.repo_path)
        )
    
    async def search(
        self, query: str, strategy: str = "hybrid"
    ) -> RetrievalResult:
        """Search the repository.
        
        Args:
            query: Search query
            strategy: Retrieval strategy (hybrid, semantic, lexical)
            
        Returns:
            RetrievalResult object
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.retriever.retrieve_context(query, strategy)
    
    async def get_stats(self) -> IndexStats:
        """Get index statistics.
        
        Returns:
            IndexStats object
        """
        return await self.embeddings_manager.get_index_stats()
    
    async def close(self):
        """Clean up resources."""
        logger.info("Closing RAG system")
        # ChromaDB client cleanup if needed
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
