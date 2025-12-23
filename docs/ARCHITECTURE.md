# Agent Orchestrator Architecture

## Overview

The Agent Orchestrator is a modular system that orchestrates AI agents to complete complex software development tasks. It uses a multi-phase approach with state management, RAG-based context retrieval, and comprehensive verification.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Main Orchestrator                        │
│                          (main.py)                               │
└───────┬─────────────────────────────────────────────────────────┘
        │
        ├──► Configuration System (config.py)
        │    └──► YAML Config Files
        │
        ├──► State Manager (state.py)
        │    └──► SQLite Database (orchestrator.db)
        │
        ├──► RAG System (rag/)
        │    ├──► Document Processor
        │    ├──► Vector Store (ChromaDB)
        │    └──► Retriever
        │
        ├──► Planning Agent (planner.py)
        │    └──► LLM Client (Ollama)
        │
        ├──► Execution Engine
        │    ├──► Executor Agents
        │    ├──► GitHub Copilot Integration
        │    └──► Retry Logic
        │
        └──► Verification System (verifier.py)
             ├──► Build System
             ├──► Test Runner
             ├──► Code Analysis
             └──► Findings Reporter
```

## Core Components

### 1. Main Orchestrator (`main.py`)

**Responsibility:** Coordinates all components and manages the execution flow

**Key Functions:**
- Parse command-line arguments
- Initialize configuration and state
- Delegate to planning, execution, and verification phases
- Handle recovery and cleanup

**Flow:**
```python
1. Load configuration
2. Initialize state manager
3. Create or resume run
4. Planning phase → create phases
5. Execution loop:
   - For each phase:
     - Execute with retries
     - Record findings
     - Check thresholds
6. Verification phase
7. Generate summary and cleanup
```

### 2. Configuration System (`orchestrator/config.py`)

**Responsibility:** Load, validate, and merge configuration settings

**Architecture:**

```
ConfigLoader
├── load_config() → OrchestratorConfig
├── merge_configs() → Deep merge logic
└── validate() → Pydantic validation

OrchestratorConfig (Pydantic model)
├── ExecutionConfig
├── FindingsThresholds
├── VerificationConfig
├── RagConfig
├── GitConfig
├── ArtifactsConfig
├── LoggingConfig
└── ModelOverrides
```

**Key Features:**
- YAML-based configuration
- Deep merging of base + local configs
- Pydantic validation with type checking
- Path resolution and directory creation
- Default values with sensible fallbacks

### 3. State Management System (`orchestrator/state.py`)

**Responsibility:** Persist and manage orchestration state

**Database Schema:**

```
runs (Orchestration runs)
  ├── id (TEXT PRIMARY KEY)
  ├── task (TEXT)
  ├── status (TEXT)
  ├── created_at, started_at, completed_at (TEXT)
  └── metadata (JSON)

phases (Execution phases)
  ├── id (TEXT PRIMARY KEY)
  ├── run_id (FK → runs.id)
  ├── name, description (TEXT)
  ├── status, dependencies (TEXT/JSON)
  ├── retries, max_retries (INTEGER)
  └── timestamps (TEXT)

executions (Execution attempts)
  ├── id (TEXT PRIMARY KEY)
  ├── phase_id (FK → phases.id)
  ├── run_id (FK → runs.id)
  ├── attempt_number (INTEGER)
  ├── status, error (TEXT)
  └── timestamps (TEXT)

findings (Verification findings)
  ├── id (TEXT PRIMARY KEY)
  ├── execution_id (FK → executions.id)
  ├── run_id (FK → runs.id)
  ├── severity, category (TEXT)
  ├── message, location (TEXT)
  └── resolved, resolved_at (BOOLEAN/TEXT)

artifacts (Generated artifacts)
  ├── id (TEXT PRIMARY KEY)
  ├── run_id, phase_id (FK)
  ├── name, path, type (TEXT)
  ├── size, hash (INTEGER/TEXT)
  └── created_at (TEXT)

manual_interventions (Manual actions)
  ├── id (TEXT PRIMARY KEY)
  ├── run_id, phase_id (FK)
  ├── reason, action_required (TEXT)
  ├── status, resolved_at (TEXT)
  └── created_at (TEXT)
```

**StateManager API:**

```python
# Run management
await state.create_run(task, plan)
await state.update_run_status(run_id, status)
await state.get_run(run_id)
await state.list_runs(status_filter)

# Phase management
await state.create_phase(run_id, phase_data)
await state.update_phase_status(phase_id, status)
await state.get_phases_for_run(run_id)

# Execution tracking
await state.create_execution(phase_id, run_id, attempt)
await state.complete_execution(execution_id, output)
await state.fail_execution(execution_id, error)

# Findings management
await state.add_finding(execution_id, finding)
await state.get_findings_summary(run_id)

# Recovery
await state.get_recoverable_runs()
await state.recover_run(run_id)

# Export
await state.export_run_summary(run_id, format="markdown")
```

### 4. RAG System (`repo_brain/`)

**Responsibility:** Provide contextual information from codebase

**Components:**

```
RAGSystem
├── DocumentProcessor
│   ├── parse_code_file()
│   ├── extract_metadata()
│   └── chunk_document()
│
├── VectorStore (ChromaDB)
│   ├── add_documents()
│   ├── search()
│   └── update_collection()
│
└── Retriever
    ├── retrieve_context()
    ├── rerank_results()
    └── format_context()
```

**Data Flow:**

```
1. Index Phase:
   Repository Files → DocumentProcessor → Chunks + Metadata
                                            ↓
                                       VectorStore
                                            ↓
                                    Embeddings (Ollama)

2. Retrieval Phase:
   Query → Retriever → VectorStore.search()
                            ↓
                     Top-K Results → Reranker
                                         ↓
                                  Formatted Context
```

**Key Features:**
- Automatic codebase indexing
- Semantic search with embeddings
- Result reranking for relevance
- Metadata filtering (file type, path, etc.)
- Incremental updates

### 5. Planning Agent (`agents/planner.py`)

**Responsibility:** Break down tasks into executable phases

**Algorithm:**

```python
1. Retrieve relevant context from RAG
2. Analyze task requirements
3. Identify dependencies and risks
4. Generate phase plan:
   - Phase name, description
   - Dependencies (other phases)
   - Estimated complexity
   - Risk level
5. Validate plan structure
6. Return structured plan (JSON)
```

**Phase Structure:**

```json
{
  "phases": [
    {
      "id": "phase-001",
      "name": "Setup authentication models",
      "description": "Create User and Session models",
      "dependencies": [],
      "estimated_complexity": "medium",
      "risk_level": "low",
      "verification_criteria": [
        "Models are properly defined",
        "Database migrations are created",
        "Basic validation tests pass"
      ]
    }
  ]
}
```

### 6. Execution Engine

**Responsibility:** Execute phases with retry logic and error handling

**Components:**

```
ExecutionEngine
├── PhaseExecutor
│   ├── execute_phase()
│   ├── retry_on_failure()
│   └── record_artifacts()
│
├── CopilotIntegration (optional)
│   ├── suggest_changes()
│   ├── execute_edits()
│   └── validate_output()
│
└── ErrorHandler
    ├── classify_error()
    ├── determine_retry()
    └── escalate_if_needed()
```

**Execution Flow:**

```
For each phase:
  1. Load phase context from RAG
  2. Generate execution prompt
  3. Call executor agent (LLM)
  4. Parse agent output
  5. Apply changes (via Copilot or direct)
  6. Record execution in state
  7. If failed and retries available:
     - Increment retry counter
     - Analyze failure reason
     - Adjust prompt
     - Retry (go to step 2)
  8. If succeeded:
     - Record artifacts
     - Mark phase complete
  9. If failed permanently:
     - Record error
     - Check if critical
     - Abort or continue per config
```

**Retry Strategy:**

```python
attempt = 1
while attempt <= max_retries:
    try:
        result = execute_phase(phase)
        return result
    except Exception as e:
        if is_retriable(e) and attempt < max_retries:
            wait_time = exponential_backoff(attempt)
            await asyncio.sleep(wait_time)
            attempt += 1
        else:
            raise
```

### 7. Verification System (`orchestrator/verifier.py`)

**Responsibility:** Validate execution quality and correctness

**Verification Pipeline:**

```
1. Build Verification
   ├── Run build command
   ├── Parse build output
   └── Record build errors as findings

2. Test Verification
   ├── Run test suite
   ├── Parse test results
   └── Record test failures as findings

3. Lint Verification
   ├── Run linter
   ├── Parse lint output
   └── Record lint issues as findings

4. Security Verification (optional)
   ├── Run security scanners
   ├── Parse security reports
   └── Record vulnerabilities as findings

5. Custom Verification
   ├── Run custom test commands
   ├── Parse outputs
   └── Record issues as findings
```

**Findings Classification:**

```python
Finding:
  - severity: "major" | "medium" | "minor"
  - category: "build" | "test" | "lint" | "security" | "custom"
  - message: str
  - location: str (file:line)
  - resolved: bool
```

**Threshold Checking:**

```python
summary = await state.get_findings_summary(run_id)
if summary.major > thresholds.max_major:
    abort("Too many major findings")
elif summary.medium > thresholds.max_medium:
    warning("Approaching medium findings threshold")
```

### 8. LLM Client (`orchestrator/llm_client.py`)

**Responsibility:** Unified interface to LLM providers

**Architecture:**

```
LLMClient
├── OllamaClient
│   ├── chat()
│   ├── generate()
│   └── embed()
│
├── OpenAIClient (future)
└── AnthropicClient (future)

ModelConfig (from models.yaml)
├── name: str
├── provider: "ollama" | "openai" | "anthropic"
├── temperature: float
├── max_tokens: int
├── context_window: int
└── capabilities: List[str]
```

**Usage Pattern:**

```python
client = LLMClient(model_config)

response = await client.chat(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.7,
    max_tokens=4000
)

result = parse_response(response)
```

## Data Flows

### Task Execution Flow

```
User Request
    ↓
Load Config & Init State
    ↓
Create Run Record ──────────────────────┐
    ↓                                    │
Planning Agent                           │
    ├──► RAG: Retrieve context          │
    ├──► LLM: Generate plan             │
    └──► State: Create phases           │
    ↓                                    │
For Each Phase:                          │
    ├──► State: Create execution        │
    ├──► RAG: Retrieve context          │
    ├──► LLM: Execute phase             │
    ├──► Apply changes                  │
    ├──► State: Record results ─────────┤
    ↓                                    │
Verification                             │
    ├──► Run build/tests/lint           │
    ├──► State: Record findings ────────┤
    ↓                                    │
Generate Summary                         │
    ├──► State: Export results ─────────┤
    ├──► Create markdown report         │
    └──► Cleanup artifacts              │
    ↓                                    │
Complete ◄──────────────────────────────┘
```

### Context Retrieval Flow

```
Task/Phase Description
    ↓
Identify Keywords & Entities
    ↓
RAG Retriever
    ├──► Query Vector Store
    │        ├──► Semantic search
    │        └──► Metadata filtering
    ├──► Get Top-K Results
    ├──► Rerank by Relevance
    └──► Format Context
    ↓
LLM Prompt with Context
```

### State Recovery Flow

```
Interruption Detected
    ↓
Query Recoverable Runs
    ├──► runs WHERE status = 'executing'
    └──► phases WHERE status = 'in_progress'
    ↓
Select Run to Resume
    ↓
Load Run State
    ├──► Load phases
    ├──► Load executions
    └──► Load findings
    ↓
Resume from Last Phase
    ├──► Skip completed phases
    ├──► Retry failed phases
    └──► Continue execution
```

## Extension Points

### 1. Custom Agents

Add specialized agents for specific tasks:

```python
# agents/custom_agent.py
class CustomAgent:
    async def execute(self, context: dict) -> dict:
        # Custom logic
        return result

# Register in main.py
agents["custom"] = CustomAgent(llm_client)
```

### 2. Custom Verifiers

Add domain-specific verification:

```python
# orchestrator/custom_verifier.py
async def custom_verify(run_id: str, state: StateManager) -> List[Finding]:
    findings = []
    # Custom verification logic
    return findings

# Register in verifier.py
verifiers.append(custom_verify)
```

### 3. Custom RAG Processors

Add support for new file types:

```python
# repo_brain/processors/custom_processor.py
class CustomProcessor(DocumentProcessor):
    def can_process(self, file_path: str) -> bool:
        return file_path.endswith(".custom")
    
    def process(self, file_path: str) -> List[Document]:
        # Custom parsing logic
        return documents

# Register in rag_system.py
processors.append(CustomProcessor())
```

### 4. Custom LLM Providers

Add new LLM backends:

```python
# orchestrator/providers/custom_provider.py
class CustomProvider(LLMProvider):
    async def chat(self, messages, **kwargs):
        # Custom API integration
        return response

# Register in llm_client.py
providers["custom"] = CustomProvider
```

## Security Considerations

### 1. Secrets Management

- Never commit secrets to configuration
- Use environment variables for sensitive data
- Store API keys in secure vaults
- Rotate credentials regularly

### 2. Code Execution

- Sandbox execution environment if possible
- Validate LLM outputs before execution
- Limit file system access
- Monitor resource usage

### 3. Database Security

- Use parameterized queries (SQL injection protection)
- Encrypt sensitive data at rest
- Backup database regularly
- Limit database file permissions

### 4. Network Security

- Use HTTPS for API calls
- Validate SSL certificates
- Implement rate limiting
- Log all network requests

## Performance Optimization

### 1. RAG System

- Index incrementally (only changed files)
- Use efficient embeddings model
- Cache frequent queries
- Limit context window size

### 2. State Management

- Use connection pooling
- Vacuum database periodically
- Archive old runs
- Compress artifacts

### 3. LLM Calls

- Batch similar requests
- Use streaming for long responses
- Implement caching for identical prompts
- Monitor token usage

### 4. Concurrency

- Parallelize independent phases
- Use async/await throughout
- Limit concurrent LLM calls
- Pool expensive resources

## Monitoring and Observability

### 1. Logging

- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Separate log files per component
- Rotate logs by size/time

### 2. Metrics

- Execution duration per phase
- LLM token usage
- Database query performance
- Finding counts by severity

### 3. Tracing

- Trace IDs for request correlation
- Phase execution timeline
- Error propagation tracking
- Performance bottleneck identification

### 4. Alerting

- Critical errors (immediate notification)
- Threshold violations (warning)
- Resource exhaustion (proactive)
- System health checks

## Testing Strategy

### 1. Unit Tests

- Test individual components in isolation
- Mock external dependencies
- Cover edge cases and error paths
- Aim for >80% code coverage

### 2. Integration Tests

- Test component interactions
- Use real database (in-memory or temp)
- Mock external APIs (Ollama, etc.)
- Verify state transitions

### 3. End-to-End Tests

- Test complete workflows
- Use small test tasks
- Verify outputs and artifacts
- Test recovery scenarios

### 4. Performance Tests

- Benchmark RAG retrieval
- Measure LLM response times
- Profile database queries
- Load test with concurrent runs

## Deployment Considerations

### Development

- Local Ollama instance
- SQLite database
- File-based artifacts
- Console logging

### Production

- Managed LLM service (optional)
- PostgreSQL database (for concurrency)
- Object storage for artifacts (S3, etc.)
- Centralized logging (ELK, Datadog)
- Containerization (Docker)
- Orchestration (Kubernetes)

## Future Enhancements

1. **Multi-Agent Collaboration**: Multiple agents working on different phases concurrently
2. **Learning System**: Learn from past runs to improve planning
3. **GUI**: Desktop application for visual monitoring
4. **Cloud Integration**: Deploy to cloud platforms
5. **Plugin System**: Dynamic loading of extensions
6. **Distributed Execution**: Scale across multiple machines
7. **Advanced Analytics**: ML-based insight generation
8. **Real-time Collaboration**: Multiple users orchestrating together

## References

- [State Management Documentation](STATE_MANAGEMENT.md)
- [Configuration Reference](CONFIGURATION.md)
- [RAG System Documentation](RAG_SYSTEM.md)
- [Executor Documentation](EXECUTOR.md)
- [User Guide](USER_GUIDE.md)
