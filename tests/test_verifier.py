"""
Tests for the verification system.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from orchestrator.verifier import PhaseVerifier, VerificationConfig
from orchestrator.verification_models import VerificationResult, ChecklistItem, SpecComplianceResult
from orchestrator.models import Finding


@pytest.fixture
def verification_config():
    """Create test verification config."""
    return VerificationConfig({
        "build_enabled": True,
        "build_command": "echo 'build success'",
        "build_timeout": 10,
        "test_enabled": True,
        "test_command": "echo 'tests passed'",
        "test_timeout": 10,
        "lint_enabled": False,
        "security_scan_enabled": False,
        "spec_validation_enabled": True,
        "spec_validation_temperature": 0.3,
        "findings_thresholds": {
            "major": 0,
            "medium": 3,
            "minor": 10
        },
        "custom_tests": []
    })


@pytest.fixture
def mock_state_manager():
    """Create mock state manager."""
    manager = Mock()
    manager.add_finding = Mock()
    manager.get_findings_for_phase = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock()
    client.generate = AsyncMock(return_value='{"checklist_results": [], "spec_compliance": {"compliant": true}, "overall_assessment": "All good"}')
    return client


@pytest.fixture
def verifier(verification_config, mock_state_manager, mock_llm_client, tmp_path):
    """Create verifier instance."""
    prompts = {
        "spec_validation_system_prompt": "Validate spec",
        "spec_validation_prompt": "Check if {original_spec} matches {git_diff}"
    }
    return PhaseVerifier(
        state_manager=mock_state_manager,
        llm_client=mock_llm_client,
        config=verification_config,
        repo_path=tmp_path,
        prompts_config=prompts
    )


class TestVerificationConfig:
    """Test VerificationConfig class."""
    
    def test_config_initialization(self):
        """Test config initialization with defaults."""
        config = VerificationConfig({})
        assert config.build_enabled is False
        assert config.test_enabled is False
        assert config.spec_validation_enabled is True
        assert config.findings_thresholds == {"major": 0, "medium": 3, "minor": 10}
    
    def test_config_with_custom_values(self):
        """Test config with custom values."""
        config = VerificationConfig({
            "build_enabled": True,
            "build_command": "make build",
            "build_timeout": 300,
            "findings_thresholds": {"major": 1, "medium": 5, "minor": 20}
        })
        assert config.build_enabled is True
        assert config.build_command == "make build"
        assert config.build_timeout == 300
        assert config.findings_thresholds["major"] == 1


class TestPhaseVerifier:
    """Test PhaseVerifier class."""
    
    @pytest.mark.asyncio
    async def test_run_build_check_success(self, verifier):
        """Test successful build check."""
        findings = await verifier._run_build_check("exec_001")
        assert len(findings) == 0
    
    @pytest.mark.asyncio
    async def test_run_build_check_failure(self, verifier):
        """Test build check failure."""
        verifier.config.build_command = "exit 1"
        findings = await verifier._run_build_check("exec_001")
        assert len(findings) == 1
        assert findings[0].severity == "major"
        assert findings[0].category == "build"
    
    @pytest.mark.asyncio
    async def test_run_test_check_success(self, verifier):
        """Test successful test check."""
        findings = await verifier._run_test_check("exec_001")
        assert len(findings) == 0
    
    @pytest.mark.asyncio
    async def test_run_test_check_failure(self, verifier):
        """Test test check failure."""
        verifier.config.test_command = "echo 'FAILED test_something' && exit 1"
        findings = await verifier._run_test_check("exec_001")
        assert len(findings) == 1
        assert findings[0].severity == "medium"
        assert findings[0].category == "test"
    
    @pytest.mark.asyncio
    async def test_extract_checklist_from_spec(self, verifier):
        """Test checklist extraction."""
        spec = """# Phase Specification

## Acceptance Criteria
- [ ] Implement user login
- [ ] Add password validation
- [x] Setup database
- [ ] Write tests
"""
        items = verifier._extract_checklist_from_spec(spec)
        assert len(items) == 3  # Only unchecked items (- [ ])
        assert "Implement user login" in items
        assert "Add password validation" in items
        assert "Write tests" in items
        assert "Setup database" not in items  # This one is checked [x]
    
    def test_check_findings_thresholds_pass(self, verifier):
        """Test threshold check passing."""
        findings_summary = {"major": 0, "medium": 2, "minor": 5}
        result = verifier._check_findings_thresholds(findings_summary)
        assert result is True
    
    def test_check_findings_thresholds_fail_major(self, verifier):
        """Test threshold check failing on major."""
        findings_summary = {"major": 1, "medium": 0, "minor": 0}
        result = verifier._check_findings_thresholds(findings_summary)
        assert result is False
    
    def test_check_findings_thresholds_fail_medium(self, verifier):
        """Test threshold check failing on medium."""
        findings_summary = {"major": 0, "medium": 5, "minor": 0}
        result = verifier._check_findings_thresholds(findings_summary)
        assert result is False
    
    def test_create_finding(self, verifier, mock_state_manager):
        """Test finding creation."""
        finding = verifier._create_finding(
            execution_id="exec_001",
            severity="major",
            category="build",
            title="Build Failed",
            description="Build command failed",
            evidence="Error: module not found",
            suggested_fix="Install missing module"
        )
        assert finding.severity == "major"
        assert finding.category == "build"
        assert finding.title == "Build Failed"
        # Findings are not persisted immediately by _create_finding
        # They are persisted in batch by verify_phase_execution
        mock_state_manager.add_finding.assert_not_called()


class TestVerificationResult:
    """Test VerificationResult dataclass."""
    
    def test_verification_result_creation(self):
        """Test creating verification result."""
        result = VerificationResult(
            passed=True,
            findings=[],
            findings_summary={"major": 0, "medium": 0, "minor": 0},
            failed_checklist_items=[],
            execution_time=1.5,
            checks_run=["build", "test"]
        )
        assert result.passed is True
        assert result.execution_time == 1.5
        assert "build" in result.checks_run
    
    def test_verification_result_with_findings(self):
        """Test verification result with findings."""
        finding = Finding(
            finding_id="f1",
            execution_id="exec_001",
            severity="medium",
            category="test",
            title="Test Failed",
            description="Unit test failed",
            evidence="AssertionError",
            suggested_fix="Fix assertion",
            created_at=datetime.now()
        )
        result = VerificationResult(
            passed=False,
            findings=[finding],
            findings_summary={"major": 0, "medium": 1, "minor": 0},
            failed_checklist_items=["Write tests"],
            execution_time=2.0,
            checks_run=["test"]
        )
        assert result.passed is False
        assert len(result.findings) == 1
        assert result.findings_summary["medium"] == 1


class TestFeedbackSpecGeneration:
    """Test feedback spec generation."""
    
    @pytest.mark.asyncio
    async def test_generate_feedback_spec(self, verifier, tmp_path):
        """Test feedback spec generation."""
        # Create original spec
        spec_path = tmp_path / "spec.md"
        spec_path.write_text("# Original Spec\n\nImplement feature X")
        
        # Create finding
        finding = Finding(
            finding_id="f1",
            execution_id="exec_001",
            severity="major",
            category="build",
            title="Build Failed",
            description="Build error",
            evidence="Error: syntax error",
            suggested_fix="Fix syntax",
            created_at=datetime.now()
        )
        
        # Generate feedback spec
        feedback_path = await verifier.generate_feedback_spec(
            original_spec_path=spec_path,
            findings=[finding],
            failed_checklist_items=["Item 1", "Item 2"],
            pass_number=1,
            copilot_summary="Attempted implementation"
        )
        
        assert feedback_path.exists()
        content = feedback_path.read_text()
        assert "Original Spec" in content
        assert "Build Failed" in content
        assert "Item 1" in content


class TestFindingsReport:
    """Test findings report generation."""
    
    @pytest.mark.asyncio
    async def test_generate_findings_report(self, verifier, tmp_path):
        """Test findings report generation."""
        finding = Finding(
            finding_id="f1",
            execution_id="exec_001",
            severity="medium",
            category="test",
            title="Test Failed",
            description="Test failure",
            evidence="AssertionError: expected 5, got 3",
            suggested_fix="Fix calculation",
            created_at=datetime.now()
        )
        
        result = VerificationResult(
            passed=False,
            findings=[finding],
            findings_summary={"major": 0, "medium": 1, "minor": 0},
            failed_checklist_items=["Complete tests"],
            execution_time=2.5,
            checks_run=["test", "build"]
        )
        
        report_path = tmp_path / "findings.md"
        await verifier.generate_findings_report(
            phase_number=1,
            phase_title="Test Phase",
            pass_number=1,
            verification_result=result,
            output_path=report_path
        )
        
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Test Failed" in content
        assert "Medium" in content or "medium" in content
        assert "Complete tests" in content
    
    @pytest.mark.asyncio
    async def test_generate_findings_json(self, verifier, tmp_path):
        """Test findings JSON generation."""
        finding = Finding(
            finding_id="f1",
            execution_id="exec_001",
            severity="major",
            category="build",
            title="Build Failed",
            description="Build error",
            evidence="Error: syntax error",
            suggested_fix="Fix syntax",
            created_at=datetime.now()
        )
        
        spec_compliance = SpecComplianceResult(
            compliant=False,
            deviations=["Missing error handling"],
            missing_implementations=["Input validation"],
            overall_assessment="Implementation incomplete"
        )
        
        result = VerificationResult(
            passed=False,
            findings=[finding],
            findings_summary={"major": 1, "medium": 0, "minor": 0},
            failed_checklist_items=["Item 1"],
            execution_time=3.2,
            checks_run=["build", "spec_validation"],
            spec_compliance=spec_compliance
        )
        
        json_path = tmp_path / "Findings.json"
        await verifier.generate_findings_json(
            phase_number=1,
            phase_title="Test Phase",
            pass_number=1,
            verification_result=result,
            output_path=json_path
        )
        
        # Assert file exists
        assert json_path.exists()
        
        # Load and validate JSON structure
        import json
        with open(json_path, "r") as f:
            data = json.load(f)
        
        # Validate structure
        assert data["phase_number"] == 1
        assert data["phase_title"] == "Test Phase"
        assert data["pass_number"] == 1
        assert data["passed"] is False
        assert len(data["findings"]) == 1
        assert data["findings"][0]["finding_id"] == "f1"
        assert data["findings"][0]["severity"] == "major"
        assert data["findings"][0]["category"] == "build"
        assert data["findings"][0]["title"] == "Build Failed"
        assert data["findings_summary"]["major"] == 1
        assert data["failed_checklist_items"] == ["Item 1"]
        assert data["spec_compliance"]["compliant"] is False
        assert "Missing error handling" in data["spec_compliance"]["deviations"]
        assert data["checks_run"] == ["build", "spec_validation"]
        assert data["execution_time"] == 3.2
    
    @pytest.mark.asyncio
    async def test_generate_findings_reports(self, verifier, tmp_path):
        """Test generating both MD and JSON reports."""
        finding = Finding(
            finding_id="f1",
            execution_id="exec_001",
            severity="minor",
            category="lint",
            title="Linting Issue",
            description="Code style violation",
            evidence="Line too long",
            suggested_fix="Break line",
            created_at=datetime.now()
        )
        
        result = VerificationResult(
            passed=True,
            findings=[finding],
            findings_summary={"major": 0, "medium": 0, "minor": 1},
            failed_checklist_items=[],
            execution_time=1.0,
            checks_run=["lint"]
        )
        
        md_path, json_path = await verifier.generate_findings_reports(
            phase_number=2,
            phase_title="Lint Phase",
            pass_number=1,
            verification_result=result,
            output_dir=tmp_path
        )
        
        # Assert both files exist
        assert md_path.exists()
        assert json_path.exists()
        assert md_path.name == "findings_report.md"
        assert json_path.name == "Findings.json"
        
        # Verify MD content
        md_content = md_path.read_text(encoding="utf-8")
        assert "Linting Issue" in md_content
        
        # Verify JSON content
        import json
        with open(json_path, "r") as f:
            json_data = json.load(f)
        assert json_data["phase_number"] == 2
        assert json_data["passed"] is True
        assert len(json_data["findings"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
