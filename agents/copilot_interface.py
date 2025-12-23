"""
GitHub Copilot CLI Interface for executing phase specifications.
"""

import asyncio
import json
import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from jinja2 import Template

from agents.copilot_models import (
    CopilotExecutionRequest,
    CopilotExecutionResult,
    CopilotValidationResult,
    CopilotCLIError,
    CopilotErrorType,
    ExecutionMode,
)

logger = logging.getLogger(__name__)


class CopilotCLIInterface:
    """Interface for interacting with GitHub Copilot CLI."""
    
    def __init__(
        self,
        cli_path: str = "gh",
        timeout: int = 600,
        capture_raw_output: bool = True,
        validate_on_startup: bool = False,
    ):
        """
        Initialize Copilot CLI interface.
        
        Args:
            cli_path: Path to gh CLI executable
            timeout: Default timeout in seconds
            capture_raw_output: Whether to capture raw CLI output
            validate_on_startup: Whether to validate environment on init (deprecated, use async validate_environment())
        """
        self.cli_path = cli_path
        self.default_timeout = timeout
        self.capture_raw_output = capture_raw_output
        
        if validate_on_startup:
            logger.warning(
                "validate_on_startup is deprecated and ignored. Call validate_environment() asynchronously instead."
            )
    
    async def validate_environment(self) -> CopilotValidationResult:
        """
        Validate that GitHub Copilot CLI is properly configured.
        
        Returns:
            Validation result with detailed status
        """
        result = CopilotValidationResult(valid=False)
        
        # Check if gh CLI is available
        try:
            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            
            if process.returncode == 0:
                result.gh_cli_available = True
                version_match = re.search(r"gh version (\S+)", stdout.decode())
                if version_match:
                    result.gh_version = version_match.group(1)
            else:
                result.error_messages.append("gh CLI not found or not working")
        except (FileNotFoundError, asyncio.TimeoutError) as e:
            result.error_messages.append(f"gh CLI not found: {e}")
            return result
        
        # Check if Copilot extension is installed
        try:
            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "extension",
                "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            
            if b"github/gh-copilot" in stdout or b"copilot" in stdout:
                result.copilot_extension_installed = True
            else:
                result.error_messages.append(
                    "Copilot extension not installed. Run: gh extension install github/gh-copilot"
                )
        except asyncio.TimeoutError:
            result.error_messages.append("Timeout checking Copilot extension")
        
        # Check authentication status
        try:
            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "auth",
                "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            
            combined_output = stdout.decode() + stderr.decode()
            if "Logged in to github.com" in combined_output:
                result.authenticated = True
            else:
                result.error_messages.append(
                    "Not authenticated to GitHub. Run: gh auth login"
                )
        except asyncio.TimeoutError:
            result.error_messages.append("Timeout checking authentication")
        
        # Assume Copilot access if extension is installed and authenticated
        if result.copilot_extension_installed and result.authenticated:
            result.copilot_access = True
        
        result.valid = (
            result.gh_cli_available
            and result.copilot_extension_installed
            and result.authenticated
            and result.copilot_access
        )
        
        return result
    
    async def get_copilot_version(self) -> Optional[str]:
        """
        Get Copilot CLI version for diagnostics.
        
        Returns:
            Version string or None if unavailable
        """
        try:
            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "copilot",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            
            if process.returncode == 0:
                return stdout.decode().strip()
        except Exception as e:
            logger.warning(f"Failed to get Copilot version: {e}")
        
        return None
    
    def _extract_json_from_output(self, output: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from mixed CLI output.
        
        Args:
            output: Raw CLI output that may contain JSON
            
        Returns:
            Parsed JSON dict or None if not found
        """
        # Try to find JSON block in output
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON
            r'\{.*\}',  # Simple JSON
        ]
        
        for pattern in json_patterns:
            matches = re.finditer(pattern, output, re.DOTALL)
            for match in matches:
                try:
                    json_data = json.loads(match.group(0))
                    # Validate patches field if present
                    if "patches" in json_data:
                        if not isinstance(json_data["patches"], list):
                            logger.warning("Invalid patches field: must be a list")
                            json_data["patches"] = []
                        else:
                            # Validate each patch has required fields
                            valid_patches = []
                            for patch in json_data["patches"]:
                                if isinstance(patch, dict) and "file" in patch and "diff" in patch:
                                    valid_patches.append(patch)
                                else:
                                    logger.warning(f"Invalid patch format: {patch}")
                            json_data["patches"] = valid_patches
                    return json_data
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _write_execution_log(
        self,
        artifact_dir: Path,
        start_timestamp: str,
        execution_time: float,
        command: list,
        exit_code: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Write execution log with timestamps and metadata.
        
        Args:
            artifact_dir: Directory to save log
            start_timestamp: ISO timestamp of execution start
            execution_time: Duration in seconds
            command: Command that was executed
            exit_code: Process exit code
            success: Whether execution succeeded
            error_message: Error message if failed
        """
        end_timestamp = datetime.now().isoformat()
        
        log_content = f"""Copilot CLI Execution Log
==========================

Start Time: {start_timestamp}
End Time: {end_timestamp}
Duration: {execution_time:.2f} seconds

Command: {' '.join(command)}
Exit Code: {exit_code}
Success: {success}
"""
        
        if error_message:
            log_content += f"\nError: {error_message}\n"
        
        log_path = artifact_dir / "execution_log.txt"
        log_path.write_text(log_content, encoding="utf-8")
    
    async def execute_spec(
        self,
        request: CopilotExecutionRequest,
        prompt_content: str,
        artifact_dir: Path,
    ) -> CopilotExecutionResult:
        """
        Execute a phase specification using GitHub Copilot CLI.
        
        Args:
            request: Execution request with spec path and context
            prompt_content: Rendered prompt content to send to Copilot
            artifact_dir: Directory to save artifacts
            
        Returns:
            Execution result with status and outputs
        """
        start_time = time.time()
        start_timestamp = datetime.now().isoformat()
        timeout = request.timeout or self.default_timeout
        
        logger.info(
            f"Executing Copilot CLI for spec: {request.spec_path} "
            f"(mode: {request.execution_mode}, timeout: {timeout}s)"
        )
        
        # Save prompt content to artifact directory
        prompt_file = artifact_dir / "copilot_prompt.md"
        prompt_file.write_text(prompt_content, encoding="utf-8")
        
        # Construct command - use gh copilot with JSON format
        # Request JSON output and apply code changes
        command = [
            self.cli_path,
            "copilot",
            "suggest",
            "--target",
            "shell",
            "--format",
            "json",
        ]
        
        raw_output = ""
        raw_error = ""
        
        try:
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=request.repo_path,
            )
            
            # Send prompt as stdin
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=prompt_content.encode("utf-8")),
                    timeout=timeout,
                )
                raw_output = stdout.decode("utf-8", errors="replace")
                raw_error = stderr.decode("utf-8", errors="replace")
                
            except asyncio.TimeoutError:
                # Kill the process on timeout
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                
                execution_time = time.time() - start_time
                error_msg = f"Copilot execution timed out after {timeout}s"
                logger.error(error_msg)
                
                # Save error artifacts
                (artifact_dir / "error.log").write_text(
                    f"{error_msg}\n\nPartial output:\n{raw_output}\n\nPartial error:\n{raw_error}",
                    encoding="utf-8",
                )
                
                # Write execution log
                self._write_execution_log(
                    artifact_dir, start_timestamp, execution_time,
                    command, -1, False, error_msg
                )
                
                return CopilotExecutionResult(
                    success=False,
                    execution_time=execution_time,
                    error_message=error_msg,
                    error_type=CopilotErrorType.TIMEOUT,
                    raw_output=raw_output,
                )
            
            execution_time = time.time() - start_time
            
            # Save raw output if enabled
            if self.capture_raw_output:
                (artifact_dir / "copilot_raw.txt").write_text(
                    f"STDOUT:\n{raw_output}\n\nSTDERR:\n{raw_error}",
                    encoding="utf-8",
                )
            
            # Check exit code
            if process.returncode != 0:
                error_msg = f"Copilot CLI failed with exit code {process.returncode}"
                logger.error(f"{error_msg}\nstderr: {raw_error}")
                
                # Save error artifacts
                (artifact_dir / "error.log").write_text(
                    f"{error_msg}\n\nOutput:\n{raw_output}\n\nError:\n{raw_error}",
                    encoding="utf-8",
                )
                
                # Check for specific error types
                error_type = CopilotErrorType.EXECUTION_ERROR
                if "not found" in raw_error.lower() or "command not found" in raw_error.lower():
                    error_type = CopilotErrorType.NOT_FOUND
                elif "auth" in raw_error.lower() or "authentication" in raw_error.lower():
                    error_type = CopilotErrorType.AUTH_ERROR
                
                # Write execution log
                self._write_execution_log(
                    artifact_dir, start_timestamp, execution_time,
                    command, process.returncode, False, error_msg
                )
                
                return CopilotExecutionResult(
                    success=False,
                    execution_time=execution_time,
                    error_message=error_msg,
                    error_type=error_type,
                    raw_output=raw_output,
                )
            
            # Try to parse JSON output
            json_output = None
            try:
                json_output = json.loads(raw_output)
            except json.JSONDecodeError:
                # Try to extract JSON from mixed output
                json_output = self._extract_json_from_output(raw_output)
            
            if json_output:
                # Save parsed JSON
                output_path = artifact_dir / "copilot_output.json"
                output_path.write_text(
                    json.dumps(json_output, indent=2),
                    encoding="utf-8",
                )
                
                # Extract patches
                patches = json_output.get("patches", [])
                
                # Save patches to individual files
                if patches:
                    patches_dir = artifact_dir / "patches"
                    patches_dir.mkdir(exist_ok=True)
                    
                    for idx, patch in enumerate(patches):
                        if isinstance(patch, dict) and "file" in patch and "diff" in patch:
                            # Sanitize filename for patch file
                            patch_filename = Path(patch["file"]).name + f"_{idx}.patch"
                            patch_file = patches_dir / patch_filename
                            patch_file.write_text(patch["diff"], encoding="utf-8")
                            logger.info(f"Saved patch for {patch['file']} to {patch_file}")
                
                # Extract fields
                result = CopilotExecutionResult(
                    success=True,
                    output_path=str(output_path),
                    execution_time=execution_time,
                    summary=json_output.get("changes_summary"),
                    files_modified=json_output.get("files_modified", []),
                    files_created=json_output.get("files_created", []),
                    changes_summary=json_output.get("changes_summary"),
                    tests_added=json_output.get("tests_added", []),
                    potential_issues=json_output.get("potential_issues", []),
                    completion_status=json_output.get("completion_status"),
                    patches=patches,
                    raw_output=raw_output,
                )
                
                # Check if patches are provided
                if not result.patches:
                    error_msg = "No actionable changes generated - patches field is empty"
                    logger.error(error_msg)
                    
                    (artifact_dir / "error.log").write_text(
                        f"{error_msg}\n\nOutput:\n{raw_output}",
                        encoding="utf-8",
                    )
                    
                    return CopilotExecutionResult(
                        success=False,
                        execution_time=execution_time,
                        error_message=error_msg,
                        error_type=CopilotErrorType.EXECUTION_ERROR,
                        raw_output=raw_output,
                        completion_status="blocked",
                    )
            else:
                # No JSON found - fail the execution
                error_msg = "Copilot did not return JSON output as required"
                logger.error(f"{error_msg}. Raw output: {raw_output[:500]}")
                
                (artifact_dir / "error.log").write_text(
                    f"{error_msg}\n\nRaw output:\n{raw_output}",
                    encoding="utf-8",
                )
                
                self._write_execution_log(
                    artifact_dir, start_timestamp, execution_time,
                    command, process.returncode, False, error_msg
                )
                
                return CopilotExecutionResult(
                    success=False,
                    execution_time=execution_time,
                    error_message=error_msg,
                    error_type=CopilotErrorType.PARSE_ERROR,
                    raw_output=raw_output,
                )
            
            # Write execution log for successful execution
            self._write_execution_log(
                artifact_dir, start_timestamp, execution_time,
                command, process.returncode, True
            )
            
            logger.info(
                f"Copilot execution completed successfully in {execution_time:.2f}s"
            )
            return result
            
        except FileNotFoundError:
            execution_time = time.time() - start_time
            error_msg = (
                f"GitHub CLI not found at '{self.cli_path}'. "
                "Please install it from https://cli.github.com/"
            )
            logger.error(error_msg)
            
            # Write execution log
            self._write_execution_log(
                artifact_dir, start_timestamp, execution_time,
                command, -1, False, error_msg
            )
            
            return CopilotExecutionResult(
                success=False,
                execution_time=execution_time,
                error_message=error_msg,
                error_type=CopilotErrorType.NOT_FOUND,
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Unexpected error executing Copilot CLI: {e}"
            logger.exception(error_msg)
            
            # Save error artifacts
            (artifact_dir / "error.log").write_text(
                f"{error_msg}\n\nOutput:\n{raw_output}\n\nError:\n{raw_error}",
                encoding="utf-8",
            )
            
            # Write execution log
            self._write_execution_log(
                artifact_dir, start_timestamp, execution_time,
                command, -1, False, error_msg
            )
            
            return CopilotExecutionResult(
                success=False,
                execution_time=execution_time,
                error_message=error_msg,
                error_type=CopilotErrorType.EXECUTION_ERROR,
                raw_output=raw_output,
            )
    
    async def validate_copilot_available(self) -> bool:
        """
        Quick check if Copilot CLI is available.
        
        Returns:
            True if Copilot CLI is available
        """
        validation = await self.validate_environment()
        return validation.valid
