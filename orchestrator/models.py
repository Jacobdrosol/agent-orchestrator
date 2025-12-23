"""Pydantic models for Agent Orchestrator state objects."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict
import json


class PhasePlan(BaseModel):
    """Structured plan for a phase."""
    files: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


class RunState(BaseModel):
    """State of an orchestration run."""
    run_id: str
    created_at: datetime
    updated_at: datetime
    status: str
    repo_path: str
    branch: str
    documentation_path: str
    config_snapshot: str
    total_phases: int = 0
    completed_phases: int = 0
    current_phase_id: Optional[str] = None
    error_message: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {'planning', 'executing', 'paused', 'completed', 'failed', 'aborted'}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunState':
        """Create from dictionary."""
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class PhaseState(BaseModel):
    """State of an execution phase."""
    phase_id: str
    run_id: str
    phase_number: int
    title: str
    intent: str
    size: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    spec_path: Optional[str] = None
    plan_json: str
    branch_name: Optional[str] = None
    retry_count: int = 0
    max_retries: int
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('phase_number')
    @classmethod
    def validate_phase_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("phase_number must be greater than 0")
        return v
    
    @field_validator('size')
    @classmethod
    def validate_size(cls, v: str) -> str:
        allowed = {'small', 'medium', 'large'}
        if v not in allowed:
            raise ValueError(f"Size must be one of {allowed}")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {'pending', 'in_progress', 'completed', 'failed', 'skipped'}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v
    
    def get_plan(self) -> PhasePlan:
        """Parse plan_json into PhasePlan object."""
        try:
            data = json.loads(self.plan_json)
            return PhasePlan(**data)
        except Exception:
            return PhasePlan()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


class ExecutionState(BaseModel):
    """State of an execution attempt."""
    execution_id: str
    phase_id: str
    pass_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    copilot_input_path: str
    copilot_output_path: Optional[str] = None
    copilot_summary: Optional[str] = None
    execution_mode: str
    error_message: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('pass_number')
    @classmethod
    def validate_pass_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("pass_number must be greater than 0")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {'running', 'completed', 'failed'}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v
    
    @field_validator('execution_mode')
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        allowed = {'direct', 'branch'}
        if v not in allowed:
            raise ValueError(f"Execution mode must be one of {allowed}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.model_dump()
        data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


class Finding(BaseModel):
    """Verification finding."""
    finding_id: str
    execution_id: str
    severity: str
    category: str
    title: str
    description: str
    evidence: str
    suggested_fix: Optional[str] = None
    resolved: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {'major', 'medium', 'minor'}
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {'build', 'test', 'lint', 'security', 'spec_validation', 'custom'}
        if v not in allowed:
            raise ValueError(f"Category must be one of {allowed}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        return data


class Artifact(BaseModel):
    """Artifact produced during orchestration."""
    artifact_id: str
    run_id: str
    phase_id: Optional[str] = None
    execution_id: Optional[str] = None
    artifact_type: str
    file_path: str
    created_at: datetime
    metadata: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('artifact_type')
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        allowed = {'phase_plan', 'spec', 'copilot_output', 'copilot_prompt', 'findings_report', 
                   'findings_report_md', 'findings_report_json', 'verification_log', 'feedback_spec'}
        if v not in allowed:
            raise ValueError(f"Artifact type must be one of {allowed}")
        return v
    
    def get_metadata(self) -> Dict[str, Any]:
        """Parse metadata JSON."""
        if self.metadata:
            try:
                return json.loads(self.metadata)
            except Exception:
                return {}
        return {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        return data


class ManualIntervention(BaseModel):
    """Manual intervention record."""
    intervention_id: str
    phase_id: str
    created_at: datetime
    reason: str
    action_taken: Optional[str] = None
    notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        allowed = {'max_retries_exceeded', 'user_requested', 'critical_error'}
        if v not in allowed:
            raise ValueError(f"Reason must be one of {allowed}")
        return v
    
    @field_validator('action_taken')
    @classmethod
    def validate_action_taken(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {'resume', 'skip', 'modify_spec', 'abort'}
            if v not in allowed:
                raise ValueError(f"Action taken must be one of {allowed}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.model_dump()
        data['created_at'] = self.created_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


class RunSummary(BaseModel):
    """Summary of a run for reporting."""
    run: RunState
    phases: List[PhaseState]
    execution_count: int
    findings_summary: Dict[str, int]
    artifacts_count: int
    
    model_config = ConfigDict(from_attributes=True)
    
    @property
    def total_phases(self) -> int:
        """Get total number of phases."""
        return self.run.total_phases
    
    @property
    def completed_phases(self) -> int:
        """Get number of completed phases."""
        return self.run.completed_phases
    
    @property
    def failed_phases(self) -> int:
        """Get number of failed phases."""
        return len([p for p in self.phases if p.status == 'failed'])
    
    @property
    def skipped_phases(self) -> int:
        """Get number of skipped phases."""
        return len([p for p in self.phases if p.status == 'skipped'])
    
    @property
    def total_executions(self) -> int:
        """Get total number of executions."""
        return self.execution_count
    
    @property
    def major_findings(self) -> int:
        """Get count of major findings."""
        return self.findings_summary.get('major', 0)
    
    @property
    def medium_findings(self) -> int:
        """Get count of medium findings."""
        return self.findings_summary.get('medium', 0)
    
    @property
    def minor_findings(self) -> int:
        """Get count of minor findings."""
        return self.findings_summary.get('minor', 0)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds."""
        if self.run.status in ('completed', 'failed', 'aborted'):
            # Find earliest start and latest completion
            start_times = [p.created_at for p in self.phases if p.created_at]
            end_times = [p.completed_at for p in self.phases if p.completed_at]
            
            if start_times and end_times:
                earliest = min(start_times)
                latest = max(end_times)
                return (latest - earliest).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'run': self.run.to_dict(),
            'phases': [p.to_dict() for p in self.phases],
            'execution_count': self.execution_count,
            'findings_summary': self.findings_summary,
            'artifacts_count': self.artifacts_count
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_markdown(self) -> str:
        """Convert to Markdown report."""
        lines = [
            f"# Run Summary: {self.run.run_id}",
            "",
            f"**Status**: {self.run.status}",
            f"**Repository**: {self.run.repo_path}",
            f"**Branch**: {self.run.branch}",
            f"**Created**: {self.run.created_at.isoformat()}",
            f"**Total Phases**: {self.run.total_phases}",
            f"**Completed Phases**: {self.run.completed_phases}",
            "",
            "## Phases",
            ""
        ]
        
        for phase in self.phases:
            lines.append(f"### Phase {phase.phase_number}: {phase.title}")
            lines.append(f"- **Status**: {phase.status}")
            lines.append(f"- **Size**: {phase.size}")
            lines.append(f"- **Retries**: {phase.retry_count}/{phase.max_retries}")
            lines.append("")
        
        lines.extend([
            "## Statistics",
            "",
            f"- **Total Executions**: {self.execution_count}",
            f"- **Total Artifacts**: {self.artifacts_count}",
            "",
            "### Findings Summary",
            ""
        ])
        
        for severity, count in self.findings_summary.items():
            lines.append(f"- **{severity.capitalize()}**: {count}")
        
        return "\n".join(lines)
