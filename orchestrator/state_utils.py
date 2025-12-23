"""Utility functions for state management."""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from .state import StateManager

logger = logging.getLogger(__name__)


def create_artifact_directory(
    run_id: str,
    phase_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    base_path: str = "data/artifacts"
) -> str:
    """Create artifact directory structure.
    
    Args:
        run_id: Run ID
        phase_id: Optional phase ID
        execution_id: Optional execution ID
        base_path: Base artifacts directory
        
    Returns:
        Absolute path to created directory
    """
    parts = [base_path, run_id]
    if phase_id:
        parts.append(phase_id)
    if execution_id:
        parts.append(execution_id)
    
    dir_path = Path(*parts)
    dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create .gitkeep to preserve structure
    gitkeep = dir_path / ".gitkeep"
    gitkeep.touch(exist_ok=True)
    
    return str(dir_path.absolute())


async def save_artifact(
    content: str,
    artifact_type: str,
    run_id: str,
    state_manager: StateManager,
    phase_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    extension: str = 'md',
    base_path: str = "data/artifacts"
) -> str:
    """Save artifact content to file and register in database.
    
    Args:
        content: Artifact content
        artifact_type: Type of artifact
        run_id: Run ID
        state_manager: StateManager instance
        phase_id: Optional phase ID
        execution_id: Optional execution ID
        extension: File extension
        base_path: Base artifacts directory
        
    Returns:
        File path where artifact was saved
    """
    # Create directory
    dir_path = create_artifact_directory(run_id, phase_id, execution_id, base_path)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{artifact_type}_{timestamp}.{extension}"
    file_path = Path(dir_path) / filename
    
    # Write content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Make path relative to base_path for storage
    relative_path = str(file_path.relative_to(base_path))
    
    # Register in database
    await state_manager.register_artifact(
        run_id=run_id,
        artifact_type=artifact_type,
        file_path=relative_path,
        phase_id=phase_id,
        execution_id=execution_id
    )
    
    logger.info(f"Saved artifact: {relative_path}")
    return str(file_path)


async def load_artifact(artifact_id: str, state_manager: StateManager, base_path: str = "data/artifacts") -> str:
    """Load artifact content from file.
    
    Args:
        artifact_id: Artifact ID
        state_manager: StateManager instance
        base_path: Base artifacts directory
        
    Returns:
        Artifact content as string
    """
    # Get artifact from database
    artifact = await state_manager.get_artifact(artifact_id)
    
    if not artifact:
        raise ValueError(f"Artifact not found: {artifact_id}")
    
    # Load file
    file_path = Path(base_path) / artifact.file_path
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


async def export_run_markdown(
    run_id: str,
    state_manager: StateManager,
    output_path: str
):
    """Generate comprehensive markdown report of run.
    
    Args:
        run_id: Run ID
        state_manager: StateManager instance
        output_path: Output file path
    """
    summary = await state_manager.export_run_summary(run_id)
    markdown = summary.to_markdown()
    
    # Add execution details
    markdown += "\n\n## Execution Details\n\n"
    
    for phase in summary.phases:
        executions = await state_manager.get_executions_for_phase(phase.phase_id)
        
        if executions:
            markdown += f"### Phase {phase.phase_number} Executions\n\n"
            
            for execution in executions:
                markdown += f"**Pass {execution.pass_number}** ({execution.status})\n"
                markdown += f"- Started: {execution.started_at.isoformat()}\n"
                if execution.completed_at:
                    markdown += f"- Completed: {execution.completed_at.isoformat()}\n"
                if execution.copilot_summary:
                    markdown += f"- Summary: {execution.copilot_summary}\n"
                
                # Add findings
                findings = await state_manager.get_findings_for_execution(execution.execution_id)
                if findings:
                    markdown += f"- Findings: {len(findings)}\n"
                    for finding in findings[:5]:  # Limit to first 5
                        markdown += f"  - [{finding.severity}] {finding.title}\n"
                
                markdown += "\n"
    
    # Save markdown
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    logger.info(f"Exported run report to {output_path}")


async def cleanup_old_artifacts(
    state_manager: StateManager,
    retention_days: int,
    base_path: str = "data/artifacts",
    compress: bool = True
):
    """Clean up old artifacts.
    
    Args:
        state_manager: StateManager instance
        retention_days: Number of days to retain artifacts
        base_path: Base artifacts directory
        compress: Whether to compress instead of delete
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    # Get all runs
    runs = await state_manager.list_runs(limit=1000)
    
    cleaned_count = 0
    for run in runs:
        if run.created_at < cutoff_date:
            artifacts = await state_manager.get_artifacts_for_run(run.run_id)
            
            for artifact in artifacts:
                file_path = Path(base_path) / artifact.file_path
                
                if file_path.exists():
                    if compress:
                        # TODO: Implement compression
                        logger.debug(f"Would compress: {file_path}")
                    else:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.debug(f"Deleted: {file_path}")
    
    logger.info(f"Cleaned up {cleaned_count} old artifacts")
