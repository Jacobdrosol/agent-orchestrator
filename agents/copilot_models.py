"""
Pydantic models for GitHub Copilot CLI integration.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ExecutionMode(str, Enum):
    """Execution mode for Copilot CLI."""
    DIRECT = "direct"
    BRANCH = "branch"


class CopilotErrorType(str, Enum):
    """Types of Copilot CLI errors."""
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    EXECUTION_ERROR = "execution_error"
    PARSE_ERROR = "parse_error"
    AUTH_ERROR = "auth_error"


class CopilotExecutionRequest(BaseModel):
    """Request model for Copilot CLI execution."""
    spec_path: str = Field(..., description="Path to phase specification file")
    repo_path: str = Field(..., description="Repository root path")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.DIRECT, description="Execution mode")
    findings: Optional[Dict[str, Any]] = Field(default=None, description="Findings from previous pass")
    repo_context: Optional[str] = Field(default=None, description="Additional repository context")
    timeout: int = Field(default=600, description="Execution timeout in seconds")
    pass_number: int = Field(default=1, description="Current pass number")


class CopilotExecutionResult(BaseModel):
    """Result model for Copilot CLI execution."""
    success: bool = Field(..., description="Whether execution succeeded")
    output_path: Optional[str] = Field(default=None, description="Path to Copilot output JSON")
    summary: Optional[str] = Field(default=None, description="Extracted summary from Copilot")
    files_modified: List[str] = Field(default_factory=list, description="List of modified files")
    files_created: List[str] = Field(default_factory=list, description="List of created files")
    execution_time: float = Field(..., description="Duration in seconds")
    error_message: Optional[str] = Field(default=None, description="Error details if failed")
    error_type: Optional[CopilotErrorType] = Field(default=None, description="Type of error if failed")
    raw_output: Optional[str] = Field(default=None, description="Full CLI output for debugging")
    changes_summary: Optional[str] = Field(default=None, description="Brief description of changes")
    tests_added: List[str] = Field(default_factory=list, description="Tests added during execution")
    potential_issues: List[str] = Field(default_factory=list, description="Potential issues or concerns")
    completion_status: Optional[str] = Field(default=None, description="complete|partial|blocked")
    patches: List[Dict[str, Any]] = Field(default_factory=list, description="List of unified diff patches for files")
    patches: List[Dict[str, str]] = Field(default_factory=list, description="Unified diff patches for file changes")


class CopilotValidationResult(BaseModel):
    """Result of Copilot CLI environment validation."""
    valid: bool = Field(..., description="Overall validation status")
    gh_cli_available: bool = Field(default=False, description="Whether gh CLI is available")
    copilot_extension_installed: bool = Field(default=False, description="Whether Copilot extension is installed")
    authenticated: bool = Field(default=False, description="Whether GitHub auth is valid")
    copilot_access: bool = Field(default=False, description="Whether Copilot subscription is active")
    error_messages: List[str] = Field(default_factory=list, description="Validation error messages")
    gh_version: Optional[str] = Field(default=None, description="GitHub CLI version")


class CopilotCLIError(Exception):
    """Custom exception for Copilot CLI failures."""
    
    def __init__(
        self,
        message: str,
        error_type: CopilotErrorType,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
    
    def __str__(self):
        details = [f"CopilotCLIError: {self.args[0]}"]
        if self.command:
            details.append(f"Command: {self.command}")
        if self.exit_code is not None:
            details.append(f"Exit code: {self.exit_code}")
        if self.stderr:
            details.append(f"stderr: {self.stderr[:500]}")
        return "\n".join(details)
