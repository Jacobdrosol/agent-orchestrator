# Agent Orchestrator Documentation

This directory contains comprehensive documentation for the Agent Orchestrator system.

## Available Guides

### Getting Started
- [User Guide](USER_GUIDE.md) - Complete usage instructions, workflows, and troubleshooting
- [Ollama Setup](OLLAMA_SETUP.md) - Installation and model configuration for local LLM

### System Documentation
- [Architecture](ARCHITECTURE.md) - System design, component interactions, and data flows
- [State Management](STATE_MANAGEMENT.md) - Database schema and state tracking
- [Configuration Reference](CONFIGURATION.md) - Complete configuration settings guide
- [RAG System](RAG_SYSTEM.md) - Retrieval-Augmented Generation documentation
- [Executor Documentation](EXECUTOR.md) - Execution engine details

### Development Guides
- [Contributing](CONTRIBUTING.md) - Development guidelines and contribution process
- [Cross-Platform Support](CROSS_PLATFORM.md) - Linux and macOS adaptation guide
- [GUI Expansion](GUI_EXPANSION.md) - Guide for building desktop UI

### Integration Guides
- [Copilot Integration](COPILOT_INTEGRATION.md) - GitHub Copilot integration details
- [Patch-Based Copilot Integration](patch_based_copilot_integration.md) - Alternative integration approach

### Testing and Verification
- [Verification Guide](VERIFICATION.md) - Testing and verification procedures

## Quick Links

- [Project README](../README.md) - Main project documentation
- [Configuration Files](../config/README.md) - Configuration management
- [Examples Directory](examples/README.md) - Configuration examples and sample docs
- [Code Examples](examples/) - Usage examples for various components

## Documentation Structure

```
docs/
├── README.md                              # This file
├── USER_GUIDE.md                          # Complete user guide
├── ARCHITECTURE.md                        # System architecture
├── CONTRIBUTING.md                        # Contribution guidelines
├── GUI_EXPANSION.md                       # GUI development guide
├── CROSS_PLATFORM.md                      # Cross-platform support
├── OLLAMA_SETUP.md                        # Ollama installation
├── STATE_MANAGEMENT.md                    # State system docs
├── CONFIGURATION.md                       # Config reference
├── RAG_SYSTEM.md                          # RAG documentation
├── EXECUTOR.md                            # Executor docs
├── COPILOT_INTEGRATION.md                 # Copilot integration
├── VERIFICATION.md                        # Verification guide
└── examples/                              # Examples directory
    ├── README.md                          # Examples overview
    ├── development-config.yaml            # Dev configuration
    ├── production-config.yaml             # Prod configuration
    ├── sample-issue-doc.md                # Issue doc template
    ├── sample-issue-doc.json              # Issue JSON format
    ├── state_usage.py                     # State management example
    ├── planner_usage.py                   # Planner example
    ├── rag_usage.py                       # RAG example
    └── llm_client_usage.py                # LLM client example
```

## Getting Help

1. **Start with the User Guide**: [USER_GUIDE.md](USER_GUIDE.md) covers most common use cases
2. **Check Configuration**: [CONFIGURATION.md](CONFIGURATION.md) explains all settings
3. **Review Examples**: [examples/](examples/) directory contains working examples
4. **Search Issues**: Check GitHub issues for known problems and solutions
5. **Ask Questions**: Open a GitHub Discussion for help

## Contributing to Documentation

Documentation contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Writing clear documentation
- Following markdown conventions
- Adding examples
- Updating existing docs

## Documentation Standards

- **Clear and Concise**: Use simple language and short sentences
- **Examples**: Include code examples and usage patterns
- **Up-to-Date**: Keep docs synchronized with code changes
- **Cross-Referenced**: Link to related documentation
- **Tested**: Verify examples actually work
