from dataclasses import dataclass, field
from typing import List, Dict, Optional
from orchestrator.models import Finding


@dataclass
class ChecklistItem:
    text: str
    completed: bool
    evidence: str
    suggested_fix: Optional[str] = None


@dataclass
class SpecComplianceResult:
    compliant: bool
    deviations: List[str]
    missing_implementations: List[str]
    overall_assessment: str


@dataclass
class VerificationResult:
    passed: bool
    findings: List[Finding]
    findings_summary: Dict[str, int]
    failed_checklist_items: List[str]
    execution_time: float
    checks_run: List[str]
    spec_compliance: Optional[SpecComplianceResult] = None
