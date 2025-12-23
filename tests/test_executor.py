"""
Unit tests for the PhaseExecutor module.
"""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from orchestrator.config import OrchestratorConfig, ConfigError
from orchestrator.executor import PhaseExecutor, validate_executor_config
from orchestrator.state import PhaseState, RunState


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=OrchestratorConfig)
    config.execution.max_retries = 3
    config.execution.copilot_mode = "direct"
    config.execution.branch_prefix = "yolo/"
    config.paths.artifact_base_path = tempfile.mkdtemp()
    config.llm.host = "http://localhost:11434"
    config.llm.model = "llama2"
    config.llm.temperature = 0.7
    config.llm.max_tokens = 4000
    config.llm.embedding_model = "nomic-embed-text"
    return config


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    client.generate = AsyncMock(return_value="Enhanced specification content")
    return client


@pytest.fixture
def mock_rag_system():
    """Create a mock RAG system."""
    rag = MagicMock()
    rag.retrieve_context = MagicMock(return_value=MagicMock(chunks=[]))
    rag.get_hot_files = MagicMock(return_value=[])
    return rag


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    state = MagicMock()
    state.get_phases_for_run = AsyncMock(return_value=[])
    state.get_phase = AsyncMock(return_value=None)
    state.get_run = AsyncMock(return_value=None)
    state.update_run_status = AsyncMock()
    state.update_phase_status = AsyncMock()
    state.register_artifact = AsyncMock()
    state.create_intervention = AsyncMock(return_value=MagicMock(intervention_id="intervention_123"))
    state.get_pending_interventions = AsyncMock(return_value=[])
    state.resolve_intervention = AsyncMock()
    state.increment_phase_retry = AsyncMock(return_value=1)
    state.get_artifacts_for_phase = AsyncMock(return_value=[])
    state.get_executions_for_phase = AsyncMock(return_value=[])
    state.get_findings_for_phase = AsyncMock(return_value=[])
    state.db = MagicMock()
    state.db.execute = AsyncMock()
    state.db.commit = AsyncMock()
    return state


@pytest.fixture
def executor(mock_config, mock_llm_client, mock_rag_system, mock_state_manager):
    """Create a PhaseExecutor instance."""
    with patch("orchestrator.executor.Repo"):
        return PhaseExecutor(
            config=mock_config,
            llm_client=mock_llm_client,
            rag_system=mock_rag_system,
            state_manager=mock_state_manager,
            repo_path="/tmp/test_repo",
        )


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_valid_config(self, mock_config):
        """Test that valid config passes validation."""
        validate_executor_config(mock_config)

    def test_invalid_max_retries(self, mock_config):
        """Test that max_retries < 1 raises error."""
        mock_config.execution.max_retries = 0
        with pytest.raises(ConfigError, match="max_retries must be >= 1"):
            validate_executor_config(mock_config)

    def test_invalid_copilot_mode(self, mock_config):
        """Test that invalid copilot_mode raises error."""
        mock_config.execution.copilot_mode = "invalid"
        with pytest.raises(ConfigError, match="copilot_mode must be"):
            validate_executor_config(mock_config)

    def test_invalid_branch_prefix(self, mock_config):
        """Test that invalid branch_prefix raises error."""
        mock_config.execution.branch_prefix = "invalid prefix!"
        with pytest.raises(ConfigError, match="branch_prefix must contain only"):
            validate_executor_config(mock_config)


class TestPhaseSpecGeneration:
    """Tests for phase specification generation."""

    @pytest.mark.asyncio
    async def test_generate_phase_spec_basic(
        self, executor, mock_state_manager, mock_rag_system
    ):
        """Test basic phase spec generation."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"
        phase.plan_json = json.dumps({
            "title": "Test Phase",
            "intent": "Test intent",
            "files": ["file1.py", "file2.py"],
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
            "risks": [],
            "size": "MEDIUM",
            "goals": "Test goals",
        })

        mock_state_manager.get_phase.return_value = phase

        spec_path = await executor.generate_phase_spec("phase_123", 1)

        assert os.path.exists(spec_path)
        assert "spec.md" in spec_path
        assert "phase_123" in spec_path
        assert "pass_1" in spec_path

        with open(spec_path, "r") as f:
            content = f.read()
            assert "Test Phase" in content
            assert "Test intent" in content
            assert "file1.py" in content

    @pytest.mark.asyncio
    async def test_generate_phase_spec_with_context(
        self, executor, mock_state_manager, mock_rag_system
    ):
        """Test spec generation with RAG context."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"
        phase.plan_json = json.dumps({
            "title": "Test Phase",
            "intent": "Test intent",
            "files": ["file1.py"],
            "acceptance_criteria": ["Criterion 1"],
            "risks": [],
            "size": "SMALL",
            "goals": "Test goals",
        })

        mock_state_manager.get_phase.return_value = phase

        mock_chunk = MagicMock()
        mock_chunk.file_path = "example.py"
        mock_chunk.content = "def example(): pass"
        mock_chunk.line_start = 1
        mock_chunk.line_end = 10
        mock_chunk.language = "python"
        mock_chunk.symbols = ["example"]

        mock_rag_system.retrieve_context.return_value = MagicMock(chunks=[mock_chunk])
        mock_rag_system.get_hot_files.return_value = [
            {"file_path": "hot.py", "count": 5}
        ]

        spec_path = await executor.generate_phase_spec("phase_123", 1)

        with open(spec_path, "r") as f:
            content = f.read()
            assert "example.py" in content
            assert "def example(): pass" in content
            assert "hot.py" in content


class TestPhaseExecution:
    """Tests for phase execution."""

    @pytest.mark.asyncio
    async def test_execute_single_phase_success(
        self, executor, mock_state_manager
    ):
        """Test successful single phase execution."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"
        phase.metadata = None
        phase.plan_json = json.dumps({
            "title": "Test Phase",
            "intent": "Test intent",
            "files": [],
            "acceptance_criteria": ["Criterion 1"],
            "risks": [],
            "size": "SMALL",
            "goals": "Test goals",
        })

        mock_state_manager.get_phase.return_value = phase

        with patch.object(executor, "generate_phase_spec", new=AsyncMock(return_value="/tmp/spec.md")):
            result = await executor.execute_single_phase("phase_123")

        assert result is True
        mock_state_manager.update_phase_status.assert_called()

    @pytest.mark.asyncio
    async def test_execute_phases_all_success(
        self, executor, mock_state_manager
    ):
        """Test execution of all phases successfully."""
        phase1 = MagicMock(spec=PhaseState)
        phase1.id = "phase_1"
        phase1.phase_number = 1
        phase1.title = "Phase 1"
        phase1.status = "pending"

        phase2 = MagicMock(spec=PhaseState)
        phase2.id = "phase_2"
        phase2.phase_number = 2
        phase2.title = "Phase 2"
        phase2.status = "pending"

        mock_state_manager.get_phases_for_run.return_value = [phase1, phase2]

        with patch.object(executor, "execute_single_phase", new=AsyncMock(return_value=True)):
            await executor.execute_phases("run_123")

        mock_state_manager.update_run_status.assert_any_call("run_123", "executing")
        mock_state_manager.update_run_status.assert_any_call("run_123", "completed")


class TestRetryLogic:
    """Tests for retry loop logic."""

    @pytest.mark.asyncio
    async def test_retry_on_error(self, executor, mock_state_manager):
        """Test retry logic when errors occur."""
        executor.config.execution.max_retries = 2

        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"
        phase.metadata = None
        phase.plan_json = json.dumps({
            "title": "Test Phase",
            "intent": "Test intent",
            "files": [],
            "acceptance_criteria": ["Criterion 1"],
            "risks": [],
            "size": "SMALL",
            "goals": "Test goals",
        })

        mock_state_manager.get_phase.return_value = phase

        call_count = 0

        async def failing_spec_gen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Test error")
            return "/tmp/spec.md"

        with patch.object(executor, "generate_phase_spec", new=failing_spec_gen):
            result = await executor.execute_single_phase("phase_123")

        assert call_count == 2
        assert result is True

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, executor, mock_state_manager):
        """Test manual intervention when max retries exceeded."""
        executor.config.execution.max_retries = 2

        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"
        phase.metadata = None
        phase.plan_json = json.dumps({
            "title": "Test Phase",
            "intent": "Test intent",
            "files": [],
            "acceptance_criteria": ["Criterion 1"],
            "risks": [],
            "size": "SMALL",
            "goals": "Test goals",
        })

        mock_state_manager.get_phase.return_value = phase

        async def always_fail(*args, **kwargs):
            raise Exception("Test error")

        with patch.object(executor, "generate_phase_spec", new=always_fail):
            result = await executor.execute_single_phase("phase_123")

        assert result is False
        mock_state_manager.create_intervention.assert_called()


class TestBranchManagement:
    """Tests for branch management."""

    @pytest.mark.asyncio
    async def test_create_branch_in_branch_mode(self, executor, mock_state_manager):
        """Test branch creation in branch mode."""
        executor.config.execution.copilot_mode = "branch"

        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.phase_number = 1
        phase.title = "Test Phase"

        mock_repo = MagicMock()
        mock_branch = MagicMock()
        mock_repo.create_head.return_value = mock_branch
        mock_repo.active_branch.name = "main"
        executor.git_repo = mock_repo

        branch_name = await executor.create_phase_branch(phase)

        assert branch_name
        assert "phase-1" in branch_name
        assert "test-phase" in branch_name
        mock_repo.create_head.assert_called_once()
        mock_branch.checkout.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_branch_in_direct_mode(self, executor, mock_state_manager):
        """Test no branch creation in direct mode."""
        executor.config.execution.copilot_mode = "direct"

        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.phase_number = 1
        phase.title = "Test Phase"

        branch_name = await executor.create_phase_branch(phase)

        assert branch_name == ""


class TestManualIntervention:
    """Tests for manual intervention."""

    @pytest.mark.asyncio
    async def test_handle_manual_intervention(self, executor, mock_state_manager):
        """Test manual intervention creation."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"

        mock_state_manager.get_phase.return_value = phase

        intervention_id = await executor.handle_manual_intervention("phase_123")

        assert intervention_id == "intervention_123"
        mock_state_manager.create_intervention.assert_called_once()
        mock_state_manager.update_phase_status.assert_called_with("phase_123", "paused")
        mock_state_manager.update_run_status.assert_called_with("run_456", "paused")

    @pytest.mark.asyncio
    async def test_resume_phase_continue(self, executor, mock_state_manager):
        """Test resuming a phase."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"

        intervention = MagicMock()
        intervention.id = "intervention_123"
        intervention.status = "pending"

        mock_state_manager.get_phase.return_value = phase
        mock_state_manager.get_interventions_for_phase.return_value = [intervention]

        await executor.resume_phase("phase_123", "resume")

        mock_state_manager.update_phase_status.assert_called_with(
            "phase_123", "in_progress"
        )
        mock_state_manager.update_run_status.assert_called_with("run_456", "executing")
        mock_state_manager.resolve_intervention.assert_called()

    @pytest.mark.asyncio
    async def test_resume_phase_skip(self, executor, mock_state_manager):
        """Test skipping a phase."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"

        intervention = MagicMock()
        intervention.id = "intervention_123"
        intervention.status = "pending"

        mock_state_manager.get_phase.return_value = phase
        mock_state_manager.get_interventions_for_phase.return_value = [intervention]

        await executor.resume_phase("phase_123", "skip")

        mock_state_manager.update_phase_status.assert_called_with("phase_123", "skipped")


class TestErrorHandling:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_handle_execution_error(self, executor, mock_state_manager):
        """Test error handling."""
        phase = MagicMock(spec=PhaseState)
        phase.id = "phase_123"
        phase.run_id = "run_456"
        phase.phase_number = 1
        phase.title = "Test Phase"

        mock_state_manager.get_phase.return_value = phase

        error = Exception("Test error")
        await executor.handle_execution_error("phase_123", error)

        mock_state_manager.update_phase_status.assert_called_with("phase_123", "failed")

        artifact_dir = (
            Path(executor.config.paths.artifact_base_path) / "run_456" / "phase_123"
        )
        error_log = artifact_dir / "error.log"
        assert error_log.exists()

    @pytest.mark.asyncio
    async def test_recover_execution(self, executor, mock_state_manager):
        """Test execution recovery."""
        run = MagicMock(spec=RunState)
        run.id = "run_123"
        run.status = "executing"

        phase1 = MagicMock(spec=PhaseState)
        phase1.id = "phase_1"
        phase1.phase_number = 1
        phase1.status = "completed"

        phase2 = MagicMock(spec=PhaseState)
        phase2.id = "phase_2"
        phase2.phase_number = 2
        phase2.status = "in_progress"

        mock_state_manager.get_run.return_value = run
        mock_state_manager.get_phases_for_run.return_value = [phase1, phase2]

        recovery_phase_id = await executor.recover_execution("run_123")

        assert recovery_phase_id == "phase_2"


class TestProgressTracking:
    """Tests for progress tracking."""

    @pytest.mark.asyncio
    async def test_generate_execution_summary(self, executor, mock_state_manager):
        """Test execution summary generation."""
        phase1 = MagicMock(spec=PhaseState)
        phase1.id = "phase_1"
        phase1.status = "completed"

        phase2 = MagicMock(spec=PhaseState)
        phase2.id = "phase_2"
        phase2.status = "failed"

        phase3 = MagicMock(spec=PhaseState)
        phase3.id = "phase_3"
        phase3.status = "skipped"

        mock_state_manager.get_phases_for_run.return_value = [phase1, phase2, phase3]
        mock_state_manager.get_artifacts_for_phase.return_value = []
        mock_state_manager.get_executions_for_phase.return_value = []
        mock_state_manager.get_findings_for_phase.return_value = []

        summary = await executor.generate_execution_summary("run_123")

        assert summary["run_id"] == "run_123"
        assert summary["total_phases"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
