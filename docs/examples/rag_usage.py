"""
Example usage of the RAG system for repository knowledge retrieval.

This script demonstrates how to:
1. Initialize the RAG system
2. Index a repository
3. Perform different types of searches
4. Get context for phase planning and spec generation
"""

import asyncio
from pathlib import Path

from orchestrator import OllamaClient
from repo_brain import RAGSystem


async def main():
    """Demonstrate RAG system usage."""
    
    # Initialize LLM client
    llm_client = OllamaClient(base_url="http://localhost:11434")
    
    # Load configuration
    config = {
        "rag": {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "max_retrieved_chunks": 20,
            "max_context_tokens": 8000,
            "semantic_search_enabled": True,
            "symbol_search_enabled": True,
        }
    }
    
    # Initialize RAG system
    repo_path = Path.cwd()  # Current repository
    
    print("=" * 60)
    print("RAG System Demo")
    print("=" * 60)
    
    async with RAGSystem(str(repo_path), config, llm_client) as rag:
        # Example 1: Initialize and index repository
        print("\n[1] Initializing RAG system...")
        stats = await rag.initialize()
        
        print(f"\n✓ Index Statistics:")
        print(f"  - Total files: {stats.total_files}")
        print(f"  - Total chunks: {stats.total_chunks}")
        print(f"  - Total symbols: {stats.total_symbols}")
        print(f"  - Languages: {stats.languages}")
        print(f"  - Index size: {stats.index_size_mb:.2f} MB")
        
        # Example 2: Semantic search
        print("\n[2] Semantic search for 'authentication logic'...")
        results = await rag.search("authentication logic", strategy="semantic")
        
        print(f"\n✓ Found {len(results.chunks)} relevant chunks:")
        for i, chunk in enumerate(results.chunks[:3]):
            print(f"\n  Chunk {i+1}:")
            print(f"  - File: {chunk.file_path}")
            print(f"  - Lines: {chunk.start_line}-{chunk.end_line}")
            print(f"  - Language: {chunk.language}")
            print(f"  - Symbols: {', '.join(chunk.symbols) if chunk.symbols else 'None'}")
            print(f"  - Preview: {chunk.content[:100]}...")
        
        # Example 3: Lexical search
        print("\n[3] Lexical search for 'async def'...")
        results = await rag.search("async def", strategy="lexical")
        
        print(f"\n✓ Found {len(results.chunks)} matches:")
        for i, chunk in enumerate(results.chunks[:3]):
            print(f"\n  Match {i+1}:")
            print(f"  - File: {chunk.file_path}")
            print(f"  - Lines: {chunk.start_line}-{chunk.end_line}")
        
        # Example 4: Hybrid search (default)
        print("\n[4] Hybrid search for 'error handling'...")
        results = await rag.search("error handling", strategy="hybrid")
        
        print(f"\n✓ Found {len(results.chunks)} relevant chunks (hybrid):")
        print(f"  - Total tokens: {results.total_tokens}")
        print(f"  - Retrieval method: {results.retrieval_method}")
        
        # Example 5: Get phase planning context
        print("\n[5] Getting phase planning context...")
        issue_doc = """
        Implement a new user authentication system with the following requirements:
        - Support JWT token-based authentication
        - Add login and logout endpoints
        - Integrate with existing user database
        - Add middleware for protecting routes
        """
        
        context = await rag.get_phase_planning_context(issue_doc)
        
        print(f"\n✓ Phase planning context ready:")
        print(f"  - Repository: {context['repository_overview']['path']}")
        print(f"  - Hot files: {len(context['repository_overview']['hot_files'])}")
        print(f"  - Total tokens: {context['total_tokens']}")
        print(f"\n  Relevant code preview:")
        print(f"  {context['relevant_code'][:200]}...")
        
        # Example 6: Get spec generation context
        print("\n[6] Getting spec generation context...")
        phase_plan = {
            "title": "Implement JWT Authentication",
            "intent": "Add secure token-based authentication",
            "acceptance_criteria": [
                "Login endpoint returns valid JWT",
                "Protected routes require valid token",
                "Logout invalidates token"
            ]
        }
        
        context = await rag.get_spec_generation_context(phase_plan)
        
        print(f"\n✓ Spec generation context ready:")
        print(f"  - Phase: {context['phase_overview']['title']}")
        print(f"  - Total tokens: {context['total_tokens']}")
        
        # Example 7: Force re-index
        print("\n[7] Force re-indexing...")
        stats = await rag.initialize(force_reindex=True)
        
        print(f"\n✓ Re-indexed: {stats.total_files} files")
        
        # Example 8: Get current stats
        print("\n[8] Getting current index statistics...")
        stats = await rag.get_stats()
        
        print(f"\n✓ Current statistics:")
        print(f"  - Files: {stats.total_files}")
        print(f"  - Chunks: {stats.total_chunks}")
        print(f"  - Size: {stats.index_size_mb:.2f} MB")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
