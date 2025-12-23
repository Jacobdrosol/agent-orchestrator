# Runtime Data

This directory stores runtime data including vector stores, artifacts, and state database.

## Subdirectories

### `index/`
Contains ChromaDB vector store and embeddings for RAG system:
- Repository code embeddings
- Symbol and function indices
- Semantic search data structures

### `artifacts/`
Stores generated outputs and execution artifacts:
- Phase specifications
- Findings reports
- Copilot CLI outputs
- Timestamped execution logs

## Important Notes

**Warning:** Contents of this directory are excluded from version control via `.gitignore`.

- Vector stores can be rebuilt by re-indexing the repository
- Artifacts are regenerated during each orchestration run
- State database tracks progress and can be exported to JSON
- Only `.gitkeep` files are version-controlled to preserve directory structure

## Data Retention

Configure data retention policies in `config/orchestrator-config.yaml`:
- Artifact cleanup thresholds
- Vector store refresh intervals
- State backup schedules
