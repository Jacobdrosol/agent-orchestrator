"""State management for Agent Orchestrator using SQLite."""

import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import aiosqlite

from .schema import initialize_database
from .models import (
    RunState, PhaseState, ExecutionState, Finding, 
    Artifact, ManualIntervention, RunSummary
)
from .exceptions import (
    RunNotFoundError, PhaseNotFoundError, ExecutionNotFoundError, 
    DatabaseError
)

logger = logging.getLogger(__name__)


class StateManager:
    """Manages orchestration state using SQLite database."""
    
    def __init__(self, db_path: str, artifact_base_path: str):
        """Initialize state manager.
        
        Args:
            db_path: Path to SQLite database file
            artifact_base_path: Base directory for artifacts
        """
        self.db_path = db_path
        self.artifact_base_path = Path(artifact_base_path)
        self.db: Optional[aiosqlite.Connection] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.db:
            await self.db.close()
            
    async def _initialize(self):
        """Initialize database connection and schema."""
        try:
            # Ensure parent directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.db = await aiosqlite.connect(self.db_path)
            self.db.row_factory = aiosqlite.Row
            await initialize_database(self.db)
            logger.info(f"State manager initialized with database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize state manager: {e}")
            raise DatabaseError("Failed to initialize database", e)
    
    # Run Management
    
    async def create_run(
        self, 
        repo_path: str, 
        branch: str, 
        doc_path: str, 
        config: dict
    ) -> RunState:
        """Create new orchestration run."""
        run_id = str(uuid.uuid4())
        now = datetime.now()
        config_snapshot = json.dumps(config)
        
        try:
            await self.db.execute(
                """INSERT INTO runs (
                    run_id, created_at, updated_at, status, repo_path, branch,
                    documentation_path, config_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, now, now, 'planning', repo_path, branch, doc_path, config_snapshot)
            )
            await self.db.commit()
            logger.info(f"Created run {run_id}")
            
            return RunState(
                run_id=run_id,
                created_at=now,
                updated_at=now,
                status='planning',
                repo_path=repo_path,
                branch=branch,
                documentation_path=doc_path,
                config_snapshot=config_snapshot
            )
        except Exception as e:
            logger.error(f"Failed to create run: {e}")
            raise DatabaseError("Failed to create run", e)
    
    async def get_run(self, run_id: str) -> Optional[RunState]:
        """Get run by ID."""
        try:
            async with self.db.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return RunState(**dict(row))
                return None
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            raise DatabaseError(f"Failed to get run {run_id}", e)
    
    async def update_run_status(
        self, 
        run_id: str, 
        status: str, 
        error: Optional[str] = None
    ):
        """Update run status."""
        try:
            now = datetime.now()
            await self.db.execute(
                """UPDATE runs 
                   SET status = ?, updated_at = ?, error_message = ?
                   WHERE run_id = ?""",
                (status, now, error, run_id)
            )
            await self.db.commit()
            logger.info(f"Updated run {run_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update run status: {e}")
            raise DatabaseError("Failed to update run status", e)
    
    async def list_runs(
        self, 
        status: Optional[str] = None, 
        limit: int = 50
    ) -> List[RunState]:
        """List runs with optional status filter."""
        try:
            if status:
                query = "SELECT * FROM runs WHERE status = ? ORDER BY created_at DESC LIMIT ?"
                params = (status, limit)
            else:
                query = "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?"
                params = (limit,)
            
            async with self.db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [RunState(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            raise DatabaseError("Failed to list runs", e)
    
    async def get_latest_run(self) -> Optional[RunState]:
        """Get most recent run."""
        runs = await self.list_runs(limit=1)
        return runs[0] if runs else None
    
    async def list_recent_runs(self, limit: int = 10) -> List[RunState]:
        """List recent runs with default limit."""
        return await self.list_runs(limit=limit)
    
    # Phase Management
    
    async def create_phase(
        self,
        run_id: str,
        phase_number: int,
        title: str,
        intent: str,
        plan: dict,
        max_retries: int,
        size: str = 'medium'
    ) -> PhaseState:
        """Create new phase."""
        phase_id = str(uuid.uuid4())
        now = datetime.now()
        plan_json = json.dumps(plan)
        
        try:
            await self.db.execute(
                """INSERT INTO phases (
                    phase_id, run_id, phase_number, title, intent, size,
                    status, created_at, plan_json, max_retries
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (phase_id, run_id, phase_number, title, intent, size, 
                 'pending', now, plan_json, max_retries)
            )
            
            # Update run total_phases
            await self.db.execute(
                "UPDATE runs SET total_phases = total_phases + 1 WHERE run_id = ?",
                (run_id,)
            )
            
            await self.db.commit()
            logger.info(f"Created phase {phase_id} (Phase {phase_number}: {title})")
            
            return PhaseState(
                phase_id=phase_id,
                run_id=run_id,
                phase_number=phase_number,
                title=title,
                intent=intent,
                size=size,
                status='pending',
                created_at=now,
                plan_json=plan_json,
                max_retries=max_retries
            )
        except Exception as e:
            logger.error(f"Failed to create phase: {e}")
            raise DatabaseError("Failed to create phase", e)
    
    async def get_phase(self, phase_id: str) -> Optional[PhaseState]:
        """Get phase by ID."""
        try:
            async with self.db.execute(
                "SELECT * FROM phases WHERE phase_id = ?", (phase_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return PhaseState(**dict(row))
                return None
        except Exception as e:
            logger.error(f"Failed to get phase {phase_id}: {e}")
            raise DatabaseError(f"Failed to get phase {phase_id}", e)
    
    async def get_phases_for_run(self, run_id: str) -> List[PhaseState]:
        """Get all phases for a run."""
        try:
            async with self.db.execute(
                "SELECT * FROM phases WHERE run_id = ? ORDER BY phase_number",
                (run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [PhaseState(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get phases for run {run_id}: {e}")
            raise DatabaseError(f"Failed to get phases for run {run_id}", e)
    
    async def update_phase_status(
        self,
        phase_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        """Update phase status."""
        try:
            updates = ["status = ?"]
            params = [status]
            
            if started_at:
                updates.append("started_at = ?")
                params.append(started_at)
            if completed_at:
                updates.append("completed_at = ?")
                params.append(completed_at)
            
            params.append(phase_id)
            
            await self.db.execute(
                f"UPDATE phases SET {', '.join(updates)} WHERE phase_id = ?",
                params
            )
            
            # Update run's current_phase_id and completed_phases
            if status == 'in_progress':
                await self.db.execute(
                    "UPDATE runs SET current_phase_id = ? WHERE run_id = (SELECT run_id FROM phases WHERE phase_id = ?)",
                    (phase_id, phase_id)
                )
            elif status == 'completed':
                await self.db.execute(
                    "UPDATE runs SET completed_phases = completed_phases + 1 WHERE run_id IN (SELECT run_id FROM phases WHERE phase_id = ?)",
                    (phase_id,)
                )
            
            await self.db.commit()
            logger.info(f"Updated phase {phase_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update phase status: {e}")
            raise DatabaseError("Failed to update phase status", e)
    
    async def increment_phase_retry(self, phase_id: str) -> int:
        """Increment retry count and return new count."""
        try:
            await self.db.execute(
                "UPDATE phases SET retry_count = retry_count + 1 WHERE phase_id = ?",
                (phase_id,)
            )
            await self.db.commit()
            
            async with self.db.execute(
                "SELECT retry_count FROM phases WHERE phase_id = ?", (phase_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Failed to increment retry count: {e}")
            raise DatabaseError("Failed to increment retry count", e)
    
    async def get_current_phase(self, run_id: str) -> Optional[PhaseState]:
        """Get currently executing phase."""
        try:
            async with self.db.execute(
                """SELECT * FROM phases 
                   WHERE run_id = ? AND status = 'in_progress'
                   ORDER BY phase_number LIMIT 1""",
                (run_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return PhaseState(**dict(row))
                return None
        except Exception as e:
            logger.error(f"Failed to get current phase: {e}")
            raise DatabaseError("Failed to get current phase", e)
    
    # Execution Management
    
    async def create_execution(
        self,
        phase_id: str,
        pass_number: int,
        copilot_input_path: str,
        execution_mode: str
    ) -> ExecutionState:
        """Create execution record."""
        execution_id = str(uuid.uuid4())
        now = datetime.now()
        
        try:
            await self.db.execute(
                """INSERT INTO executions (
                    execution_id, phase_id, pass_number, started_at,
                    status, copilot_input_path, execution_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (execution_id, phase_id, pass_number, now, 'running', 
                 copilot_input_path, execution_mode)
            )
            await self.db.commit()
            logger.info(f"Created execution {execution_id} (pass {pass_number})")
            
            return ExecutionState(
                execution_id=execution_id,
                phase_id=phase_id,
                pass_number=pass_number,
                started_at=now,
                status='running',
                copilot_input_path=copilot_input_path,
                execution_mode=execution_mode
            )
        except Exception as e:
            logger.error(f"Failed to create execution: {e}")
            raise DatabaseError("Failed to create execution", e)
    
    async def complete_execution(
        self,
        execution_id: str,
        copilot_output_path: str,
        copilot_summary: str
    ):
        """Mark execution complete."""
        try:
            now = datetime.now()
            await self.db.execute(
                """UPDATE executions 
                   SET status = 'completed', completed_at = ?,
                       copilot_output_path = ?, copilot_summary = ?
                   WHERE execution_id = ?""",
                (now, copilot_output_path, copilot_summary, execution_id)
            )
            await self.db.commit()
            logger.info(f"Completed execution {execution_id}")
        except Exception as e:
            logger.error(f"Failed to complete execution: {e}")
            raise DatabaseError("Failed to complete execution", e)
    
    async def fail_execution(self, execution_id: str, error: str):
        """Mark execution failed."""
        try:
            now = datetime.now()
            await self.db.execute(
                """UPDATE executions 
                   SET status = 'failed', completed_at = ?, error_message = ?
                   WHERE execution_id = ?""",
                (now, error, execution_id)
            )
            await self.db.commit()
            logger.info(f"Failed execution {execution_id}")
        except Exception as e:
            logger.error(f"Failed to mark execution as failed: {e}")
            raise DatabaseError("Failed to mark execution as failed", e)
    
    async def get_executions_for_phase(self, phase_id: str) -> List[ExecutionState]:
        """Get all executions for a phase."""
        try:
            async with self.db.execute(
                "SELECT * FROM executions WHERE phase_id = ? ORDER BY pass_number",
                (phase_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [ExecutionState(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get executions: {e}")
            raise DatabaseError("Failed to get executions", e)
    
    # Findings Management
    
    async def add_finding(
        self,
        execution_id: str,
        severity: str,
        category: str,
        title: str,
        description: str,
        evidence: str,
        suggested_fix: Optional[str] = None
    ) -> Finding:
        """Add finding."""
        finding_id = str(uuid.uuid4())
        now = datetime.now()
        
        try:
            await self.db.execute(
                """INSERT INTO findings (
                    finding_id, execution_id, severity, category, title,
                    description, evidence, suggested_fix, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (finding_id, execution_id, severity, category, title,
                 description, evidence, suggested_fix, now)
            )
            await self.db.commit()
            logger.debug(f"Added {severity} finding: {title}")
            
            return Finding(
                finding_id=finding_id,
                execution_id=execution_id,
                severity=severity,
                category=category,
                title=title,
                description=description,
                evidence=evidence,
                suggested_fix=suggested_fix,
                created_at=now
            )
        except Exception as e:
            logger.error(f"Failed to add finding: {e}")
            raise DatabaseError("Failed to add finding", e)
    
    async def get_findings_for_execution(self, execution_id: str) -> List[Finding]:
        """Get findings for an execution."""
        try:
            async with self.db.execute(
                "SELECT * FROM findings WHERE execution_id = ? ORDER BY severity, created_at",
                (execution_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [Finding(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get findings: {e}")
            raise DatabaseError("Failed to get findings", e)
    
    async def get_findings_for_phase(self, phase_id: str) -> List[Finding]:
        """Get all findings for a phase across all executions."""
        try:
            async with self.db.execute(
                """SELECT f.* FROM findings f
                   JOIN executions e ON f.execution_id = e.execution_id
                   WHERE e.phase_id = ?
                   ORDER BY e.pass_number DESC, f.severity, f.created_at""",
                (phase_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [Finding(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get findings for phase: {e}")
            raise DatabaseError("Failed to get findings for phase", e)
    
    async def get_findings_summary(self, execution_id: str) -> Dict[str, int]:
        """Get counts by severity."""
        try:
            async with self.db.execute(
                """SELECT severity, COUNT(*) as count 
                   FROM findings 
                   WHERE execution_id = ? 
                   GROUP BY severity""",
                (execution_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {row['severity']: row['count'] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get findings summary: {e}")
            raise DatabaseError("Failed to get findings summary", e)
    
    async def mark_finding_resolved(self, finding_id: str):
        """Mark finding as resolved."""
        try:
            await self.db.execute(
                "UPDATE findings SET resolved = 1 WHERE finding_id = ?",
                (finding_id,)
            )
            await self.db.commit()
            logger.debug(f"Marked finding {finding_id} as resolved")
        except Exception as e:
            logger.error(f"Failed to mark finding as resolved: {e}")
            raise DatabaseError("Failed to mark finding as resolved", e)
    
    async def get_unresolved_findings(
        self,
        execution_id: str,
        severities: List[str]
    ) -> List[Finding]:
        """Get unresolved findings by severity."""
        try:
            placeholders = ','.join('?' * len(severities))
            async with self.db.execute(
                f"""SELECT * FROM findings 
                    WHERE execution_id = ? AND severity IN ({placeholders}) AND resolved = 0
                    ORDER BY severity, created_at""",
                [execution_id] + severities
            ) as cursor:
                rows = await cursor.fetchall()
                return [Finding(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get unresolved findings: {e}")
            raise DatabaseError("Failed to get unresolved findings", e)
    
    # Artifact Management
    
    async def register_artifact(
        self,
        run_id: str,
        artifact_type: str,
        file_path: str,
        phase_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Artifact:
        """Register artifact."""
        artifact_id = str(uuid.uuid4())
        now = datetime.now()
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            await self.db.execute(
                """INSERT INTO artifacts (
                    artifact_id, run_id, phase_id, execution_id, artifact_type,
                    file_path, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (artifact_id, run_id, phase_id, execution_id, artifact_type,
                 file_path, now, metadata_json)
            )
            await self.db.commit()
            logger.debug(f"Registered artifact {artifact_type}: {file_path}")
            
            return Artifact(
                artifact_id=artifact_id,
                run_id=run_id,
                phase_id=phase_id,
                execution_id=execution_id,
                artifact_type=artifact_type,
                file_path=file_path,
                created_at=now,
                metadata=metadata_json
            )
        except Exception as e:
            logger.error(f"Failed to register artifact: {e}")
            raise DatabaseError("Failed to register artifact", e)
    
    async def get_artifacts_for_run(
        self,
        run_id: str,
        artifact_type: Optional[str] = None
    ) -> List[Artifact]:
        """Get artifacts for a run."""
        try:
            if artifact_type:
                query = "SELECT * FROM artifacts WHERE run_id = ? AND artifact_type = ? ORDER BY created_at"
                params = (run_id, artifact_type)
            else:
                query = "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at"
                params = (run_id,)
            
            async with self.db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [Artifact(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get artifacts: {e}")
            raise DatabaseError("Failed to get artifacts", e)
    
    async def get_artifacts_for_phase(self, phase_id: str) -> List[Artifact]:
        """Get artifacts for a phase."""
        try:
            async with self.db.execute(
                "SELECT * FROM artifacts WHERE phase_id = ? ORDER BY created_at",
                (phase_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [Artifact(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get phase artifacts: {e}")
            raise DatabaseError("Failed to get phase artifacts", e)
    
    async def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID."""
        try:
            async with self.db.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Artifact(**dict(row))
                return None
        except Exception as e:
            logger.error(f"Failed to get artifact {artifact_id}: {e}")
            raise DatabaseError(f"Failed to get artifact {artifact_id}", e)
    
    # Manual Intervention
    
    async def create_intervention(
        self,
        phase_id: str,
        reason: str
    ) -> ManualIntervention:
        """Create intervention record."""
        intervention_id = str(uuid.uuid4())
        now = datetime.now()
        
        try:
            await self.db.execute(
                """INSERT INTO manual_interventions (
                    intervention_id, phase_id, created_at, reason
                ) VALUES (?, ?, ?, ?)""",
                (intervention_id, phase_id, now, reason)
            )
            await self.db.commit()
            logger.warning(f"Created intervention for phase {phase_id}: {reason}")
            
            return ManualIntervention(
                intervention_id=intervention_id,
                phase_id=phase_id,
                created_at=now,
                reason=reason
            )
        except Exception as e:
            logger.error(f"Failed to create intervention: {e}")
            raise DatabaseError("Failed to create intervention", e)
    
    async def resolve_intervention(
        self,
        intervention_id: str,
        action: str,
        notes: Optional[str] = None
    ):
        """Resolve intervention."""
        try:
            now = datetime.now()
            await self.db.execute(
                """UPDATE manual_interventions 
                   SET action_taken = ?, notes = ?, resolved_at = ?
                   WHERE intervention_id = ?""",
                (action, notes, now, intervention_id)
            )
            await self.db.commit()
            logger.info(f"Resolved intervention {intervention_id} with action: {action}")
        except Exception as e:
            logger.error(f"Failed to resolve intervention: {e}")
            raise DatabaseError("Failed to resolve intervention", e)
    
    async def get_pending_interventions(self, run_id: str) -> List[ManualIntervention]:
        """Get unresolved interventions."""
        try:
            async with self.db.execute(
                """SELECT mi.* FROM manual_interventions mi
                   JOIN phases p ON mi.phase_id = p.phase_id
                   WHERE p.run_id = ? AND mi.resolved_at IS NULL
                   ORDER BY mi.created_at""",
                (run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [ManualIntervention(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get pending interventions: {e}")
            raise DatabaseError("Failed to get pending interventions", e)
    
    # JSON Export
    
    async def export_run_to_json(self, run_id: str, output_path: str):
        """Export complete run state to JSON."""
        try:
            run = await self.get_run(run_id)
            if not run:
                raise RunNotFoundError(run_id)
            
            phases = await self.get_phases_for_run(run_id)
            artifacts = await self.get_artifacts_for_run(run_id)
            
            phase_data = []
            for phase in phases:
                executions = await self.get_executions_for_phase(phase.phase_id)
                execution_data = []
                
                for execution in executions:
                    findings = await self.get_findings_for_execution(execution.execution_id)
                    execution_data.append({
                        'execution': execution.to_dict(),
                        'findings': [f.to_dict() for f in findings]
                    })
                
                phase_data.append({
                    'phase': phase.to_dict(),
                    'executions': execution_data
                })
            
            export = {
                'run': run.to_dict(),
                'phases': phase_data,
                'artifacts': [a.to_dict() for a in artifacts]
            }
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export, f, indent=2)
            
            logger.info(f"Exported run {run_id} to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export run: {e}")
            raise DatabaseError("Failed to export run", e)
    
    async def export_phase_to_json(self, phase_id: str, output_path: str):
        """Export single phase to JSON."""
        try:
            phase = await self.get_phase(phase_id)
            if not phase:
                raise PhaseNotFoundError(phase_id)
            
            executions = await self.get_executions_for_phase(phase_id)
            artifacts = await self.get_artifacts_for_phase(phase_id)
            
            execution_data = []
            for execution in executions:
                findings = await self.get_findings_for_execution(execution.execution_id)
                execution_data.append({
                    'execution': execution.to_dict(),
                    'findings': [f.to_dict() for f in findings]
                })
            
            export = {
                'phase': phase.to_dict(),
                'executions': execution_data,
                'artifacts': [a.to_dict() for a in artifacts]
            }
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export, f, indent=2)
            
            logger.info(f"Exported phase {phase_id} to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export phase: {e}")
            raise DatabaseError("Failed to export phase", e)
    
    async def export_run_summary(self, run_id: str) -> RunSummary:
        """Generate summary object for reporting."""
        try:
            run = await self.get_run(run_id)
            if not run:
                raise RunNotFoundError(run_id)
            
            phases = await self.get_phases_for_run(run_id)
            artifacts = await self.get_artifacts_for_run(run_id)
            
            execution_count = 0
            findings_summary = {'major': 0, 'medium': 0, 'minor': 0}
            
            for phase in phases:
                executions = await self.get_executions_for_phase(phase.phase_id)
                execution_count += len(executions)
                
                for execution in executions:
                    summary = await self.get_findings_summary(execution.execution_id)
                    for severity, count in summary.items():
                        findings_summary[severity] = findings_summary.get(severity, 0) + count
            
            return RunSummary(
                run=run,
                phases=phases,
                execution_count=execution_count,
                findings_summary=findings_summary,
                artifacts_count=len(artifacts)
            )
        except Exception as e:
            logger.error(f"Failed to export run summary: {e}")
            raise DatabaseError("Failed to export run summary", e)
    
    async def get_run_summary(self, run_id: str):
        """Get run summary for display purposes."""
        return await self.export_run_summary(run_id)
    
    # Recovery
    
    async def get_recoverable_runs(self) -> List[RunState]:
        """Get runs that can be recovered."""
        return await self.list_runs(status='executing') + await self.list_runs(status='paused')
    
    async def recover_run(self, run_id: str) -> Tuple[RunState, Optional[PhaseState]]:
        """Load run state for recovery."""
        try:
            run = await self.get_run(run_id)
            if not run:
                raise RunNotFoundError(run_id)
            
            current_phase = await self.get_current_phase(run_id)
            logger.info(f"Recovered run {run_id}")
            return run, current_phase
        except Exception as e:
            logger.error(f"Failed to recover run: {e}")
            raise DatabaseError("Failed to recover run", e)
    
    async def cleanup_failed_run(self, run_id: str):
        """Mark run as failed and clean up."""
        await self.update_run_status(run_id, 'failed', 'Cleanup after failure')
        logger.info(f"Cleaned up failed run {run_id}")
    
    # Utilities
    
    async def vacuum_database(self):
        """Optimize database."""
        try:
            await self.db.execute("VACUUM")
            await self.db.commit()
            logger.info("Database vacuumed")
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            raise DatabaseError("Failed to vacuum database", e)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            stats = {}
            
            async with self.db.execute("SELECT COUNT(*) FROM runs") as cursor:
                row = await cursor.fetchone()
                stats['total_runs'] = row[0]
            
            async with self.db.execute("SELECT COUNT(*) FROM phases") as cursor:
                row = await cursor.fetchone()
                stats['total_phases'] = row[0]
            
            async with self.db.execute(
                "SELECT severity, COUNT(*) as count FROM findings GROUP BY severity"
            ) as cursor:
                rows = await cursor.fetchall()
                stats['findings_by_severity'] = {row['severity']: row['count'] for row in rows}
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            raise DatabaseError("Failed to get statistics", e)
