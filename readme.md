# Agent Orchestrator

**Local AI-Powered Orchestration for Automated Software Development**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## Overview

Agent Orchestrator is a sophisticated local orchestration system that mimics Traycer's capabilities using Ollama-powered LLMs. It provides a cost-effective alternative for automated project management and code generation by combining RAG-based repository intelligence, LLM-powered planning, GitHub Copilot CLI integration, and automated verification loops. Unlike cloud-based solutions, Agent Orchestrator runs entirely on your hardware, enabling unlimited orchestration workflows without API costs. The system prioritizes quality over speed, leveraging powerful local models for context-aware planning and spec generation.

---

## Key Features

- **Repo-Aware Planning**: RAG system indexes your entire codebase for context-aware phase planning with semantic search and symbol analysis
- **Local LLM Powered**: Uses Ollama with Qwen2.5-Coder 14B Q4 for high-quality planning and spec generation without API costs
- **Automated Verification Loops**: Runs build, tests, lint, security scans, and spec validation until criteria met with configurable retry limits
- **GitHub Copilot Integration**: Seamlessly feeds specs to Copilot CLI and captures results for automated implementation
- **Highly Customizable**: YAML-based configuration for retry limits, findings thresholds, execution modes, and prompt templates
- **Comprehensive Artifacts**: Saves all specs, findings, and Copilot outputs with timestamps for audit trails and debugging
- **Branch-Per-Phase Mode**: Optional workflow isolation with automatic branch management and clean separation of concerns
- **State Persistence**: SQLite + JSON exports for progress tracking, recovery, and historical analysis

---

## Hardware Requirements

**Minimum Requirements:**
- GPU: 12GB VRAM (e.g., RTX 3060 12GB)
- RAM: 32GB system memory
- Storage: 50GB free disk space for models and vector store

**Recommended Configuration:**
- GPU: RTX 4070 12GB or better
- RAM: 64GB system memory
- Storage: 100GB+ SSD for optimal performance

**Note:** This system is designed for **quality over speed**. Initial planning and spec generation can take 30-60 minutes depending on repository size and complexity. The trade-off is significantly higher quality outputs compared to faster, less sophisticated approaches.

---

## Quick Start

### 1. Install Ollama and Download Models

Follow the comprehensive setup guide in [`docs/OLLAMA_SETUP.md`](docs/OLLAMA_SETUP.md) to:
- Install Ollama for Windows
- Download Qwen2.5-Coder 14B Q4 (recommended for quality)
- Configure GPU acceleration and memory settings
- Verify installation and model availability

### 2. Clone Repository and Install Dependencies

```powershell
# Clone the repository
git clone https://github.com/Jacobdrosol/agent-orchestrator.git
cd agent-orchestrator

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .

# Optional: Install development dependencies
pip install -e ".[dev]"
```

#### Dependency Management

This project uses two files for dependency management:

- **`requirements.txt`**: Lists all runtime dependencies with pinned versions for reproducible installations. Install with:
  ```powershell
  pip install -r requirements.txt
  ```

- **`pyproject.toml`**: Defines package metadata and dependencies for editable installs. The `pip install -e .` command uses this file to install the package in development mode, allowing you to make changes without reinstalling.

### 3. Configure Settings

Copy the default configuration and customize for your environment:

```powershell
# Configuration files will be created in Phase 3
# Edit config/orchestrator-config.yaml for:
# - Model selection and parameters
# - Retry limits and verification thresholds
# - Branch management preferences
# - Artifact storage locations
```

### 4. Run the Orchestrator

```powershell
# PowerShell launcher script (recommended)
.\AgentOrchestrator\scripts\orchestrator.ps1

# Or run directly with Python
python main.py run

# The CLI will:
# - Validate environment (Python, Ollama, GitHub CLI)
# - Load configuration
# - Prompt for documentation file path
# - Prompt for repository path
# - Prompt for target branch
# - Confirm git sync
# - Initialize components (LLM, RAG, state management)
# - Generate and display phase breakdown
# - Request approval before execution
# - Execute all phases with automated verification
# - Display completion summary
```

#### CLI Commands

```powershell
# Start a new orchestration run (interactive)
python main.py run

# Resume an interrupted run
python main.py resume --run-id <run-id>

# Show status of recent runs or specific run
python main.py status
python main.py status --run-id <run-id>

# Validate and display configuration
python main.py config

# Use custom configuration file
python main.py run --config path/to/config.yaml

# Display help
python main.py --help
python main.py run --help
```

#### Example Run Script

Use the example script for automated runs with pre-filled values:

```powershell
# Copy and customize the example script
.\scripts\example_run.ps1

# Or specify parameters directly
.\scripts\example_run.ps1 `
  -DocumentationPath "docs/requirements.md" `
  -RepositoryPath "." `
  -Branch "main" `
  -ConfigPath "config/orchestrator-config.yaml"
```

### 5. Monitor Progress

The orchestrator will:
1. Index your repository using RAG system
2. Generate phase-based execution plan
3. Create detailed specs for each phase
4. Execute specs via GitHub Copilot CLI
5. Run verification loops until criteria met
6. Generate comprehensive findings reports
7. Proceed to next phase or terminate based on results

All artifacts are saved to `data/artifacts/` with timestamps for review.

---

## Project Structure

```
AgentOrchestrator/
├── orchestrator/          # Core orchestration engine (planner, executor, verifier)
├── repo_brain/            # RAG system for repo indexing & retrieval
├── agents/                # Specialized agents (Copilot CLI interface, GitHub bot)
├── templates/             # Jinja2 templates for specs, findings, prompts
├── config/                # YAML configuration files
├── data/                  # Runtime data (vector store, artifacts, state DB)
├── tests/                 # Unit and integration tests
├── docs/                  # Comprehensive documentation
└── scripts/               # Utility scripts (PowerShell launcher, etc.)
```

For detailed architecture and component interactions, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | Complete usage instructions and workflow examples |
| [Architecture](docs/ARCHITECTURE.md) | System design, component interactions, and data flow |
| [Ollama Setup](docs/OLLAMA_SETUP.md) | Installation and model configuration guide |
| [GUI Expansion](docs/GUI_EXPANSION.md) | Guide for building a desktop UI with real-time monitoring |
| [Cross-Platform Support](docs/CROSS_PLATFORM.md) | Adapting the system for Linux and macOS |
| [Contributing](docs/CONTRIBUTING.md) | Development guidelines and contribution process |

---

## Contributing

Agent Orchestrator is in active development. Contributions are welcome! Please see [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for:
- Development setup instructions
- Code style guidelines
- Testing requirements
- Pull request process

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Inspired by Traycer's orchestration capabilities and workflow automation
- Built for local, cost-effective automation using open-source LLMs
- Powered by Ollama, ChromaDB, and GitHub Copilot CLI
- Special thanks to the open-source community for the foundational tools

---

## Roadmap

**Phase 1:** Project foundation and structure ✓  
**Phase 2:** Ollama integration and LLM client implementation ✓  
**Phase 3:** Configuration system and state management ✓  
**Phase 4:** RAG system with ChromaDB and tree-sitter ✓  
**Phase 5:** Core orchestration engine (planner, executor, verifier) ✓  
**Phase 6:** GitHub Copilot CLI agent integration ✓  
**Phase 7:** Verification engine with automated testing ✓  
**Phase 8:** Template system for specs and findings ✓  
**Phase 9:** CLI interface and PowerShell launcher ✓  
**Phase 10:** Documentation and deployment (In Progress)

---

**Questions or issues?** Open an issue on GitHub or consult the documentation.
