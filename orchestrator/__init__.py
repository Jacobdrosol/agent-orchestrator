"""
Agent Orchestrator - Local AI-Powered Orchestration System

A cost-effective alternative to cloud-based orchestration tools,
powered by Ollama and designed for quality over speed.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

# Package-level imports
from orchestrator.llm_client import (
    OllamaClient,
    GenerateRequest,
    GenerateResponse,
    EmbedRequest,
    EmbedResponse,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaGenerationError,
)

from orchestrator.state import StateManager
from orchestrator.config import (
    OrchestratorConfig,
    ConfigLoader,
    get_default_config,
)
from orchestrator.models import (
    RunState,
    PhaseState,
    ExecutionState,
    Finding,
    Artifact,
    ManualIntervention,
    RunSummary,
)
from orchestrator.exceptions import (
    OrchestratorError,
    StateError,
    RunNotFoundError,
    PhaseNotFoundError,
    ExecutionNotFoundError,
    DatabaseError,
    ConfigError,
    ValidationError,
)

__all__ = [
    # LLM Client
    "OllamaClient",
    "GenerateRequest",
    "GenerateResponse",
    "EmbedRequest",
    "EmbedResponse",
    "OllamaConnectionError",
    "OllamaModelNotFoundError",
    "OllamaGenerationError",
    # State Management
    "StateManager",
    # Configuration
    "OrchestratorConfig",
    "ConfigLoader",
    "get_default_config",
    # Models
    "RunState",
    "PhaseState",
    "ExecutionState",
    "Finding",
    "Artifact",
    "ManualIntervention",
    "RunSummary",
    # Exceptions
    "OrchestratorError",
    "StateError",
    "RunNotFoundError",
    "PhaseNotFoundError",
    "ExecutionNotFoundError",
    "DatabaseError",
    "ConfigError",
    "ValidationError",
]
