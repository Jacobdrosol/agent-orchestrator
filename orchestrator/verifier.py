import asyncio
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from orchestrator.models import Finding
from orchestrator.verification_models import (
    ChecklistItem,
    SpecComplianceResult,
    VerificationResult
)
from orchestrator.state import StateManager
from orchestrator.llm_client import OllamaClient


logger = logging.getLogger(__name__)


class VerificationConfig:
    """Configuration for verification checks."""
    
    def __init__(self, config_dict: Dict):
        self.build_enabled = config_dict.get("build_enabled", False)
        self.build_command = config_dict.get("build_command", "")
        self.build_timeout = config_dict.get("build_timeout", 300)
        
        self.test_enabled = config_dict.get("test_enabled", False)
        self.test_command = config_dict.get("test_command", "")
        self.test_timeout = config_dict.get("test_timeout", 600)
        self.test_output_format = config_dict.get("test_output_format", "text")
        
        self.lint_enabled = config_dict.get("lint_enabled", False)
        self.lint_command = config_dict.get("lint_command", "")
        self.lint_timeout = config_dict.get("lint_timeout", 120)
        
        self.security_scan_enabled = config_dict.get("security_scan_enabled", False)
        self.security_command = config_dict.get("security_command", "")
        self.security_timeout = config_dict.get("security_timeout", 180)
        
        self.spec_validation_enabled = config_dict.get("spec_validation_enabled", True)
        self.spec_validation_temperature = config_dict.get("spec_validation_temperature", 0.3)
        
        self.custom_tests = config_dict.get("custom_tests", [])
        
        self.findings_thresholds = config_dict.get("findings_thresholds", {
            "major": 0,
            "medium": 3,
            "minor": 10
        })


class PhaseVerifier:
    """Verifies phase execution through multiple validation layers."""
    
    def __init__(
        self,
        state_manager: StateManager,
        llm_client: OllamaClient,
        config: VerificationConfig,
        repo_path: Path,
        prompts_config: Dict
    ):
        self.state_manager = state_manager
        self.llm_client = llm_client
        self.config = config
        self.repo_path = Path(repo_path)
        self.prompts_config = prompts_config
        
        # Setup Jinja2 for template rendering
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
    
    async def verify_phase_execution(
        self,
        execution_id: str,
        phase_id: str,
        spec_path: Path,
        copilot_result: Dict
    ) -> VerificationResult:
        """Main verification method - runs all enabled checks."""
        logger.info(f"Starting verification for execution {execution_id}")
        start_time = time.time()
        
        all_findings = []
        checks_run = []
        failed_checklist_items = []
        spec_compliance = None
        
        # Run build check
        if self.config.build_enabled:
            logger.info("Running build check")
            checks_run.append("build")
            try:
                findings = await self._run_build_check(execution_id)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Build check failed: {e}")
                all_findings.append(self._create_finding(
                    execution_id, "major", "build",
                    "Build Check Failed",
                    f"Build check execution failed: {str(e)}",
                    str(e),
                    "Ensure build command is correctly configured and executable"
                ))
        
        # Run test check
        if self.config.test_enabled:
            logger.info("Running test check")
            checks_run.append("test")
            try:
                findings = await self._run_test_check(execution_id)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Test check failed: {e}")
                all_findings.append(self._create_finding(
                    execution_id, "major", "test",
                    "Test Check Failed",
                    f"Test check execution failed: {str(e)}",
                    str(e),
                    "Ensure test command is correctly configured and executable"
                ))
        
        # Run lint check
        if self.config.lint_enabled:
            logger.info("Running lint check")
            checks_run.append("lint")
            try:
                findings = await self._run_lint_check(execution_id)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Lint check failed: {e}")
                all_findings.append(self._create_finding(
                    execution_id, "minor", "lint",
                    "Lint Check Failed",
                    f"Lint check execution failed: {str(e)}",
                    str(e),
                    "Ensure lint command is correctly configured and executable"
                ))
        
        # Run security scan
        if self.config.security_scan_enabled:
            logger.info("Running security scan")
            checks_run.append("security")
            try:
                findings = await self._run_security_scan(execution_id)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Security scan failed: {e}")
                all_findings.append(self._create_finding(
                    execution_id, "medium", "security",
                    "Security Scan Failed",
                    f"Security scan execution failed: {str(e)}",
                    str(e),
                    "Ensure security scan command is correctly configured and executable"
                ))
        
        # Run custom tests
        if self.config.custom_tests:
            logger.info("Running custom tests")
            checks_run.append("custom")
            try:
                findings = await self._run_custom_tests(execution_id)
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Custom tests failed: {e}")
        
        # Run spec validation
        if self.config.spec_validation_enabled:
            logger.info("Running spec validation")
            checks_run.append("spec_validation")
            try:
                findings, failed_items, compliance = await self._validate_spec_compliance(
                    execution_id, spec_path, copilot_result
                )
                all_findings.extend(findings)
                failed_checklist_items = failed_items
                spec_compliance = compliance
            except Exception as e:
                logger.error(f"Spec validation failed: {e}")
                all_findings.append(self._create_finding(
                    execution_id, "medium", "spec_validation",
                    "Spec Validation Failed",
                    f"Spec validation execution failed: {str(e)}",
                    str(e),
                    "Review spec validation configuration and LLM connectivity"
                ))
        
        # Calculate findings summary
        findings_summary = {
            "major": sum(1 for f in all_findings if f.severity == "major"),
            "medium": sum(1 for f in all_findings if f.severity == "medium"),
            "minor": sum(1 for f in all_findings if f.severity == "minor")
        }
        
        logger.info(f"Verification complete. Findings: {findings_summary}")
        
        # Persist findings to state manager
        for finding in all_findings:
            try:
                await self.state_manager.add_finding(
                    execution_id=finding.execution_id,
                    severity=finding.severity,
                    category=finding.category,
                    title=finding.title,
                    description=finding.description,
                    evidence=finding.evidence,
                    suggested_fix=finding.suggested_fix
                )
            except Exception as e:
                logger.error(f"Failed to persist finding: {e}")
        
        # Check if verification passed
        passed = self._check_findings_thresholds(findings_summary)
        
        execution_time = time.time() - start_time
        
        return VerificationResult(
            passed=passed,
            findings=all_findings,
            findings_summary=findings_summary,
            failed_checklist_items=failed_checklist_items,
            execution_time=execution_time,
            checks_run=checks_run,
            spec_compliance=spec_compliance
        )
    
    async def _run_build_check(self, execution_id: str) -> List[Finding]:
        """Execute build command and parse for errors."""
        findings = []
        
        result = await self._run_command(
            self.config.build_command,
            self.config.build_timeout,
            self.repo_path
        )
        
        if result["exit_code"] != 0:
            # Parse build errors
            error_lines = [line for line in result["stderr"].split("\n") if "error" in line.lower()]
            
            evidence = f"Command: {self.config.build_command}\n"
            evidence += f"Exit Code: {result['exit_code']}\n"
            evidence += f"Errors:\n{chr(10).join(error_lines[:10])}"
            
            findings.append(self._create_finding(
                execution_id,
                "major",
                "build",
                "Build Failed",
                "The build command failed with errors",
                evidence,
                "Fix compilation errors and ensure all dependencies are available"
            ))
        
        return findings
    
    async def _run_test_check(self, execution_id: str) -> List[Finding]:
        """Execute test command and parse results."""
        findings = []
        
        result = await self._run_command(
            self.config.test_command,
            self.config.test_timeout,
            self.repo_path
        )
        
        # Parse test output for failures
        output = result["stdout"] + result["stderr"]
        
        # Look for common test failure patterns
        failed_pattern = re.compile(r"FAILED|Failed:|✗|❌", re.IGNORECASE)
        test_failures = [line for line in output.split("\n") if failed_pattern.search(line)]
        
        if test_failures or result["exit_code"] != 0:
            evidence = f"Command: {self.config.test_command}\n"
            evidence += f"Exit Code: {result['exit_code']}\n"
            evidence += f"Failures:\n{chr(10).join(test_failures[:10])}"
            
            findings.append(self._create_finding(
                execution_id,
                "medium",
                "test",
                "Test Failures Detected",
                f"Found {len(test_failures)} test failure(s)",
                evidence,
                "Fix failing tests to ensure changes work correctly"
            ))
        
        return findings
    
    async def _run_lint_check(self, execution_id: str) -> List[Finding]:
        """Execute lint command and parse violations."""
        findings = []
        
        result = await self._run_command(
            self.config.lint_command,
            self.config.lint_timeout,
            self.repo_path
        )
        
        if result["exit_code"] != 0:
            output = result["stdout"] + result["stderr"]
            
            # Count violations
            violation_lines = [line for line in output.split("\n") if line.strip()]
            
            evidence = f"Command: {self.config.lint_command}\n"
            evidence += f"Exit Code: {result['exit_code']}\n"
            evidence += f"Violations:\n{chr(10).join(violation_lines[:20])}"
            
            findings.append(self._create_finding(
                execution_id,
                "minor",
                "lint",
                "Linting Issues Found",
                f"Code style violations detected",
                evidence,
                "Run formatter and fix linting issues"
            ))
        
        return findings
    
    async def _run_security_scan(self, execution_id: str) -> List[Finding]:
        """Execute security scan and parse vulnerabilities."""
        findings = []
        
        result = await self._run_command(
            self.config.security_command,
            self.config.security_timeout,
            self.repo_path
        )
        
        output = result["stdout"] + result["stderr"]
        
        # Look for vulnerability patterns
        vuln_pattern = re.compile(r"vulnerability|vulnerable|CVE-\d+", re.IGNORECASE)
        vulnerabilities = [line for line in output.split("\n") if vuln_pattern.search(line)]
        
        if vulnerabilities:
            evidence = f"Command: {self.config.security_command}\n"
            evidence += f"Vulnerabilities:\n{chr(10).join(vulnerabilities[:10])}"
            
            # Determine severity based on keywords
            severity = "major" if any("high" in v.lower() or "critical" in v.lower() for v in vulnerabilities) else "medium"
            
            findings.append(self._create_finding(
                execution_id,
                severity,
                "security",
                "Security Vulnerabilities Detected",
                f"Found {len(vulnerabilities)} potential security issue(s)",
                evidence,
                "Update vulnerable dependencies or apply security patches"
            ))
        
        return findings
    
    async def _run_custom_tests(self, execution_id: str) -> List[Finding]:
        """Execute custom tests from configuration."""
        findings = []
        
        for test in self.config.custom_tests:
            if not test.get("enabled", False):
                continue
            
            test_name = test.get("name", "Unknown")
            command = test.get("command", "")
            working_dir = test.get("working_directory", ".")
            timeout = test.get("timeout", 60)
            severity = test.get("severity_on_failure", "medium")
            
            logger.info(f"Running custom test: {test_name}")
            
            try:
                result = await self._run_command(
                    command,
                    timeout,
                    self.repo_path / working_dir
                )
                
                if result["exit_code"] != 0:
                    evidence = f"Test: {test_name}\n"
                    evidence += f"Command: {command}\n"
                    evidence += f"Exit Code: {result['exit_code']}\n"
                    evidence += f"Output:\n{result['stdout'][:500]}"
                    
                    findings.append(self._create_finding(
                        execution_id,
                        severity,
                        "custom",
                        f"Custom Test Failed: {test_name}",
                        f"Custom test '{test_name}' failed",
                        evidence,
                        "Review test output and fix the identified issues"
                    ))
            except Exception as e:
                logger.error(f"Custom test {test_name} failed: {e}")
        
        return findings
    
    async def _validate_spec_compliance(
        self,
        execution_id: str,
        spec_path: Path,
        copilot_result: Dict
    ) -> Tuple[List[Finding], List[str], Optional[SpecComplianceResult]]:
        """Validate changes against spec using LLM."""
        findings = []
        failed_checklist_items = []
        
        # Read spec
        spec_content = spec_path.read_text(encoding="utf-8")
        
        # Extract checklist
        checklist_items = self._extract_checklist_from_spec(spec_content)
        
        # Get git diff
        git_diff = await self._get_git_diff()
        
        # Build prompt
        prompt = self._build_spec_validation_prompt(
            spec_content,
            checklist_items,
            git_diff,
            copilot_result
        )
        
        # Call LLM
        system_prompt = self.prompts_config.get(
            "spec_validation_system_prompt",
            "You are a code review expert validating implementation against specification."
        )
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=self.config.spec_validation_temperature
            )
            
            # Parse JSON response
            validation_result = json.loads(response)
            
            # Process checklist results
            for item_result in validation_result.get("checklist_results", []):
                if not item_result.get("completed", False):
                    failed_checklist_items.append(item_result.get("item", ""))
                    
                    findings.append(self._create_finding(
                        execution_id,
                        "medium",
                        "spec_validation",
                        f"Incomplete Requirement: {item_result.get('item', '')[:50]}...",
                        item_result.get("evidence", ""),
                        item_result.get("evidence", ""),
                        item_result.get("suggested_fix", "Complete this requirement")
                    ))
            
            # Process spec compliance
            compliance = validation_result.get("spec_compliance", {})
            if not compliance.get("compliant", True):
                for deviation in compliance.get("deviations", []):
                    findings.append(self._create_finding(
                        execution_id,
                        "major",
                        "spec_validation",
                        "Deviation from Spec",
                        deviation,
                        deviation,
                        "Align implementation with specification"
                    ))
                
                for missing in compliance.get("missing_implementations", []):
                    findings.append(self._create_finding(
                        execution_id,
                        "medium",
                        "spec_validation",
                        "Missing Implementation",
                        missing,
                        missing,
                        "Implement missing requirement"
                    ))
            
            spec_compliance = SpecComplianceResult(
                compliant=compliance.get("compliant", True),
                deviations=compliance.get("deviations", []),
                missing_implementations=compliance.get("missing_implementations", []),
                overall_assessment=validation_result.get("overall_assessment", "")
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            findings.append(self._create_finding(
                execution_id,
                "medium",
                "spec_validation",
                "Spec Validation Parse Error",
                f"LLM response could not be parsed as JSON: {str(e)}",
                response[:500] if 'response' in locals() else "No response captured",
                "Review LLM prompt and ensure it returns valid JSON"
            ))
            spec_compliance = None
        except Exception as e:
            logger.error(f"Spec validation failed: {e}")
            findings.append(self._create_finding(
                execution_id,
                "medium",
                "spec_validation",
                "Spec Validation Error",
                f"Spec validation execution failed: {str(e)}",
                str(e),
                "Review spec validation configuration and LLM connectivity"
            ))
            spec_compliance = None
        
        return findings, failed_checklist_items, spec_compliance
    
    def _build_spec_validation_prompt(
        self,
        spec_content: str,
        checklist_items: List[str],
        git_diff: str,
        copilot_result: Dict
    ) -> str:
        """Build prompt for spec validation."""
        template_str = self.prompts_config.get("spec_validation_prompt", "")
        
        if not template_str:
            # Fallback default prompt
            template_str = """# Task: Validate Implementation Against Specification

## Original Specification
{original_spec}

## Acceptance Criteria Checklist
{checklist_items}

## Changes Made
{git_diff}

## Implementation Summary
{copilot_summary}

## Files Modified
{files_modified}

## Files Created
{files_created}

Respond with JSON containing checklist_results, spec_compliance, and overall_assessment."""
        
        checklist_text = "\n".join([f"- [ ] {item}" for item in checklist_items])
        
        return template_str.format(
            original_spec=spec_content,
            checklist_items=checklist_text,
            git_diff=git_diff[:5000],  # Limit diff size
            copilot_summary=copilot_result.get("changes_summary", ""),
            files_modified=", ".join(copilot_result.get("files_modified", [])),
            files_created=", ".join(copilot_result.get("files_created", []))
        )
    
    async def _get_git_diff(self) -> str:
        """Get git diff of recent changes."""
        result = await self._run_command(
            "git --no-pager diff HEAD",
            30,
            self.repo_path
        )
        return result["stdout"]
    
    def _extract_checklist_from_spec(self, spec_content: str) -> List[str]:
        """Extract checklist items from spec."""
        pattern = re.compile(r"^- \[ \] (.+)$", re.MULTILINE)
        matches = pattern.findall(spec_content)
        return matches
    
    def _create_finding(
        self,
        execution_id: str,
        severity: str,
        category: str,
        title: str,
        description: str,
        evidence: str,
        suggested_fix: str
    ) -> Finding:
        """Create a finding object without persisting to state."""
        finding = Finding(
            finding_id=f"{execution_id}_{category}_{datetime.now().timestamp()}",
            execution_id=execution_id,
            severity=severity,
            category=category,
            title=title,
            description=description,
            evidence=evidence,
            suggested_fix=suggested_fix,
            created_at=datetime.now()
        )
        
        # Findings are persisted in batch by verify_phase_execution
        return finding
    
    def _check_findings_thresholds(self, findings_summary: Dict[str, int]) -> bool:
        """Check if findings are within acceptable thresholds."""
        thresholds = self.config.findings_thresholds
        
        if findings_summary.get("major", 0) > thresholds.get("major", 0):
            logger.warning(f"Major findings exceed threshold: {findings_summary['major']} > {thresholds['major']}")
            return False
        
        if findings_summary.get("medium", 0) > thresholds.get("medium", 3):
            logger.warning(f"Medium findings exceed threshold: {findings_summary['medium']} > {thresholds['medium']}")
            return False
        
        if findings_summary.get("minor", 0) > thresholds.get("minor", 10):
            logger.warning(f"Minor findings exceed threshold: {findings_summary['minor']} > {thresholds['minor']}")
            return False
        
        return True
    
    async def _run_command(
        self,
        command: str,
        timeout: int,
        working_dir: Path
    ) -> Dict[str, any]:
        """Run a shell command and return results."""
        logger.debug(f"Running command: {command} in {working_dir}")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return {
                "exit_code": process.returncode,
                "stdout": stdout.decode("utf-8", errors="ignore"),
                "stderr": stderr.decode("utf-8", errors="ignore")
            }
        except asyncio.TimeoutError:
            logger.error(f"Command timed out after {timeout}s: {command}")
            process.kill()
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e)
            }
    
    async def generate_feedback_spec(
        self,
        original_spec_path: Path,
        findings: List[Finding],
        failed_checklist_items: List[str],
        pass_number: int,
        copilot_summary: str
    ) -> Path:
        """Generate feedback spec for retry."""
        logger.info(f"Generating feedback spec for pass {pass_number}")
        
        # Read original spec
        original_spec = original_spec_path.read_text(encoding="utf-8")
        
        # Group findings by category
        findings_by_category = {}
        for finding in findings:
            category = finding.category
            if category not in findings_by_category:
                findings_by_category[category] = []
            findings_by_category[category].append(finding)
        
        # Aggregate suggested fixes
        suggested_fixes = [f.suggested_fix for f in findings if f.suggested_fix]
        
        # Render template
        template = self.jinja_env.get_template("feedback_spec.md.j2")
        feedback_content = template.render(
            original_spec=original_spec,
            pass_number=pass_number,
            findings_by_category=findings_by_category,
            failed_checklist_items=failed_checklist_items,
            copilot_summary=copilot_summary,
            suggested_fixes=suggested_fixes
        )
        
        # Save feedback spec
        feedback_path = original_spec_path.parent / f"feedback_spec_pass_{pass_number}.md"
        feedback_path.write_text(feedback_content, encoding="utf-8")
        
        logger.info(f"Feedback spec saved to {feedback_path}")
        return feedback_path
    
    async def generate_findings_json(
        self,
        phase_number: int,
        phase_title: str,
        pass_number: int,
        verification_result: VerificationResult,
        output_path: Path
    ) -> Path:
        """Generate findings JSON report."""
        logger.info(f"Generating findings JSON for phase {phase_number} pass {pass_number}")
        
        # Build JSON structure with all VerificationResult fields
        findings_data = {
            "phase_number": phase_number,
            "phase_title": phase_title,
            "pass_number": pass_number,
            "timestamp": datetime.now().isoformat(),
            "passed": verification_result.passed,
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "execution_id": f.execution_id,
                    "severity": f.severity,
                    "category": f.category,
                    "title": f.title,
                    "description": f.description,
                    "evidence": f.evidence,
                    "suggested_fix": f.suggested_fix,
                    "resolved": f.resolved,
                    "created_at": f.created_at.isoformat() if hasattr(f.created_at, 'isoformat') else str(f.created_at)
                }
                for f in verification_result.findings
            ],
            "findings_summary": verification_result.findings_summary,
            "failed_checklist_items": verification_result.failed_checklist_items,
            "spec_compliance": {
                "compliant": verification_result.spec_compliance.compliant,
                "deviations": verification_result.spec_compliance.deviations,
                "missing_implementations": verification_result.spec_compliance.missing_implementations,
                "overall_assessment": verification_result.spec_compliance.overall_assessment
            } if verification_result.spec_compliance else None,
            "checks_run": verification_result.checks_run,
            "execution_time": verification_result.execution_time
        }
        
        # Save JSON with proper formatting
        output_path.write_text(json.dumps(findings_data, indent=2, default=str), encoding="utf-8")
        
        logger.info(f"Findings JSON saved to {output_path}")
        return output_path

    async def generate_findings_report(
        self,
        phase_number: int,
        phase_title: str,
        pass_number: int,
        verification_result: VerificationResult,
        output_path: Path
    ) -> Path:
        """Generate findings markdown report."""
        logger.info(f"Generating findings report for phase {phase_number} pass {pass_number}")
        
        # Categorize findings by severity
        major_findings = [f for f in verification_result.findings if f.severity == "major"]
        medium_findings = [f for f in verification_result.findings if f.severity == "medium"]
        minor_findings = [f for f in verification_result.findings if f.severity == "minor"]
        
        # Render template
        template = self.jinja_env.get_template("findings.md.j2")
        report_content = template.render(
            phase_number=phase_number,
            phase_title=phase_title,
            pass_number=pass_number,
            timestamp=datetime.now().isoformat(),
            passed=verification_result.passed,
            findings_summary=verification_result.findings_summary,
            major_findings=major_findings,
            medium_findings=medium_findings,
            minor_findings=minor_findings,
            failed_checklist_items=verification_result.failed_checklist_items,
            checks_run=verification_result.checks_run
        )
        
        # Save report
        output_path.write_text(report_content, encoding="utf-8")
        
        logger.info(f"Findings report saved to {output_path}")
        return output_path
    
    async def generate_findings_reports(
        self,
        phase_number: int,
        phase_title: str,
        pass_number: int,
        verification_result: VerificationResult,
        output_dir: Path
    ) -> tuple[Path, Path]:
        """Generate both markdown and JSON findings reports.
        
        Returns:
            Tuple of (md_path, json_path)
        """
        logger.info(f"Generating findings reports (MD + JSON) for phase {phase_number} pass {pass_number}")
        
        # Generate markdown report
        md_path = output_dir / "findings_report.md"
        await self.generate_findings_report(
            phase_number, phase_title, pass_number, verification_result, md_path
        )
        
        # Generate JSON report
        json_path = output_dir / "Findings.json"
        await self.generate_findings_json(
            phase_number, phase_title, pass_number, verification_result, json_path
        )
        
        logger.info(f"Generated findings reports: {md_path}, {json_path}")
        return md_path, json_path
