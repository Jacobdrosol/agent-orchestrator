# Agent Orchestrator
Local AI-Powered Orchestration for Automated Software Development

## Overview
Agent Orchestrator is a local orchestration system designed to mimic Traycer-style workflows using Ollama. It helps you turn high-level product or engineering goals into structured phases, GitHub issues, and detailed implementation specs, then executes iterative verification loops until acceptance criteria are met. The system is built for cost-effective automation: it runs locally, relies on RAG-based repo intelligence for context, and integrates with GitHub Copilot for code changes. By storing comprehensive artifacts (plans, specs, diffs, findings, and summaries) with state persistence, you can run unlimited orchestration workflows without per-request API costs and recover cleanly from interruptions.

## Key Features
- Repo-Aware Planning: RAG system indexes your codebase for context-aware phase planning
- Local LLM Powered: Uses Ollama with Qwen2.5-Coder 14B Q4 for high-quality planning and spec generation
- Automated Verification Loops: Runs build, tests, lint, security scans, and spec validation until criteria met
- GitHub Copilot Integration: Feeds specs to Copilot CLI and captures outputs and summaries
- Highly Customizable: YAML-based configuration for retry limits, findings thresholds, execution modes
- Comprehensive Artifacts: Saves specs, findings, and Copilot outputs with timestamps
- Branch-Per-Phase Mode: Optional isolation workflow with automatic branch management
- State Persistence: SQLite + JSON exports for progress tracking and recovery

## Hardware Requirements
- Minimum: 12GB VRAM GPU, 32GB RAM, 50GB free disk space
- Recommended: RTX 4070 12GB, 64GB RAM
- Note: Quality-focused, not speed-focused. Planning can take 30-60 minutes depending on repo size and settings.

## Quick Start
1) Install Ollama and download Qwen2.5-Coder 14B Q4
   - See docs/OLLAMA_SETUP.md

2) Clone this repository and install dependencies
   - pip install -e .

3) Configure settings
   - Edit config/orchestrator-config.yaml

4) Run the orchestrator
   - python -m orchestrator
   - Or on Windows: .\scripts\orchestrator.ps1

5) Follow interactive prompts
   - Select documentation file, repo path, and branch
   - Review generated phases and approve before execution (recommended)

## Project Structure
- orchestrator/               Core package (CLI entrypoints, pipeline, adapters)
- config/                     Configuration files (YAML)
- data/                       Local runtime data (index, artifacts, database)
- docs/                       Architecture and usage docs
- scripts/                    Helper scripts (PowerShell, bash)
- tests/                      Unit/integration tests

For detailed design and system flow, see docs/ARCHITECTURE.md.

## Documentation
- User Guide: docs/USER_GUIDE.md
- Architecture: docs/ARCHITECTURE.md
- Ollama Setup: docs/OLLAMA_SETUP.md
- GUI Expansion: docs/GUI_EXPANSION.md
- Cross-Platform: docs/CROSS_PLATFORM.md
- Contributing: docs/CONTRIBUTING.md

## Contributing
This project is in active development. Please read docs/CONTRIBUTING.md for guidelines and workflow.

## License
MIT License. See LICENSE.

## Acknowledgments
Inspired by Traycer-style orchestration workflows.
Built for local, cost-effective automation.
