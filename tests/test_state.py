"""Unit tests for state management."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from orchestrator.state import StateManager
from orchestrator.models import RunState, PhaseState, ExecutionState, Finding
from orchestrator.exceptions import RunNotFoundError, PhaseNotFoundError


@pytest.fixture
async def state_manager():
    """Create temporary state manager for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        artifact_path = str(Path(tmpdir) / "artifacts")
        
        async with StateManager(db_path, artifact_path) as sm:
            yield sm


@pytest.mark.asyncio
async def test_create_run(state_manager):
    """Test creating a new run."""
    config = {"max_retries": 3, "copilot_mode": "direct"}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    assert run.run_id is not None
    assert run.status == "planning"
    assert run.repo_path == "/test/repo"
    assert run.branch == "main"
    assert json.loads(run.config_snapshot) == config


@pytest.mark.asyncio
async def test_get_run(state_manager):
    """Test retrieving a run."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    retrieved = await state_manager.get_run(run.run_id)
    assert retrieved is not None
    assert retrieved.run_id == run.run_id
    assert retrieved.status == "planning"


@pytest.mark.asyncio
async def test_update_run_status(state_manager):
    """Test updating run status."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    await state_manager.update_run_status(run.run_id, "executing")
    
    updated = await state_manager.get_run(run.run_id)
    assert updated.status == "executing"


@pytest.mark.asyncio
async def test_create_phase(state_manager):
    """Test creating a phase."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {
        "files": ["file1.py", "file2.py"],
        "acceptance_criteria": ["Build passes", "Tests pass"],
        "dependencies": [],
        "risks": []
    }
    
    phase = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Setup Database",
        intent="Create database schema",
        plan=plan,
        max_retries=3,
        size="medium"
    )
    
    assert phase.phase_id is not None
    assert phase.phase_number == 1
    assert phase.status == "pending"
    assert json.loads(phase.plan_json) == plan


@pytest.mark.asyncio
async def test_get_phases_for_run(state_manager):
    """Test retrieving phases for a run."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {"files": [], "acceptance_criteria": [], "dependencies": [], "risks": []}
    
    phase1 = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Phase 1",
        intent="First phase",
        plan=plan,
        max_retries=3
    )
    
    phase2 = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=2,
        title="Phase 2",
        intent="Second phase",
        plan=plan,
        max_retries=3
    )
    
    phases = await state_manager.get_phases_for_run(run.run_id)
    assert len(phases) == 2
    assert phases[0].phase_number == 1
    assert phases[1].phase_number == 2


@pytest.mark.asyncio
async def test_phase_status_transitions(state_manager):
    """Test phase status transitions."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {"files": [], "acceptance_criteria": [], "dependencies": [], "risks": []}
    phase = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Test Phase",
        intent="Test phase transitions",
        plan=plan,
        max_retries=3
    )
    
    # Pending -> In Progress
    await state_manager.update_phase_status(
        phase.phase_id,
        "in_progress",
        started_at=datetime.now()
    )
    
    updated = await state_manager.get_phase(phase.phase_id)
    assert updated.status == "in_progress"
    assert updated.started_at is not None
    
    # In Progress -> Completed
    await state_manager.update_phase_status(
        phase.phase_id,
        "completed",
        completed_at=datetime.now()
    )
    
    updated = await state_manager.get_phase(phase.phase_id)
    assert updated.status == "completed"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_create_execution(state_manager):
    """Test creating an execution."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {"files": [], "acceptance_criteria": [], "dependencies": [], "risks": []}
    phase = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Test Phase",
        intent="Test execution",
        plan=plan,
        max_retries=3
    )
    
    execution = await state_manager.create_execution(
        phase_id=phase.phase_id,
        pass_number=1,
        copilot_input_path="/test/spec.md",
        execution_mode="direct"
    )
    
    assert execution.execution_id is not None
    assert execution.pass_number == 1
    assert execution.status == "running"


@pytest.mark.asyncio
async def test_add_findings(state_manager):
    """Test adding findings."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {"files": [], "acceptance_criteria": [], "dependencies": [], "risks": []}
    phase = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Test Phase",
        intent="Test findings",
        plan=plan,
        max_retries=3
    )
    
    execution = await state_manager.create_execution(
        phase_id=phase.phase_id,
        pass_number=1,
        copilot_input_path="/test/spec.md",
        execution_mode="direct"
    )
    
    finding = await state_manager.add_finding(
        execution_id=execution.execution_id,
        severity="major",
        category="build",
        title="Build failed",
        description="Compilation error in module X",
        evidence="Error: undefined symbol 'foo'",
        suggested_fix="Import the missing module"
    )
    
    assert finding.finding_id is not None
    assert finding.severity == "major"
    assert finding.resolved is False


@pytest.mark.asyncio
async def test_findings_summary(state_manager):
    """Test findings summary."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {"files": [], "acceptance_criteria": [], "dependencies": [], "risks": []}
    phase = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Test Phase",
        intent="Test findings summary",
        plan=plan,
        max_retries=3
    )
    
    execution = await state_manager.create_execution(
        phase_id=phase.phase_id,
        pass_number=1,
        copilot_input_path="/test/spec.md",
        execution_mode="direct"
    )
    
    # Add multiple findings
    await state_manager.add_finding(
        execution_id=execution.execution_id,
        severity="major",
        category="build",
        title="Build failed",
        description="Error",
        evidence="Evidence"
    )
    
    await state_manager.add_finding(
        execution_id=execution.execution_id,
        severity="minor",
        category="lint",
        title="Style issue",
        description="Warning",
        evidence="Evidence"
    )
    
    summary = await state_manager.get_findings_summary(execution.execution_id)
    assert summary["major"] == 1
    assert summary["minor"] == 1


@pytest.mark.asyncio
async def test_export_run_summary(state_manager):
    """Test exporting run summary."""
    config = {"max_retries": 3}
    run = await state_manager.create_run(
        repo_path="/test/repo",
        branch="main",
        doc_path="/test/doc.md",
        config=config
    )
    
    plan = {"files": [], "acceptance_criteria": [], "dependencies": [], "risks": []}
    phase = await state_manager.create_phase(
        run_id=run.run_id,
        phase_number=1,
        title="Test Phase",
        intent="Test summary",
        plan=plan,
        max_retries=3
    )
    
    summary = await state_manager.export_run_summary(run.run_id)
    assert summary.run.run_id == run.run_id
    assert len(summary.phases) == 1
    assert summary.phases[0].phase_number == 1


@pytest.mark.asyncio
async def test_run_not_found(state_manager):
    """Test error handling for non-existent run."""
    result = await state_manager.get_run("nonexistent-id")
    assert result is None
