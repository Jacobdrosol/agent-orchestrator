"""Custom exceptions for Agent Orchestrator."""


class OrchestratorError(Exception):
    """Base exception for all orchestrator errors."""
    pass


class StateError(OrchestratorError):
    """Base exception for state management errors."""
    pass


class RunNotFoundError(StateError):
    """Raised when a run ID cannot be found in the database."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Run not found: {run_id}")


class PhaseNotFoundError(StateError):
    """Raised when a phase ID cannot be found in the database."""
    
    def __init__(self, phase_id: str):
        self.phase_id = phase_id
        super().__init__(f"Phase not found: {phase_id}")


class ExecutionNotFoundError(StateError):
    """Raised when an execution ID cannot be found in the database."""
    
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        super().__init__(f"Execution not found: {execution_id}")


class DatabaseError(StateError):
    """Raised when a database operation fails."""
    
    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(f"Database error: {message}")


class ConfigError(OrchestratorError):
    """Raised when configuration loading or validation fails."""
    pass


class ValidationError(OrchestratorError):
    """Raised when data validation fails."""
    pass
