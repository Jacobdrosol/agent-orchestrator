"""Context builder for assembling retrieval results into LLM prompts."""

import logging
from typing import Dict, List

from .models import CodeChunk, RetrievalResult

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds structured context from retrieval results."""
    
    def __init__(self, retriever, config: dict):
        """Initialize the context builder.
        
        Args:
            retriever: RepoRetriever instance
            config: RAG configuration
        """
        self.retriever = retriever
        self.config = config
        self.max_tokens = config.get("rag", {}).get("max_context_tokens", 8000)
    
    async def build_phase_planning_context(
        self, issue_documentation: str, repo_path: str
    ) -> Dict:
        """Build context for phase planning.
        
        Args:
            issue_documentation: Issue documentation text
            repo_path: Repository path
            
        Returns:
            Structured context dictionary
        """
        logger.info("Building phase planning context")
        
        # Extract key terms from issue documentation
        # For now, use the entire issue as query
        query = issue_documentation[:500]  # Limit query length
        
        # Retrieve relevant code
        retrieval_result = await self.retriever.retrieve_context(
            query, retrieval_strategy="hybrid"
        )
        
        # Retrieve documentation
        doc_chunks = await self.retriever.retrieve_documentation(query)
        
        # Get hot files
        hot_files = await self.retriever.indexer.get_hot_files(top_n=10)
        
        # Build context sections
        context = {
            "repository_overview": {
                "path": repo_path,
                "hot_files": hot_files,
            },
            "relevant_code": self.format_chunks_as_markdown(retrieval_result.chunks),
            "documentation": self.format_chunks_as_markdown(doc_chunks),
            "total_tokens": retrieval_result.total_tokens,
        }
        
        logger.info(f"Phase planning context ready ({context['total_tokens']} tokens)")
        return context
    
    async def build_spec_generation_context(
        self, phase_plan: Dict, repo_path: str
    ) -> Dict:
        """Build context for spec generation.
        
        Args:
            phase_plan: Phase plan dictionary
            repo_path: Repository path
            
        Returns:
            Structured context dictionary
        """
        logger.info("Building spec generation context")
        
        # Extract file mentions from phase plan
        # This is simplified - in reality, would parse plan more carefully
        phase_text = str(phase_plan)
        
        # Retrieve relevant code
        retrieval_result = await self.retriever.retrieve_context(
            phase_text[:500], retrieval_strategy="hybrid"
        )
        
        context = {
            "phase_overview": phase_plan,
            "files_to_modify": self.format_chunks_as_markdown(retrieval_result.chunks),
            "total_tokens": retrieval_result.total_tokens,
        }
        
        logger.info(f"Spec generation context ready ({context['total_tokens']} tokens)")
        return context
    
    async def build_verification_context(
        self, original_spec: Dict, changes_summary: str, repo_path: str
    ) -> Dict:
        """Build context for verification.
        
        Args:
            original_spec: Original specification
            changes_summary: Summary of changes made
            repo_path: Repository path
            
        Returns:
            Structured context dictionary
        """
        logger.info("Building verification context")
        
        context = {
            "original_spec": original_spec,
            "changes_summary": changes_summary,
            "total_tokens": len(str(original_spec)) // 4 + len(changes_summary) // 4,
        }
        
        logger.info(f"Verification context ready ({context['total_tokens']} tokens)")
        return context
    
    def format_chunks_as_markdown(self, chunks: List[CodeChunk]) -> str:
        """Format chunks as markdown with code blocks.
        
        Args:
            chunks: List of CodeChunk objects
            
        Returns:
            Formatted markdown string
        """
        if not chunks:
            return "No relevant code found."
        
        # Group chunks by file
        file_chunks = {}
        for chunk in chunks:
            if chunk.file_path not in file_chunks:
                file_chunks[chunk.file_path] = []
            file_chunks[chunk.file_path].append(chunk)
        
        # Format as markdown
        sections = []
        for file_path, file_chunk_list in file_chunks.items():
            sections.append(f"\n### {file_path}\n")
            
            for chunk in file_chunk_list:
                sections.append(
                    f"```{chunk.language}\n"
                    f"# Lines {chunk.start_line}-{chunk.end_line}\n"
                    f"{chunk.content}\n"
                    f"```\n"
                )
        
        return "\n".join(sections)
    
    def estimate_context_tokens(self, context_dict: Dict) -> int:
        """Estimate total tokens in context.
        
        Args:
            context_dict: Context dictionary
            
        Returns:
            Estimated token count
        """
        total = 0
        
        def count_tokens(obj):
            nonlocal total
            if isinstance(obj, str):
                total += len(obj) // 4
            elif isinstance(obj, dict):
                for value in obj.values():
                    count_tokens(value)
            elif isinstance(obj, list):
                for item in obj:
                    count_tokens(item)
        
        count_tokens(context_dict)
        
        if total > self.max_tokens:
            logger.warning(
                f"Context exceeds token limit: {total} > {self.max_tokens}"
            )
        
        return total
