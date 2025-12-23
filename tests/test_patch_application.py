"""
Integration tests for patch application functionality.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from git import Repo

from orchestrator.executor import PhaseExecutor
from orchestrator.state import StateManager, PhaseState
from agents.copilot_models import CopilotExecutionResult


@pytest.fixture
def temp_repo(tmp_path):
    """Create temporary git repository."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    # Initialize git repo
    repo = Repo.init(repo_path)
    
    # Create initial file
    test_file = repo_path / "test.py"
    test_file.write_text("def foo():\n    pass\n")
    
    repo.index.add(["test.py"])
    repo.index.commit("Initial commit")
    
    return repo_path, repo


@pytest.fixture
def sample_phase_state():
    """Create sample phase state."""
    return PhaseState(
        id="phase-1",
        run_id="run-1",
        phase_number=1,
        title="Test Phase",
        status="in_progress",
        plan_json='{"title": "Test Phase", "source_branch": "main"}',
        created_at="2024-01-01T00:00:00",
        branch_name=None,
    )


class TestPatchApplication:
    """Tests for patch application functionality."""
    
    @pytest.mark.asyncio
    async def test_apply_copilot_patches_success(self, temp_repo, sample_phase_state, tmp_path):
        """Test successful application of patches."""
        repo_path, repo = temp_repo
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        
        # Create patches directory
        patches_dir = artifact_dir / "patches"
        patches_dir.mkdir()
        
        # Create a valid patch file
        patch_content = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
 def foo():
-    pass
+    return True
"""
        patch_file = patches_dir / "test.py_0.patch"
        patch_file.write_text(patch_content)
        
        # Create execution result
        result = CopilotExecutionResult(
            success=True,
            execution_time=1.0,
            patches=[
                {
                    "file": "test.py",
                    "diff": patch_content
                }
            ]
        )
        
        # Mock executor setup
        with patch("orchestrator.executor.OrchestratorConfig") as mock_config, \
             patch("orchestrator.executor.StateManager") as mock_state:
            
            mock_config.return_value.paths.artifact_base_path = str(tmp_path)
            mock_state_instance = AsyncMock()
            mock_state.return_value = mock_state_instance
            
            # Create minimal executor mock
            executor = Mock()
            executor.git_repo = repo
            executor.state_manager = mock_state_instance
            
            # Import the method
            from orchestrator.executor import PhaseExecutor
            apply_method = PhaseExecutor._apply_copilot_patches
            
            # Call the method
            success = await apply_method(
                executor,
                sample_phase_state,
                result,
                artifact_dir,
                pass_number=1
            )
            
            assert success is True
            
            # Verify patch was applied
            test_file = repo_path / "test.py"
            content = test_file.read_text()
            assert "return True" in content
    
    @pytest.mark.asyncio
    async def test_apply_copilot_patches_missing_patch_file(self, temp_repo, sample_phase_state, tmp_path):
        """Test patch application when patch file is missing."""
        repo_path, repo = temp_repo
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        
        # Create patches directory but no patch files
        patches_dir = artifact_dir / "patches"
        patches_dir.mkdir()
        
        # Create execution result
        result = CopilotExecutionResult(
            success=True,
            execution_time=1.0,
            patches=[
                {
                    "file": "test.py",
                    "diff": "some diff"
                }
            ]
        )
        
        # Mock executor
        executor = Mock()
        executor.git_repo = repo
        executor.state_manager = AsyncMock()
        
        from orchestrator.executor import PhaseExecutor
        apply_method = PhaseExecutor._apply_copilot_patches
        
        success = await apply_method(
            executor,
            sample_phase_state,
            result,
            artifact_dir,
            pass_number=1
        )
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_apply_copilot_patches_invalid_diff(self, temp_repo, sample_phase_state, tmp_path):
        """Test patch application with invalid diff."""
        repo_path, repo = temp_repo
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        
        patches_dir = artifact_dir / "patches"
        patches_dir.mkdir()
        
        # Create invalid patch
        patch_content = "This is not a valid unified diff"
        patch_file = patches_dir / "test.py_0.patch"
        patch_file.write_text(patch_content)
        
        result = CopilotExecutionResult(
            success=True,
            execution_time=1.0,
            patches=[
                {
                    "file": "test.py",
                    "diff": patch_content
                }
            ]
        )
        
        executor = Mock()
        executor.git_repo = repo
        executor.state_manager = AsyncMock()
        
        from orchestrator.executor import PhaseExecutor
        apply_method = PhaseExecutor._apply_copilot_patches
        
        success = await apply_method(
            executor,
            sample_phase_state,
            result,
            artifact_dir,
            pass_number=1
        )
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_apply_copilot_patches_multiple_files(self, temp_repo, sample_phase_state, tmp_path):
        """Test application of patches to multiple files."""
        repo_path, repo = temp_repo
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        
        # Create second file
        file2 = repo_path / "test2.py"
        file2.write_text("def bar():\n    pass\n")
        repo.index.add(["test2.py"])
        repo.index.commit("Add test2.py")
        
        patches_dir = artifact_dir / "patches"
        patches_dir.mkdir()
        
        # Create patches for both files
        patch1 = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
 def foo():
-    pass
+    return True
"""
        patch2 = """--- a/test2.py
+++ b/test2.py
@@ -1,2 +1,2 @@
 def bar():
-    pass
+    return False
"""
        
        (patches_dir / "test.py_0.patch").write_text(patch1)
        (patches_dir / "test2.py_1.patch").write_text(patch2)
        
        result = CopilotExecutionResult(
            success=True,
            execution_time=1.0,
            patches=[
                {"file": "test.py", "diff": patch1},
                {"file": "test2.py", "diff": patch2}
            ]
        )
        
        executor = Mock()
        executor.git_repo = repo
        executor.state_manager = AsyncMock()
        
        from orchestrator.executor import PhaseExecutor
        apply_method = PhaseExecutor._apply_copilot_patches
        
        success = await apply_method(
            executor,
            sample_phase_state,
            result,
            artifact_dir,
            pass_number=1
        )
        
        assert success is True
        
        # Verify both patches were applied
        content1 = (repo_path / "test.py").read_text()
        content2 = (repo_path / "test2.py").read_text()
        assert "return True" in content1
        assert "return False" in content2


class TestPatchValidation:
    """Tests for patch validation functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_patches_after_application(self, temp_repo, sample_phase_state, tmp_path):
        """Test validation of changes after patch application."""
        repo_path, repo = temp_repo
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        
        patches_dir = artifact_dir / "patches"
        patches_dir.mkdir()
        
        patch_content = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
 def foo():
-    pass
+    return True
"""
        patch_file = patches_dir / "test.py_0.patch"
        patch_file.write_text(patch_content)
        
        result = CopilotExecutionResult(
            success=True,
            execution_time=1.0,
            patches=[{"file": "test.py", "diff": patch_content}],
            files_modified=["test.py"]
        )
        
        executor = Mock()
        executor.git_repo = repo
        executor.state_manager = AsyncMock()
        
        from orchestrator.executor import PhaseExecutor
        apply_method = PhaseExecutor._apply_copilot_patches
        
        success = await apply_method(
            executor,
            sample_phase_state,
            result,
            artifact_dir,
            pass_number=1
        )
        
        assert success is True
        
        # Verify git detects changes
        assert repo.is_dirty()
        
        # Check diff output
        diff = repo.git.diff()
        assert "return True" in diff


class TestCommitWorkflow:
    """Tests for commit workflow with patches."""
    
    @pytest.mark.asyncio
    async def test_commit_after_patch_application(self, temp_repo, sample_phase_state, tmp_path):
        """Test commit workflow after applying patches."""
        repo_path, repo = temp_repo
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        
        patches_dir = artifact_dir / "patches"
        patches_dir.mkdir()
        
        patch_content = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
 def foo():
-    pass
+    return True
"""
        patch_file = patches_dir / "test.py_0.patch"
        patch_file.write_text(patch_content)
        
        result = CopilotExecutionResult(
            success=True,
            execution_time=1.0,
            patches=[{"file": "test.py", "diff": patch_content}],
            changes_summary="Updated foo function"
        )
        
        # Apply patch
        repo.git.apply(str(patch_file))
        repo.git.add(A=True)
        
        # Mock commit
        executor = Mock()
        executor.git_repo = repo
        executor.config = Mock()
        executor.config.copilot = {}
        
        from orchestrator.executor import PhaseExecutor
        commit_method = PhaseExecutor._commit_copilot_changes
        
        await commit_method(
            executor,
            sample_phase_state,
            result,
            pass_number=1
        )
        
        # Verify commit was created
        latest_commit = repo.head.commit
        assert "Test Phase" in latest_commit.message
        assert "Updated foo function" in latest_commit.message
