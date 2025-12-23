# Agent Orchestrator User Guide

## Overview

Agent Orchestrator is an intelligent system for automating complex software development workflows using AI agents. It breaks down large tasks into phases, executes them with retries, verifies results, and maintains state across interruptions.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuration](#configuration)
3. [Basic Usage](#basic-usage)
4. [Workflows](#workflows)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Topics](#advanced-topics)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Ollama (for local LLM support)
- 8GB+ RAM recommended

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Agent\ Orchestrator
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Ollama:**
   - Follow [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for installation
   - Pull recommended models:
     ```bash
     ollama pull qwen2.5-coder:7b
     ollama pull deepseek-r1:8b
     ```

4. **Configure the system:**
   ```bash
   cp config/orchestrator-config.yaml config/orchestrator-config.local.yaml
   # Edit local config as needed
   ```

### Verification

Run verification tests to ensure everything is working:

```bash
python verify_patch_implementation.py
```

## Configuration

### Configuration Files

The system uses YAML configuration with precedence:

1. `config/orchestrator-config.local.yaml` (highest priority, git-ignored)
2. `config/orchestrator-config.yaml` (base configuration)
3. `config/models.yaml` (model definitions)

### Key Settings

#### Execution Settings

```yaml
execution:
  max_retries: 3
  enable_copilot: true
  copilot_mode: "suggest"  # suggest, execute, hybrid
```

#### Findings Thresholds

```yaml
findings_thresholds:
  max_major: 0      # No major issues allowed
  max_medium: 5     # Up to 5 medium issues
  max_minor: 20     # Up to 20 minor issues
```

#### Verification Settings

```yaml
verification:
  run_build: true
  run_tests: true
  run_lint: true
  run_security_checks: false
```

See [CONFIGURATION.md](CONFIGURATION.md) for complete reference.

## Workflows

### Optional: GitHub Issue Consolidation Workflow

Before running the orchestrator, you can use the **GitHub Issue Consolidator** to fetch and consolidate GitHub issues into structured documentation.

#### When to Use

- You have a parent GitHub issue (epic) with multiple child issues (sub-tasks)
- You want to create comprehensive requirements documentation from GitHub issues
- You need to track completion status across multiple issues
- You want to use GitHub issues as orchestrator input

#### Consolidation Steps

1. **Set up GitHub authentication:**
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here  # Linux/macOS
   $env:GITHUB_TOKEN = "ghp_your_token_here"  # Windows PowerShell
   ```

2. **Run the consolidator:**
   ```bash
   python -m agents.issue_consolidator \
     --parent 100 \
     --children 101,102,103 \
     --completed 101 \
     --output project-requirements \
     --repo owner/repo
   ```

3. **Review generated files:**
   - `project-requirements.md` - Markdown documentation
   - `project-requirements.json` - Structured JSON data

4. **Use with orchestrator:**
   ```bash
   python main.py --input-file project-requirements.md
   ```

For complete documentation, see [`ISSUE_CONSOLIDATOR.md`](ISSUE_CONSOLIDATOR.md).

### Standard Orchestrator Workflow

1. **Planning Phase**
   - Task is analyzed by the planner agent
   - Phases are created with dependencies
   - Risk assessment is performed

2. **Execution Phase**
   - Each phase is executed in order
   - Retries on failure (up to max_retries)
   - Progress is logged to database

3. **Verification Phase**
   - Code is built and tested
   - Findings are classified by severity
   - Reports are generated

4. **Completion**
   - Summary is exported
   - Artifacts are saved
   - Database is cleaned up

## Basic Usage

### Running the Orchestrator

#### Simple Task Execution

```bash
python main.py "Implement user authentication system"
```

#### With Custom Configuration

```bash
python main.py --config config/orchestrator-config.local.yaml "Add REST API endpoints"
```

#### Resume Interrupted Run

```bash
python main.py --resume <run_id>
```

### Command-Line Options

```
usage: main.py [-h] [--config CONFIG] [--resume RUN_ID] [--dry-run] [--verbose] [task]

positional arguments:
  task              Task description

optional arguments:
  -h, --help        Show this help message
  --config CONFIG   Path to configuration file
  --resume RUN_ID   Resume a previous run
  --dry-run         Plan only, don't execute
  --verbose         Enable verbose logging
```

### Example: Feature Implementation

```bash
# Start the orchestration
python main.py "Add search functionality to user dashboard"

# The system will:
# 1. Analyze the task and create phases
# 2. Execute backend changes
# 3. Execute frontend changes
# 4. Run tests and verification
# 5. Generate summary report
```

### Example: Bug Fix

```bash
# Fix a specific bug
python main.py "Fix memory leak in data processing pipeline"

# The system will:
# 1. Analyze the issue
# 2. Locate the problematic code
# 3. Implement the fix
# 4. Verify with existing tests
# 5. Add regression tests
```

### Recovery Workflow

If execution is interrupted:

```bash
# List recoverable runs
sqlite3 data/orchestrator.db "SELECT id, task, status FROM runs ORDER BY created_at DESC LIMIT 5;"

# Resume a specific run
python main.py --resume <run_id>
```

## Troubleshooting

### Common Issues

#### Ollama Connection Failed

**Problem:** Cannot connect to Ollama server

**Solution:**
```bash
# Check if Ollama is running
ollama list

# Start Ollama service (Linux/macOS)
systemctl start ollama

# Start Ollama service (Windows)
# Run Ollama from Start Menu or desktop shortcut
```

#### Model Not Found

**Problem:** Specified model is not available

**Solution:**
```bash
# Pull the required model
ollama pull qwen2.5-coder:7b

# Verify models are available
ollama list
```

#### Configuration Errors

**Problem:** Configuration validation fails

**Solution:**
- Check YAML syntax (no tabs, proper indentation)
- Verify all required fields are present
- Check data types match expected values
- Review logs in `data/logs/orchestrator.log`

#### Database Locked

**Problem:** SQLite database is locked

**Solution:**
```bash
# Check for stale connections
lsof data/orchestrator.db  # Linux/macOS
handle.exe data/orchestrator.db  # Windows

# If needed, restart the orchestrator
# The system will recover automatically
```

#### Test Failures

**Problem:** Verification tests fail unexpectedly

**Solution:**
1. Review findings in the database:
   ```bash
   sqlite3 data/orchestrator.db "SELECT * FROM findings WHERE severity='major';"
   ```

2. Check test command configuration:
   ```yaml
   verification:
     test_command: "pytest"  # Ensure this matches your setup
   ```

3. Run tests manually to debug:
   ```bash
   pytest tests/
   ```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
python main.py --verbose "Task description"
```

Logs are written to:
- Console (INFO level by default)
- `data/logs/orchestrator.log` (DEBUG level)

### Getting Help

1. Check documentation:
   - [Architecture Guide](ARCHITECTURE.md)
   - [Configuration Reference](CONFIGURATION.md)
   - [State Management](STATE_MANAGEMENT.md)

2. Review examples:
   - `docs/examples/state_usage.py`
   - `docs/examples/planner_usage.py`
   - `docs/examples/rag_usage.py`

3. Check database state:
   ```bash
   sqlite3 data/orchestrator.db
   .schema
   SELECT * FROM runs ORDER BY created_at DESC LIMIT 1;
   ```

## Advanced Topics

### Custom Verification Tests

Define custom test commands in configuration:

```yaml
verification:
  custom_tests:
    - name: "Integration Tests"
      command: "pytest tests/integration/"
      required: true
    - name: "Performance Tests"
      command: "pytest tests/performance/"
      required: false
```

### Manual Interventions

If a phase requires manual action:

1. The system pauses and creates an intervention record
2. Perform the required action manually
3. Resume execution:
   ```bash
   python main.py --resume <run_id>
   ```

### Artifact Management

Artifacts are saved in `data/artifacts/<run_id>/`:

- Phase outputs
- Test reports
- Build logs
- Generated files

Configure retention:

```yaml
artifacts:
  retention_days: 30
  compress_after_days: 7
  max_size_mb: 1000
```

### RAG System Integration

The orchestrator includes a RAG (Retrieval-Augmented Generation) system for context:

```yaml
rag:
  chunk_size: 1000
  chunk_overlap: 200
  top_k_results: 5
  rerank_results: true
```

See [RAG_SYSTEM.md](RAG_SYSTEM.md) for details.

### Model Overrides

Override models for specific runs:

```yaml
model_overrides:
  planner_model: "deepseek-r1:8b"
  executor_model: "qwen2.5-coder:7b"
  verifier_model: "qwen2.5-coder:7b"
```

### Git Integration

Automated git operations:

```yaml
git:
  auto_pull: true
  auto_commit: false
  commit_message_template: "feat: {phase_name}"
```

## Best Practices

1. **Use Local Config**: Keep sensitive settings in `orchestrator-config.local.yaml`
2. **Monitor Findings**: Check findings thresholds match your project standards
3. **Review Phase Plans**: Use `--dry-run` to preview before execution
4. **Enable Verification**: Always run tests in CI/CD environments
5. **Clean Up**: Regularly vacuum the database and clean old artifacts
6. **Backup State**: Keep backups of `data/orchestrator.db` for critical runs
7. **Version Control**: Commit configuration changes to track system evolution
8. **Resource Management**: Monitor RAM usage with large context windows

## Quick Reference

### Common Commands

```bash
# Start new task
python main.py "Task description"

# Resume interrupted run
python main.py --resume <run_id>

# Dry run (plan only)
python main.py --dry-run "Task description"

# Verbose output
python main.py --verbose "Task description"

# Custom config
python main.py --config path/to/config.yaml "Task description"
```

### Configuration Quick Edit

```bash
# Edit local configuration
nano config/orchestrator-config.local.yaml

# Validate configuration
python -c "from orchestrator import ConfigLoader; ConfigLoader.load_config('config/orchestrator-config.local.yaml')"
```

### Database Queries

```bash
sqlite3 data/orchestrator.db

# List recent runs
SELECT id, task, status, created_at FROM runs ORDER BY created_at DESC LIMIT 10;

# Check phases for a run
SELECT name, status, retries FROM phases WHERE run_id='<run_id>';

# View findings
SELECT severity, category, message FROM findings WHERE execution_id IN (SELECT id FROM executions WHERE run_id='<run_id>');
```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand system design
- Explore [examples](examples/) for usage patterns
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Review [GUI_EXPANSION.md](GUI_EXPANSION.md) for desktop UI plans
