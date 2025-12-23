"""
Integration tests for GitHub Copilot CLI interface.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from agents.copilot_interface import CopilotCLIInterface
from agents.copilot_models import (
    CopilotExecutionRequest,
    CopilotExecutionResult,
    CopilotValidationResult,
    CopilotCLIError,
    CopilotErrorType,
    ExecutionMode,
)


@pytest.fixture
def temp_artifact_dir(tmp_path):
    """Create temporary artifact directory."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    return artifact_dir


@pytest.fixture
def sample_spec_file(tmp_path):
    """Create sample spec file."""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Phase Specification\n\nImplement feature X")
    return str(spec_path)


@pytest.fixture
def sample_request(sample_spec_file, tmp_path):
    """Create sample execution request."""
    return CopilotExecutionRequest(
        spec_path=sample_spec_file,
        repo_path=str(tmp_path),
        execution_mode=ExecutionMode.DIRECT,
        timeout=60,
        pass_number=1,
    )


@pytest.fixture
def copilot_interface():
    """Create Copilot interface with validation disabled."""
    return CopilotCLIInterface(
        cli_path="gh",
        timeout=60,
        capture_raw_output=True,
        validate_on_startup=False,
    )


class TestCopilotValidation:
    """Tests for Copilot environment validation."""
    
    @pytest.mark.asyncio
    async def test_validate_environment_success(self, copilot_interface):
        """Test successful environment validation."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock gh --version
            version_process = AsyncMock()
            version_process.communicate = AsyncMock(
                return_value=(b"gh version 2.40.0", b"")
            )
            version_process.returncode = 0
            
            # Mock gh extension list
            extension_process = AsyncMock()
            extension_process.communicate = AsyncMock(
                return_value=(b"github/gh-copilot\tv1.0.0\n", b"")
            )
            extension_process.returncode = 0
            
            # Mock gh auth status
            auth_process = AsyncMock()
            auth_process.communicate = AsyncMock(
                return_value=(b"", b"Logged in to github.com as user")
            )
            auth_process.returncode = 0
            
            mock_exec.side_effect = [
                version_process,
                extension_process,
                auth_process,
            ]
            
            result = await copilot_interface.validate_environment()
            
            assert result.valid is True
            assert result.gh_cli_available is True
            assert result.copilot_extension_installed is True
            assert result.authenticated is True
            assert result.copilot_access is True
            assert result.gh_version == "2.40.0"
    
    @pytest.mark.asyncio
    async def test_validate_environment_gh_not_found(self, copilot_interface):
        """Test validation when gh CLI is not found."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            result = await copilot_interface.validate_environment()
            
            assert result.valid is False
            assert result.gh_cli_available is False
            assert len(result.error_messages) > 0
    
    @pytest.mark.asyncio
    async def test_validate_environment_copilot_not_installed(self, copilot_interface):
        """Test validation when Copilot extension is not installed."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock gh --version (success)
            version_process = AsyncMock()
            version_process.communicate = AsyncMock(
                return_value=(b"gh version 2.40.0", b"")
            )
            version_process.returncode = 0
            
            # Mock gh extension list (no copilot)
            extension_process = AsyncMock()
            extension_process.communicate = AsyncMock(
                return_value=(b"other/extension\tv1.0.0\n", b"")
            )
            extension_process.returncode = 0
            
            mock_exec.side_effect = [version_process, extension_process]
            
            result = await copilot_interface.validate_environment()
            
            assert result.valid is False
            assert result.gh_cli_available is True
            assert result.copilot_extension_installed is False
            assert any("extension" in msg.lower() for msg in result.error_messages)


class TestCopilotExecution:
    """Tests for Copilot CLI execution."""
    
    @pytest.mark.asyncio
    async def test_execute_spec_success_with_patches(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test successful Copilot execution with patches."""
        sample_output = {
            "patches": [
                {
                    "file": "file1.py",
                    "diff": "--- a/file1.py\n+++ b/file1.py\n@@ -1,3 +1,3 @@\n def foo():\n-    pass\n+    return True\n"
                },
                {
                    "file": "file2.py",
                    "diff": "--- /dev/null\n+++ b/file2.py\n@@ -0,0 +1,2 @@\n+def bar():\n+    return False\n"
                }
            ],
            "files_modified": ["file1.py"],
            "files_created": ["file2.py"],
            "changes_summary": "Implemented feature X with patches",
            "tests_added": ["test_feature_x"],
            "potential_issues": [],
            "completion_status": "complete",
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(json.dumps(sample_output).encode(), b"")
            )
            process.returncode = 0
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            assert result.success is True
            assert len(result.patches) == 2
            assert result.patches[0]["file"] == "file1.py"
            assert result.patches[1]["file"] == "file2.py"
            assert result.files_modified == ["file1.py"]
            assert result.files_created == ["file2.py"]
            assert result.changes_summary == "Implemented feature X with patches"
            assert result.completion_status == "complete"
            
            # Check patch files were saved
            patches_dir = temp_artifact_dir / "patches"
            assert patches_dir.exists()
            assert (patches_dir / "file1.py_0.patch").exists()
            assert (patches_dir / "file2.py_1.patch").exists()
    
    @pytest.mark.asyncio
    async def test_execute_spec_no_patches(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test execution fails when no patches provided."""
        sample_output = {
            "patches": [],
            "files_modified": [],
            "files_created": [],
            "changes_summary": "No changes made",
            "completion_status": "blocked",
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(json.dumps(sample_output).encode(), b"")
            )
            process.returncode = 0
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            assert result.success is False
            assert result.error_type == CopilotErrorType.EXECUTION_ERROR
            assert "no actionable changes" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_execute_spec_invalid_patches(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test execution with invalid patch format."""
        sample_output = {
            "patches": [
                {"file": "file1.py"},  # Missing diff
                {"diff": "some diff"},  # Missing file
                "invalid",  # Not a dict
            ],
            "files_modified": ["file1.py"],
            "changes_summary": "Invalid patches",
            "completion_status": "partial",
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(json.dumps(sample_output).encode(), b"")
            )
            process.returncode = 0
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            # Should filter out invalid patches
            assert result.success is False  # No valid patches
            assert len(result.patches) == 0
    
    @pytest.mark.asyncio
    async def test_execute_spec_success(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test successful Copilot execution with JSON output."""
        sample_output = {
            "patches": [
                {
                    "file": "file1.py",
                    "diff": "--- a/file1.py\n+++ b/file1.py\n@@ -1,1 +1,1 @@\n-old\n+new\n"
                }
            ],
            "files_modified": ["file1.py", "file2.py"],
            "files_created": ["file3.py"],
            "changes_summary": "Implemented feature X",
            "tests_added": ["test_feature_x"],
            "potential_issues": [],
            "completion_status": "complete",
        }
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(json.dumps(sample_output).encode(), b"")
            )
            process.returncode = 0
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            assert result.success is True
            assert result.files_modified == ["file1.py", "file2.py"]
            assert result.files_created == ["file3.py"]
            assert result.changes_summary == "Implemented feature X"
            assert result.completion_status == "complete"
            assert result.execution_time > 0
            
            # Check artifacts were saved
            assert (temp_artifact_dir / "copilot_prompt.md").exists()
            assert (temp_artifact_dir / "copilot_output.json").exists()
            assert (temp_artifact_dir / "copilot_raw.txt").exists()
    
    @pytest.mark.asyncio
    async def test_execute_spec_timeout(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test Copilot execution timeout."""
        sample_request.timeout = 1  # Very short timeout
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            # Simulate long-running process
            async def slow_communicate(input=None):
                await asyncio.sleep(5)
                return (b"output", b"")
            
            process.communicate = slow_communicate
            process.kill = Mock()
            process.wait = AsyncMock()
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            assert result.success is False
            assert result.error_type == CopilotErrorType.TIMEOUT
            assert "timeout" in result.error_message.lower()
            
            # Check error log was saved
            assert (temp_artifact_dir / "error.log").exists()
    
    @pytest.mark.asyncio
    async def test_execute_spec_malformed_json(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test handling of malformed JSON output."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(b"This is not JSON output", b"")
            )
            process.returncode = 0
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            # Should still succeed but without structured output
            assert result.success is True
            assert result.summary is not None
            assert result.raw_output == "This is not JSON output"
    
    @pytest.mark.asyncio
    async def test_execute_spec_cli_error(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test handling of CLI execution errors."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(b"", b"Error: Authentication failed")
            )
            process.returncode = 1
            mock_exec.return_value = process
            
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            assert result.success is False
            assert result.error_type == CopilotErrorType.AUTH_ERROR
            assert "authentication" in result.error_message.lower()
            
            # Check error log was saved
            assert (temp_artifact_dir / "error.log").exists()
    
    @pytest.mark.asyncio
    async def test_execute_spec_gh_not_found(
        self, copilot_interface, sample_request, temp_artifact_dir
    ):
        """Test handling when gh CLI is not found."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            result = await copilot_interface.execute_spec(
                request=sample_request,
                prompt_content="Test prompt",
                artifact_dir=temp_artifact_dir,
            )
            
            assert result.success is False
            assert result.error_type == CopilotErrorType.NOT_FOUND
            assert "gh" in result.error_message.lower() or "cli" in result.error_message.lower()


class TestJSONExtraction:
    """Tests for JSON extraction from mixed output."""
    
    def test_extract_json_from_mixed_output(self, copilot_interface):
        """Test extracting JSON from output with text before/after."""
        mixed_output = """
        Some text before
        
        {
            "files_modified": ["test.py"],
            "changes_summary": "Test changes"
        }
        
        Some text after
        """
        
        result = copilot_interface._extract_json_from_output(mixed_output)
        
        assert result is not None
        assert result["files_modified"] == ["test.py"]
        assert result["changes_summary"] == "Test changes"
    
    def test_extract_json_with_patches(self, copilot_interface):
        """Test extracting JSON with patches field."""
        json_output = """
        {
            "patches": [
                {
                    "file": "test.py",
                    "diff": "--- a/test.py\\n+++ b/test.py\\n@@ -1,1 +1,1 @@\\n-old\\n+new"
                }
            ],
            "files_modified": ["test.py"],
            "changes_summary": "Test changes"
        }
        """
        
        result = copilot_interface._extract_json_from_output(json_output)
        
        assert result is not None
        assert "patches" in result
        assert len(result["patches"]) == 1
        assert result["patches"][0]["file"] == "test.py"
        assert "diff" in result["patches"][0]
    
    def test_extract_json_invalid_patches_format(self, copilot_interface):
        """Test extraction filters invalid patches."""
        json_output = """
        {
            "patches": "not a list",
            "files_modified": ["test.py"]
        }
        """
        
        result = copilot_interface._extract_json_from_output(json_output)
        
        assert result is not None
        assert result["patches"] == []  # Should be converted to empty list
    
    def test_extract_nested_json(self, copilot_interface):
        """Test extracting nested JSON structures."""
        nested_output = """
        {
            "files_modified": ["test.py"],
            "metadata": {
                "author": "test",
                "timestamp": "2024-01-01"
            }
        }
        """
        
        result = copilot_interface._extract_json_from_output(nested_output)
        
        assert result is not None
        assert "metadata" in result
        assert result["metadata"]["author"] == "test"
    
    def test_extract_json_no_match(self, copilot_interface):
        """Test when no JSON is present in output."""
        plain_output = "This is just plain text with no JSON"
        
        result = copilot_interface._extract_json_from_output(plain_output)
        
        assert result is None


class TestCopilotVersion:
    """Tests for Copilot version retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_copilot_version_success(self, copilot_interface):
        """Test successful version retrieval."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            process = AsyncMock()
            process.communicate = AsyncMock(
                return_value=(b"gh-copilot version 1.0.0", b"")
            )
            process.returncode = 0
            mock_exec.return_value = process
            
            version = await copilot_interface.get_copilot_version()
            
            assert version == "gh-copilot version 1.0.0"
    
    @pytest.mark.asyncio
    async def test_get_copilot_version_failure(self, copilot_interface):
        """Test version retrieval failure."""
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Error")):
            version = await copilot_interface.get_copilot_version()
            
            assert version is None
