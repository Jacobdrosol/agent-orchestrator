# RAG System Documentation

## Overview

The RAG (Retrieval-Augmented Generation) system provides intelligent code search and context retrieval for the Agent Orchestrator. It combines semantic search (vector embeddings), lexical search (ripgrep), and symbol analysis (tree-sitter) to find relevant code context for phase planning and spec generation.

## Architecture

The RAG system consists of five main components:

### 1. RepoIndexer (`repo_brain/indexer.py`)

Scans repository files, extracts symbols via tree-sitter, and analyzes git history.

**Key Features:**
- File scanning with exclusion patterns (node_modules, venv, etc.)
- Language detection from file extensions
- Symbol extraction (classes, functions, methods) using tree-sitter
- Git history analysis (commit counts, hot files)
- Documentation detection (markdown, README files)

**Supported Languages:**
- Python (`.py`)
- JavaScript/TypeScript (`.js`, `.jsx`, `.ts`, `.tsx`)
- Java (`.java`)
- C# (`.cs`)
- Go (`.go`)
- Rust (`.rs`)
- C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)

### 2. EmbeddingsManager (`repo_brain/embeddings.py`)

Chunks code intelligently and generates embeddings using Ollama's nomic-embed-text model.

**Key Features:**
- Intelligent code chunking with overlap
- Batch embedding generation
- ChromaDB storage with metadata
- Incremental indexing (skip unchanged files)
- Progress tracking with rich library

**Configuration:**
- `chunk_size`: Lines per chunk (default: 1000)
- `chunk_overlap`: Overlap between chunks (default: 200)

### 3. RepoRetriever (`repo_brain/retriever.py`)

Multi-modal search combining semantic, lexical, and symbol-based retrieval.

**Search Strategies:**

- **Semantic Search**: Vector similarity using embeddings
- **Lexical Search**: Ripgrep-based text matching
- **Symbol Search**: Query symbol database
- **Hybrid Search** (default): Combines semantic + lexical, deduplicates and ranks results

**Configuration:**
- `max_retrieved_chunks`: Maximum chunks to return (default: 20)
- `semantic_search_enabled`: Enable semantic search (default: true)
- `symbol_search_enabled`: Enable symbol search (default: true)

### 4. ContextBuilder (`repo_brain/context_builder.py`)

Assembles retrieved chunks into structured context for LLM prompts.

**Context Types:**

- **Phase Planning Context**: Repository overview, relevant code, documentation, hot files
- **Spec Generation Context**: Files to modify, related code, symbols
- **Verification Context**: Original spec, changes made, modified files

**Features:**
- Markdown formatting with syntax highlighting
- Token estimation and limit enforcement
- Context optimization (prioritize mentioned files, hot files)

### 5. RAGSystem (`repo_brain/rag_system.py`)

High-level orchestrator providing simple API for other components.

**Key Methods:**
- `initialize(force_reindex=False)`: Index repository
- `get_phase_planning_context(issue_doc)`: Get context for planning
- `get_spec_generation_context(phase_plan)`: Get context for specs
- `search(query, strategy="hybrid")`: General search
- `get_stats()`: Get index statistics

## Usage Examples

### Basic Initialization

```python
from repo_brain import RAGSystem
from orchestrator import OllamaClient

# Initialize LLM client
llm_client = OllamaClient(base_url="http://localhost:11434")

# Initialize RAG system
rag = RAGSystem(
    repo_path="path/to/repository",
    config=config_dict,
    llm_client=llm_client
)

# Index repository
stats = await rag.initialize()
print(f"Indexed {stats.total_files} files, {stats.total_chunks} chunks")
```

### Phase Planning Context

```python
# Get context for phase planning
issue_doc = "Implement user authentication with JWT tokens..."

context = await rag.get_phase_planning_context(issue_doc)

print(f"Relevant code: {context['relevant_code']}")
print(f"Hot files: {context['repository_overview']['hot_files']}")
print(f"Total tokens: {context['total_tokens']}")
```

### Searching the Repository

```python
# Semantic search
results = await rag.search("authentication logic", strategy="semantic")

# Lexical search
results = await rag.search("def authenticate", strategy="lexical")

# Hybrid search (default)
results = await rag.search("user login flow", strategy="hybrid")

for chunk in results.chunks:
    print(f"{chunk.file_path}:{chunk.start_line}")
    print(chunk.content[:100])
```

### Using as Context Manager

```python
async with RAGSystem(repo_path, config, llm_client) as rag:
    stats = await rag.initialize()
    results = await rag.search("error handling")
```

## Configuration

RAG settings in `config/orchestrator-config.yaml`:

```yaml
rag:
  chunk_size: 1000              # Lines per chunk
  chunk_overlap: 200            # Overlap between chunks
  max_retrieved_chunks: 20      # Maximum chunks to return
  max_context_tokens: 8000      # Maximum context size
  semantic_search_enabled: true
  symbol_search_enabled: true
```

Model settings in `config/models.yaml`:

```yaml
embedding_model:
  name: "nomic-embed-text"
  dimensions: 768
```

## Indexing Workflow

1. **Scan Repository**: Walk directory tree, filter files by extension
2. **Extract Metadata**: File size, language, last modified, git history
3. **Extract Symbols**: Parse with tree-sitter to find classes, functions, methods
4. **Chunk Files**: Split content into overlapping chunks
5. **Generate Embeddings**: Create vector embeddings using Ollama
6. **Store in ChromaDB**: Save chunks with metadata and embeddings

## Incremental Updates

The system supports incremental indexing:

1. Check if file exists in index
2. Compare last modified timestamp
3. Skip unchanged files
4. Re-index only modified files
5. Update ChromaDB with new/changed chunks

To force full re-index:

```python
await rag.initialize(force_reindex=True)
```

## Performance Tuning

### Indexing Performance

- **Batch Size**: Increase for faster embedding generation (trade-off: memory)
- **Chunk Size**: Larger chunks = fewer embeddings = faster indexing
- **Parallel Processing**: Embedding generation batches run in parallel

### Retrieval Performance

- **max_retrieved_chunks**: Lower = faster, but less context
- **Strategy**: Semantic-only is faster than hybrid
- **Filters**: Apply language/path filters to narrow search space

### Memory Usage

- Large repositories: Index in batches, use incremental updates
- Limit chunk size to avoid memory issues
- ChromaDB stores embeddings on disk (persistent storage)

## Troubleshooting

### ChromaDB Connection Errors

**Symptom**: `Failed to connect to ChromaDB`

**Solution**:
- Check vector store path is writable
- Ensure ChromaDB is properly installed: `pip install chromadb>=0.4.0`
- Delete corrupted index: `rm -rf data/index/{repo_name}`

### Tree-sitter Parser Failures

**Symptom**: `Failed to initialize {language} parser`

**Solution**:
- Install language parser: `pip install tree-sitter-{language}`
- System falls back to content-only indexing
- Symbol extraction disabled for unsupported languages

### Ripgrep Not Found

**Symptom**: `ripgrep not installed, lexical search disabled`

**Solution**:
- Install ripgrep: `brew install ripgrep` (macOS) or `apt install ripgrep` (Linux)
- System falls back to semantic-only search
- Windows: Download from https://github.com/BurntSushi/ripgrep/releases

### Large File Warnings

**Symptom**: `Skipping large file: {path} (X bytes)`

**Solution**:
- Files > 1MB are skipped by default
- Adjust limit in `indexer.py` if needed
- Consider splitting large files

### Context Token Limit

**Symptom**: `Context exceeds token limit: X > Y`

**Solution**:
- Increase `max_context_tokens` in config
- Reduce `max_retrieved_chunks`
- System automatically prioritizes most relevant chunks

### Binary File Detection

**Symptom**: Files being incorrectly skipped

**Solution**:
- Check exclusion patterns in `RepoIndexer.EXCLUDE_PATTERNS`
- Verify file extension is in `EXTENSION_TO_LANGUAGE` map
- Binary detection checks first 8KB for null bytes

## Adding New Languages

To add support for a new language:

1. **Install tree-sitter parser**:
   ```bash
   pip install tree-sitter-{language}
   ```

2. **Update `indexer.py`**:
   ```python
   EXTENSION_TO_LANGUAGE = {
       ".ext": "newlang",
       # ...
   }
   ```

3. **Initialize parser in `_initialize_parsers()`**:
   ```python
   import tree_sitter_{language} as tslang
   lang = Language(tslang.language())
   parser = Parser(lang)
   self.parsers["newlang"] = parser
   ```

4. **Update symbol extraction** if language has unique syntax

## Index Storage

ChromaDB stores data in `data/index/{repo_name}/`:

- `chroma.sqlite3`: Metadata database
- `*.bin`: Vector embeddings
- Index size: ~10-50MB per 1000 files (depends on file size)

## Limitations

- **Binary files**: Skipped automatically
- **Large files**: > 1MB skipped with warning
- **Context window**: Limited by model (default 8000 tokens)
- **Languages**: Only languages with tree-sitter parsers support symbol extraction
- **Git history**: Requires valid git repository

## Future Enhancements

- **Dependency graph**: Track imports and references
- **Change tracking**: Monitor file modifications in real-time
- **Symbol database**: Persistent symbol index for faster lookups
- **Multi-repo**: Support indexing multiple repositories
- **Custom chunking**: Language-specific chunking strategies
- **Ranking improvements**: ML-based relevance scoring

## API Reference

See docstrings in source files for detailed API documentation:

- `repo_brain/rag_system.py`: Main entry point
- `repo_brain/indexer.py`: File scanning and symbol extraction
- `repo_brain/embeddings.py`: Embedding generation and storage
- `repo_brain/retriever.py`: Multi-modal search
- `repo_brain/context_builder.py`: Context assembly
- `repo_brain/models.py`: Data models
- `repo_brain/exceptions.py`: Exception classes
