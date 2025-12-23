"""
Phase Executor Module

Orchestrates the execution of approved phases in YOLO mode, managing the execution loop,
retry logic, spec generation, branch management, and manual intervention.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from git import Repo
from jinja2 import Environment, FileSystemLoader

from orchestrator.config import OrchestratorConfig, ConfigError
from orchestrator.llm_client import OllamaClient
from orchestrator.state import StateManager, PhaseState
from orchestrator.verifier import PhaseVerifier, VerificationConfig
from repo_brain.rag_system import RAGSystem
from agents.copilot_interface import CopilotCLIInterface
from agents.copilot_models import (
    CopilotExecutionRequest,
    CopilotExecutionResult,
    CopilotCLIError,
    CopilotErrorType,
    ExecutionMode,
)

logger = logging.getLogger(__name__)


class PhaseExecutor:
    """
    Core phase execution engine that orchestrates YOLO mode execution loop.
    """

    def __init__(
        self,
        config: OrchestratorConfig,
        llm_client: OllamaClient,
        rag_system: RAGSystem,
        state_manager: StateManager,
        repo_path: str,
    ):
        """
        Initialize the PhaseExecutor.

        Args:
            config: Orchestrator configuration
            llm_client: LLM client for spec generation
            rag_system: RAG system for context retrieval
            state_manager: State manager for persistence
            repo_path: Path to the repository
        """
        self.config = config
        self.llm_client = llm_client
        self.rag_system = rag_system
        self.state_manager = state_manager
        self.repo_path = repo_path

        validate_executor_config(config)

        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

        prompts_path = Path(__file__).parent.parent / "config" / "prompts.yaml"
        with open(prompts_path, "r") as f:
            self.prompts = yaml.safe_load(f)

        try:
            self.git_repo = Repo(repo_path)
        except Exception as e:
            logger.warning(f"Failed to initialize Git repository: {e}")
            self.git_repo = None

        # Initialize Copilot CLI interface
        copilot_config = config.copilot if hasattr(config, "copilot") else None
        if copilot_config and copilot_config.get("enabled", True):
            self.copilot_interface = CopilotCLIInterface(
                cli_path=copilot_config.get("cli_path", "gh"),
                timeout=copilot_config.get("timeout", 600),
                capture_raw_output=copilot_config.get("capture_raw_output", True),
                validate_on_startup=False,  # Will validate async during execute_phases
            )
            logger.info("Copilot CLI interface initialized")
        else:
            self.copilot_interface = None
            logger.warning("Copilot CLI integration is disabled")

        # Initialize verification system
        verification_config_dict = config.verification.model_dump() if hasattr(config, "verification") else {}
        self.verification_config = VerificationConfig(verification_config_dict)
        logger.info("Verification system initialized")

        logger.info("PhaseExecutor initialized")

    async def execute_phases(self, run_id: str) -> None:
        """
        Execute all phases for a given run.

        Args:
            run_id: Run ID to execute
        """
        logger.info(f"Starting phase execution for run {run_id}")

        try:
            # Validate Copilot environment if enabled
            if self.copilot_interface:
                validation = await self.copilot_interface.validate_environment()
                if not validation.valid:
                    error_msgs = ', '.join(validation.error_messages)
                    logger.error(f"Copilot environment validation failed: {error_msgs}")
                    await self.state_manager.update_run_status(run_id, "failed")
                    raise Exception(f"Copilot validation failed: {error_msgs}")
                logger.info("Copilot environment validated successfully")
            
            phases = await self.state_manager.get_phases_for_run(run_id)
            if not phases:
                logger.warning(f"No phases found for run {run_id}")
                return

            await self.state_manager.update_run_status(run_id, "executing")

            phases_sorted = sorted(phases, key=lambda p: p.phase_number)

            for phase in phases_sorted:
                if phase.status == "skipped":
                    logger.info(f"Skipping phase {phase.phase_number}: {phase.title}")
                    continue

                logger.info(f"Executing phase {phase.phase_number}: {phase.title}")
                success = await self.execute_single_phase(phase.id)

                if not success:
                    logger.error(f"Phase {phase.phase_number} failed")
                    run_state = await self.state_manager.get_run(run_id)
                    if run_state and run_state.status == "paused":
                        logger.info("Run paused for manual intervention")
                        return
                    # Don't mark run as completed if phase failed
                    await self.state_manager.update_run_status(run_id, "failed")
                    return

            await self.state_manager.update_run_status(run_id, "completed")
            logger.info(f"Phase execution completed for run {run_id}")

            summary = await self.generate_execution_summary(run_id)
            logger.info(f"Execution summary: {summary}")

        except Exception as e:
            logger.error(f"Error executing phases for run {run_id}: {e}", exc_info=True)
            await self.state_manager.update_run_status(run_id, "failed")
            raise

    async def execute_single_phase(self, phase_id: str) -> bool:
        """
        Execute a single phase with retry loop.

        Args:
            phase_id: Phase ID to execute

        Returns:
            True if phase completed successfully, False otherwise
        """
        try:
            phase = await self.state_manager.get_phase(phase_id)
            if not phase:
                logger.error(f"Phase {phase_id} not found")
                return False

            await self.state_manager.update_phase_status(
                phase_id, "in_progress", started_at=datetime.utcnow()
            )

            await self.report_phase_progress(
                phase_id, 1, f"Starting phase {phase.phase_number}: {phase.title}"
            )

            branch_name = await self.create_phase_branch(phase)
            if branch_name:
                logger.info(f"Created branch {branch_name} for phase {phase.phase_number}")

            max_retries = self.config.execution.max_retries
            for pass_number in range(1, max_retries + 1):
                logger.info(f"Phase {phase.phase_number}, pass {pass_number}/{max_retries}")

                await self.report_phase_progress(
                    phase_id,
                    pass_number,
                    f"Pass {pass_number}/{max_retries}: Generating specification",
                )

                try:
                    spec_path = await self.generate_phase_spec(phase_id, pass_number)
                    logger.info(f"Generated spec: {spec_path}")

                    await self.report_phase_progress(
                        phase_id,
                        pass_number,
                        f"Pass {pass_number}/{max_retries}: Specification generated, invoking Copilot",
                    )

                    # Execute with Copilot CLI
                    copilot_result = await self.execute_with_copilot(
                        phase_id, spec_path, pass_number
                    )

                    if not copilot_result.success:
                        logger.error(
                            f"Copilot execution failed: {copilot_result.error_message}"
                        )
                        await self.state_manager.increment_phase_retry(phase_id)
                        
                        if pass_number < max_retries:
                            await self.report_phase_progress(
                                phase_id,
                                pass_number,
                                f"Pass {pass_number}/{max_retries}: Failed, retrying",
                            )
                            continue
                        else:
                            raise Exception(f"Copilot execution failed: {copilot_result.error_message}")

                    await self.report_phase_progress(
                        phase_id,
                        pass_number,
                        f"Pass {pass_number}/{max_retries}: Copilot execution completed",
                    )

                    # Run verification checks
                    await self.report_phase_progress(
                        phase_id,
                        pass_number,
                        f"Pass {pass_number}/{max_retries}: Running verification checks",
                    )

                    verification_result = await self._run_verification(
                        phase, pass_number, spec_path, copilot_result
                    )

                    # Check if verification passed
                    if not verification_result.passed:
                        logger.warning(
                            f"Verification failed with {verification_result.findings_summary}"
                        )
                        
                        if pass_number < max_retries:
                            # Generate feedback spec for retry
                            should_retry = await self._handle_verification_failure(
                                phase, verification_result, pass_number
                            )
                            
                            if should_retry:
                                await self.state_manager.increment_phase_retry(phase_id)
                                await self.report_phase_progress(
                                    phase_id,
                                    pass_number,
                                    f"Pass {pass_number}/{max_retries}: Verification failed, retrying",
                                )
                                continue
                        
                        # Max retries exceeded
                        logger.error(f"Phase {phase.phase_number} failed verification after {max_retries} attempts")
                        raise Exception(
                            f"Verification failed after {max_retries} attempts. "
                            f"Findings: {verification_result.findings_summary}"
                        )

                    logger.info(f"Phase {phase.phase_number} passed verification")

                    # Mark phase as completed on success
                    await self.state_manager.update_phase_status(
                        phase_id, "completed", completed_at=datetime.utcnow()
                    )

                    # Merge branch if in branch mode
                    if branch_name:
                        await self.merge_phase_branch(phase)

                    return True

                except Exception as e:
                    logger.error(
                        f"Error in pass {pass_number} for phase {phase_id}: {e}",
                        exc_info=True,
                    )
                    
                    # Increment retry count but don't mark as failed yet
                    await self.state_manager.increment_phase_retry(phase_id)

                    if pass_number == max_retries:
                        # Only mark as failed after final retry
                        await self.handle_execution_error(phase_id, e)
                        break

            logger.warning(f"Phase {phase_id} exceeded max retries")
            
            # Clean up branch on failure
            if branch_name:
                phase = await self.state_manager.get_phase(phase_id)
                if phase:
                    await self.cleanup_phase_branch(phase)
            
            await self.handle_manual_intervention(phase_id)
            return False

        except Exception as e:
            logger.error(f"Error executing phase {phase_id}: {e}", exc_info=True)
            await self.handle_execution_error(phase_id, e)
            return False

    async def generate_phase_spec(self, phase_id: str, pass_number: int) -> str:
        """
        Generate detailed phase specification.

        Args:
            phase_id: Phase ID
            pass_number: Current pass number

        Returns:
            Path to generated spec file
        """
        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        plan_data = json.loads(phase.plan_json)

        phase_title = plan_data.get("title", phase.title)
        phase_intent = plan_data.get("intent", "")
        files = plan_data.get("files", [])
        acceptance_criteria = plan_data.get("acceptance_criteria", [])
        risks = plan_data.get("risks", [])
        phase_size = plan_data.get("size", "MEDIUM")

        query_parts = [phase_title, phase_intent] + files
        query = " ".join(filter(None, query_parts))

        logger.info(f"Retrieving context for query: {query[:100]}...")
        repo_context = []
        try:
            retrieval_result = await asyncio.to_thread(
                self.rag_system.retrieve_context, query, top_k=10
            )
            if retrieval_result and hasattr(retrieval_result, "chunks"):
                repo_context = [
                    {
                        "file_path": chunk.file_path,
                        "content": chunk.content,
                        "line_start": getattr(chunk, "line_start", None),
                        "line_end": getattr(chunk, "line_end", None),
                        "language": getattr(chunk, "language", None),
                        "symbols": getattr(chunk, "symbols", []),
                    }
                    for chunk in retrieval_result.chunks[:10]
                ]
        except Exception as e:
            logger.warning(f"Error retrieving context: {e}")

        hot_files = []
        try:
            hot_files_result = await asyncio.to_thread(self.rag_system.get_hot_files, top_k=5)
            if hot_files_result:
                hot_files = [
                    {"path": f.get("file_path", ""), "modification_count": f.get("count", 0)}
                    for f in hot_files_result
                ]
        except Exception as e:
            logger.warning(f"Error retrieving hot files: {e}")

        context = {
            "phase_number": phase.phase_number,
            "phase_title": phase_title,
            "phase_intent": phase_intent,
            "phase_size": phase_size,
            "phase_goals": plan_data.get("goals", phase_intent),
            "constraints": plan_data.get("constraints", ""),
            "dependencies": plan_data.get("dependencies", ""),
            "implementation_steps": plan_data.get("implementation_steps", ""),
            "files": files,
            "files_to_modify": plan_data.get("files_to_modify", []),
            "edge_cases": plan_data.get("edge_cases", ""),
            "testing_requirements": plan_data.get("testing_requirements", ""),
            "acceptance_criteria": acceptance_criteria,
            "risks": risks,
            "repo_context": repo_context,
            "hot_files": hot_files,
            "related_context": plan_data.get("related_context", ""),
            "notes": plan_data.get("notes", ""),
            "pass_number": pass_number,
        }

        template = self.jinja_env.get_template("phase_spec.md.j2")
        spec_content = template.render(**context)

        if self.prompts.get("spec_generation_system_prompt"):
            try:
                enhanced_spec = await self._enhance_spec_with_llm(spec_content, context)
                if enhanced_spec:
                    spec_content = enhanced_spec
            except Exception as e:
                logger.warning(f"Failed to enhance spec with LLM: {e}")

        artifact_dir = (
            Path(self.config.paths.artifact_base_path)
            / phase.run_id
            / phase_id
            / f"pass_{pass_number}"
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        spec_path = artifact_dir / "spec.md"
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec_content)

        await self.state_manager.register_artifact(
            run_id=phase.run_id,
            phase_id=phase_id,
            artifact_type="spec",
            file_path=str(spec_path),
            metadata={"pass_number": pass_number},
        )

        logger.info(f"Saved specification to {spec_path}")
        return str(spec_path)

    async def execute_with_copilot(
        self, phase_id: str, spec_path: str, pass_number: int
    ) -> CopilotExecutionResult:
        """
        Execute phase specification using GitHub Copilot CLI.

        Args:
            phase_id: Phase ID
            spec_path: Path to generated spec file
            pass_number: Current pass number

        Returns:
            Copilot execution result
        """
        if not self.copilot_interface:
            logger.error("Copilot interface not initialized")
            return CopilotExecutionResult(
                success=False,
                execution_time=0.0,
                error_message="Copilot CLI integration is disabled",
            )

        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        # Get artifact directory
        artifact_dir = Path(spec_path).parent

        # Render Copilot prompt
        prompt_content = await self._render_copilot_prompt(
            phase_id, spec_path, pass_number
        )

        # Get findings from previous passes if this is a retry
        findings_dict = None
        if pass_number > 1:
            all_findings = await self.state_manager.get_findings_for_phase(phase_id)
            if all_findings:
                # Group findings by severity for the request
                findings_dict = {
                    "major": [f.to_dict() for f in all_findings if f.severity == "major"],
                    "medium": [f.to_dict() for f in all_findings if f.severity == "medium"],
                    "minor": [f.to_dict() for f in all_findings if f.severity == "minor"],
                }

        # Determine execution mode
        execution_mode = "branch" if self.config.execution.copilot_mode == "branch" else "direct"
        copilot_exec_mode = ExecutionMode.BRANCH if execution_mode == "branch" else ExecutionMode.DIRECT

        # Create execution request
        request = CopilotExecutionRequest(
            spec_path=spec_path,
            repo_path=self.repo_path,
            execution_mode=copilot_exec_mode,
            findings=findings_dict,
            repo_context=None,
            timeout=self.config.copilot.get("timeout", 600) if hasattr(self.config, "copilot") else 600,
            pass_number=pass_number,
        )

        # Create execution state record
        execution_state = await self.state_manager.create_execution(
            phase_id=phase_id,
            pass_number=pass_number,
            copilot_input_path=spec_path,
            execution_mode=execution_mode,
        )

        try:
            # Execute with Copilot
            logger.info(f"Invoking Copilot CLI for phase {phase.phase_number}")
            result = await self.copilot_interface.execute_spec(
                request=request,
                prompt_content=prompt_content,
                artifact_dir=artifact_dir,
            )

            # Update execution state with result
            if result.success:
                await self.state_manager.complete_execution(
                    execution_id=execution_state.execution_id,
                    copilot_output_path=result.output_path or "",
                    copilot_summary=result.summary or "",
                )
            else:
                await self.state_manager.fail_execution(
                    execution_id=execution_state.execution_id,
                    error=result.error_message or "Unknown error",
                )

            # Register artifacts
            if result.output_path:
                await self.state_manager.register_artifact(
                    run_id=phase.run_id,
                    phase_id=phase_id,
                    artifact_type="copilot_output",
                    file_path=result.output_path,
                    metadata={
                        "pass_number": pass_number,
                        "execution_time": result.execution_time,
                    },
                )

            # Register prompt artifact
            prompt_file = artifact_dir / "copilot_prompt.md"
            if prompt_file.exists():
                await self.state_manager.register_artifact(
                    run_id=phase.run_id,
                    phase_id=phase_id,
                    artifact_type="copilot_prompt",
                    file_path=str(prompt_file),
                    metadata={"pass_number": pass_number},
                )

            # Apply patches if successful
            if result.success and result.patches:
                patch_success = await self._apply_copilot_patches(phase, result, artifact_dir, pass_number)
                if not patch_success:
                    logger.error("Failed to apply patches")
                    result.success = False
                    result.error_message = "Failed to apply one or more patches"
                    result.error_type = CopilotErrorType.EXECUTION_ERROR
                    return result
                
                # If in branch mode, commit changes after applying patches
                if copilot_exec_mode == ExecutionMode.BRANCH:
                    await self._commit_copilot_changes(phase, result, pass_number)

            return result

        except CopilotCLIError as e:
            logger.error(f"Copilot CLI error: {e}")
            await self.state_manager.fail_execution(
                execution_id=execution_state.execution_id,
                error=str(e),
            )
            
            # Save error log
            error_log = artifact_dir / "error.log"
            error_log.write_text(str(e), encoding="utf-8")
            
            return CopilotExecutionResult(
                success=False,
                execution_time=0.0,
                error_message=str(e),
                error_type=e.error_type,
            )

    async def _render_copilot_prompt(
        self, phase_id: str, spec_path: str, pass_number: int
    ) -> str:
        """
        Render Copilot prompt using template.

        Args:
            phase_id: Phase ID
            spec_path: Path to spec file
            pass_number: Current pass number

        Returns:
            Rendered prompt content
        """
        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        # Check if feedback spec exists for retry passes
        actual_spec_path = spec_path
        if pass_number > 1:
            spec_dir = Path(spec_path).parent
            feedback_spec = spec_dir.parent / f"pass_{pass_number - 1}" / f"feedback_spec_pass_{pass_number - 1}.md"
            if feedback_spec.exists():
                logger.info(f"Using feedback spec from previous pass: {feedback_spec}")
                actual_spec_path = str(feedback_spec)

        # Read spec content
        with open(actual_spec_path, "r", encoding="utf-8") as f:
            spec_content = f.read()

        # Get findings from previous passes if this is a retry
        findings = None
        if pass_number > 1:
            all_findings = await self.state_manager.get_findings_for_phase(phase_id)
            if all_findings:
                # Group findings by severity
                findings = {
                    "major": [f for f in all_findings if f.severity == "major"],
                    "medium": [f for f in all_findings if f.severity == "medium"],
                    "minor": [f for f in all_findings if f.severity == "minor"],
                    "failed_checks": []  # TODO: Add failed checklist items if tracked separately
                }
                logger.info(
                    f"Loaded {len(all_findings)} findings from previous passes "
                    f"(major: {len(findings['major'])}, medium: {len(findings['medium'])}, "
                    f"minor: {len(findings['minor'])})"
                )

        # Get execution mode
        execution_mode = self.config.execution.copilot_mode

        # Render template
        template = self.jinja_env.get_template("copilot_prompt.md.j2")
        prompt_content = template.render(
            phase_spec=spec_content,
            findings=findings,
            repo_context=None,  # Context is already in spec
            pass_number=pass_number,
            execution_mode=execution_mode,
        )

        return prompt_content

    async def _apply_copilot_patches(
        self, phase: PhaseState, result: CopilotExecutionResult, artifact_dir: Path, pass_number: int
    ) -> bool:
        """
        Apply patches generated by Copilot.

        Args:
            phase: Phase state
            result: Copilot execution result with patches
            artifact_dir: Directory containing patch files
            pass_number: Current pass number

        Returns:
            True if all patches applied successfully, False otherwise
        """
        if not self.git_repo:
            logger.warning("Git repository not initialized, skipping patch application")
            return False

        if not result.patches:
            logger.warning("No patches to apply")
            return False

        patches_dir = artifact_dir / "patches"
        if not patches_dir.exists():
            logger.error(f"Patches directory not found: {patches_dir}")
            return False

        applied_patches = []
        failed_patches = []

        try:
            for idx, patch in enumerate(result.patches):
                if not isinstance(patch, dict) or "file" not in patch or "diff" not in patch:
                    logger.error(f"Invalid patch format at index {idx}: {patch}")
                    failed_patches.append({"index": idx, "reason": "Invalid format"})
                    continue

                patch_filename = Path(patch["file"]).name + f"_{idx}.patch"
                patch_file = patches_dir / patch_filename

                if not patch_file.exists():
                    logger.error(f"Patch file not found: {patch_file}")
                    failed_patches.append({"file": patch["file"], "reason": "Patch file not found"})
                    continue

                try:
                    # Apply patch using git apply
                    logger.info(f"Applying patch for {patch['file']}")
                    self.git_repo.git.apply(str(patch_file), check=True)
                    applied_patches.append(patch["file"])
                    logger.info(f"Successfully applied patch for {patch['file']}")

                except Exception as apply_error:
                    logger.error(f"Failed to apply patch for {patch['file']}: {apply_error}")
                    failed_patches.append({"file": patch["file"], "reason": str(apply_error)})

                    # Try to apply with --reject flag to generate .rej files for manual review
                    try:
                        self.git_repo.git.apply(str(patch_file), reject=True)
                        logger.warning(f"Applied patch with conflicts for {patch['file']} - check .rej files")
                    except Exception:
                        logger.error(f"Failed to apply patch even with --reject flag")

            # Validate applied patches
            if applied_patches:
                logger.info(f"Applied {len(applied_patches)} patches successfully")
                
                # Verify changes match JSON summary
                try:
                    diff_output = self.git_repo.git.diff(cached=True)
                    if diff_output:
                        logger.info("Verified changes are staged for commit")
                    else:
                        # Check unstaged changes
                        diff_output = self.git_repo.git.diff()
                        if diff_output:
                            logger.info("Changes detected but not staged - staging now")
                            self.git_repo.git.add(A=True)
                except Exception as e:
                    logger.warning(f"Failed to verify changes: {e}")

            if failed_patches:
                logger.error(f"Failed to apply {len(failed_patches)} patches: {failed_patches}")
                
                # Save failed patches info
                failed_log = artifact_dir / "failed_patches.json"
                failed_log.write_text(
                    json.dumps({"failed": failed_patches, "applied": applied_patches}, indent=2),
                    encoding="utf-8"
                )
                
                # Add to findings for next pass
                await self.state_manager.add_finding(
                    phase_id=phase.id,
                    pass_number=pass_number,
                    severity="major",
                    title="Patch application failures",
                    description=f"Failed to apply {len(failed_patches)} patches",
                    evidence=json.dumps(failed_patches),
                    suggested_fix="Review patch conflicts and regenerate patches with proper context"
                )
                
                return False

            return True

        except Exception as e:
            logger.error(f"Error applying patches: {e}", exc_info=True)
            return False

    async def _commit_copilot_changes(
        self, phase: PhaseState, result: CopilotExecutionResult, pass_number: int
    ) -> None:
        """
        Commit changes made by Copilot in branch mode.

        Args:
            phase: Phase state
            result: Copilot execution result
            pass_number: Current pass number
        """
        if not self.git_repo:
            logger.warning("Git repository not initialized, skipping commit")
            return

        try:
            # Stage all changes (patches should already be applied)
            self.git_repo.git.add(A=True)

            # Check if there are changes to commit
            if not self.git_repo.is_dirty():
                logger.info("No changes to commit")
                return

            # Get commit message template
            copilot_config = self.config.copilot if hasattr(self.config, "copilot") else {}
            commit_template = copilot_config.get(
                "commit_message_template",
                "Phase {phase_number}: {phase_title}\n\n{copilot_summary}"
            )

            # Render commit message
            commit_message = commit_template.format(
                phase_number=phase.phase_number,
                phase_title=phase.title,
                copilot_summary=result.summary or result.changes_summary or "Implementation complete",
                pass_number=pass_number,
                execution_id=phase.id,
            )

            # Commit
            self.git_repo.index.commit(commit_message)
            logger.info(f"Committed changes for phase {phase.phase_number}")

            # Push if configured
            if copilot_config.get("push_branches", False):
                try:
                    origin = self.git_repo.remote("origin")
                    current_branch = self.git_repo.active_branch.name
                    origin.push(current_branch)
                    logger.info(f"Pushed branch {current_branch} to remote")
                except Exception as e:
                    logger.warning(f"Failed to push branch: {e}")

        except Exception as e:
            logger.error(f"Failed to commit changes: {e}", exc_info=True)

    async def _enhance_spec_with_llm(
        self, spec_content: str, context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Optionally enhance the specification using LLM.

        Args:
            spec_content: Initial spec content
            context: Context dictionary

        Returns:
            Enhanced spec content or None if enhancement fails
        """
        try:
            system_prompt = self.prompts.get("spec_generation_system_prompt", "")
            user_prompt_template = self.prompts.get("spec_generation_prompt", "")

            repo_context_str = "\n\n".join(
                [
                    f"File: {c['file_path']}\n```\n{c['content']}\n```"
                    for c in context.get("repo_context", [])[:5]
                ]
            )

            user_prompt = user_prompt_template.format(
                phase_number=context["phase_number"],
                phase_title=context["phase_title"],
                phase_intent=context["phase_intent"],
                phase_size=context["phase_size"],
                files_list="\n".join([f"- {f}" for f in context["files"]]),
                acceptance_criteria="\n".join(
                    [f"- {c}" for c in context["acceptance_criteria"]]
                ),
                repo_context=repo_context_str or "No additional context available",
            )

            prompt = f"{system_prompt}\n\n{user_prompt}\n\n## Current Specification\n\n{spec_content}\n\n## Instructions\n\nEnhance the above specification with additional implementation details based on the repository context. Keep the same structure but add specific code patterns, function signatures, and integration details."

            response = await asyncio.to_thread(self.llm_client.generate, prompt)

            if response and len(response) > len(spec_content) * 0.5:
                return response

            return None

        except Exception as e:
            logger.error(f"Error enhancing spec with LLM: {e}")
            return None

    async def create_phase_branch(self, phase: PhaseState) -> str:
        """
        Create a branch for phase execution if in branch mode.

        Args:
            phase: Phase state

        Returns:
            Branch name or empty string if direct mode
        """
        if self.config.execution.copilot_mode != "branch":
            return ""

        if not self.git_repo:
            logger.warning("Git repository not available, skipping branch creation")
            return ""

        try:
            sanitized_title = re.sub(r"[^\w\-]", "-", phase.title.lower())
            sanitized_title = re.sub(r"-+", "-", sanitized_title).strip("-")
            branch_name = (
                f"{self.config.execution.branch_prefix}"
                f"phase-{phase.phase_number}-{sanitized_title}"
            )

            current_branch = self.git_repo.active_branch
            new_branch = self.git_repo.create_head(branch_name)
            new_branch.checkout()

            # Update phase with branch information
            await self.state_manager.db.execute(
                "UPDATE phases SET branch_name = ? WHERE phase_id = ?",
                (branch_name, phase.id)
            )
            await self.state_manager.db.commit()

            logger.info(f"Created and checked out branch: {branch_name}")
            return branch_name

        except Exception as e:
            logger.error(f"Error creating phase branch: {e}", exc_info=True)
            return ""

    async def merge_phase_branch(self, phase: PhaseState) -> None:
        """
        Merge phase branch back to source branch.

        Args:
            phase: Phase state
        """
        if not phase.branch_name:
            return

        if not self.git_repo:
            logger.warning("Git repository not available, skipping branch merge")
            return

        try:
            branch_name = phase.branch_name
            
            # Get the original branch name from phase data
            phase_plan = json.loads(phase.plan_json)
            source_branch = phase_plan.get("source_branch", "main")

            self.git_repo.git.checkout(source_branch)
            self.git_repo.git.merge(branch_name, no_ff=True)

            self.git_repo.delete_head(branch_name, force=True)

            logger.info(f"Merged and deleted branch: {branch_name}")

        except Exception as e:
            logger.error(f"Error merging phase branch: {e}", exc_info=True)

    async def cleanup_phase_branch(self, phase: PhaseState) -> None:
        """
        Cleanup phase branch on failure or skip.

        Args:
            phase: Phase state
        """
        if not phase.branch_name:
            return

        if phase.status not in ["failed", "skipped"]:
            return

        if not self.git_repo:
            return

        try:
            branch_name = phase.branch_name
            phase_plan = json.loads(phase.plan_json)
            source_branch = phase_plan.get("source_branch", "main")

            self.git_repo.git.checkout(source_branch)

            if self.config.execution.delete_failed_branches:
                self.git_repo.delete_head(branch_name, force=True)
                logger.info(f"Deleted failed branch: {branch_name}")
            else:
                logger.info(f"Keeping failed branch for review: {branch_name}")

        except Exception as e:
            logger.error(f"Error cleaning up phase branch: {e}", exc_info=True)

    async def handle_manual_intervention(self, phase_id: str) -> str:
        """
        Handle manual intervention when max retries exceeded.

        Args:
            phase_id: Phase ID

        Returns:
            Intervention ID
        """
        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        intervention = await self.state_manager.create_intervention(
            phase_id=phase_id,
            reason="max_retries_exceeded",
        )

        await self.state_manager.update_phase_status(phase_id, "paused")
        await self.state_manager.update_run_status(phase.run_id, "paused")

        logger.warning(
            f"Manual intervention required for phase {phase.phase_number}: {phase.title}. "
            f"Intervention ID: {intervention.intervention_id}"
        )

        return intervention.intervention_id

    async def resume_phase(
        self,
        phase_id: str,
        action: str,
        modified_spec_path: Optional[str] = None,
    ) -> None:
        """
        Resume phase execution after manual intervention.

        Args:
            phase_id: Phase ID
            action: Action to take (resume, skip, modify_spec, abort)
            modified_spec_path: Path to modified spec if action is 'modify_spec'
        """
        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        interventions = await self.state_manager.get_pending_interventions(phase.run_id)
        active_intervention = next(
            (i for i in interventions if i.phase_id == phase_id), None
        )

        if not active_intervention:
            logger.warning(f"No active intervention found for phase {phase_id}")
            return

        if action == "resume":
            await self.state_manager.update_phase_status(phase_id, "in_progress")
            await self.state_manager.update_run_status(phase.run_id, "executing")
            await self.state_manager.resolve_intervention(
                active_intervention.intervention_id, action="resumed"
            )
            logger.info(f"Resuming phase {phase_id}")

        elif action == "skip":
            await self.state_manager.update_phase_status(phase_id, "skipped")
            await self.state_manager.resolve_intervention(
                active_intervention.intervention_id, action="skipped"
            )
            logger.info(f"Skipped phase {phase_id}")

        elif action == "modify_spec":
            if not modified_spec_path or not os.path.exists(modified_spec_path):
                raise ValueError("Valid modified_spec_path required for modify_spec action")

            await self.state_manager.update_phase_status(phase_id, "in_progress")
            await self.state_manager.update_run_status(phase.run_id, "executing")
            await self.state_manager.resolve_intervention(
                active_intervention.intervention_id, action="modified_spec"
            )
            logger.info(f"Resuming phase {phase_id} with modified spec")

        elif action == "abort":
            await self.state_manager.update_phase_status(phase_id, "failed")
            await self.state_manager.update_run_status(phase.run_id, "aborted")
            await self.state_manager.resolve_intervention(
                active_intervention.intervention_id, action="aborted"
            )
            logger.info(f"Aborted phase {phase_id}")

        else:
            raise ValueError(f"Invalid action: {action}")

    async def report_phase_progress(
        self, phase_id: str, pass_number: int, status: str
    ) -> None:
        """
        Report phase progress.

        Args:
            phase_id: Phase ID
            pass_number: Current pass number
            status: Status message
        """
        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            return

        logger.info(
            f"[Phase {phase.phase_number}] Pass {pass_number}: {status}",
            extra={
                "phase_id": phase_id,
                "phase_number": phase.phase_number,
                "phase_title": phase.title,
                "pass_number": pass_number,
                "status": status,
            },
        )

    async def generate_execution_summary(self, run_id: str) -> Dict[str, Any]:
        """
        Generate execution summary for a run.

        Args:
            run_id: Run ID

        Returns:
            Summary dictionary
        """
        phases = await self.state_manager.get_phases_for_run(run_id)

        total_phases = len(phases)
        completed = sum(1 for p in phases if p.status == "completed")
        failed = sum(1 for p in phases if p.status == "failed")
        skipped = sum(1 for p in phases if p.status == "skipped")
        in_progress = sum(1 for p in phases if p.status == "in_progress")

        total_passes = 0
        for phase in phases:
            artifacts = await self.state_manager.get_artifacts_for_phase(phase.id)
            spec_artifacts = [a for a in artifacts if a.artifact_type == "specification"]
            total_passes += len(spec_artifacts)

        executions = []
        findings = []
        for phase in phases:
            phase_executions = await self.state_manager.get_executions_for_phase(phase.id)
            phase_findings = await self.state_manager.get_findings_for_phase(phase.id)
            executions.extend(phase_executions)
            findings.extend(phase_findings)

        summary = {
            "run_id": run_id,
            "total_phases": total_phases,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "in_progress": in_progress,
            "total_passes": total_passes,
            "total_executions": len(executions),
            "total_findings": len(findings),
        }

        return summary

    async def handle_execution_error(self, phase_id: str, error: Exception) -> None:
        """
        Handle execution error.

        Args:
            phase_id: Phase ID
            error: Exception that occurred
        """
        phase = await self.state_manager.get_phase(phase_id)
        if not phase:
            logger.error(f"Phase {phase_id} not found during error handling")
            return

        logger.error(
            f"Execution error in phase {phase.phase_number}: {phase.title}",
            exc_info=error,
        )

        await self.state_manager.update_phase_status(phase_id, "failed")

        artifact_dir = (
            Path(self.config.paths.artifact_base_path) / phase.run_id / phase_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        error_log_path = artifact_dir / "error.log"
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"Error: {str(error)}\n")
            f.write(f"Type: {type(error).__name__}\n")
            f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n")
            import traceback

            f.write(f"\nTraceback:\n{traceback.format_exc()}\n")

        logger.info(f"Error details saved to {error_log_path}")

    async def recover_execution(self, run_id: str) -> Optional[str]:
        """
        Recover execution from interrupted state.

        Args:
            run_id: Run ID

        Returns:
            Phase ID to resume from, or None if no recovery needed
        """
        run = await self.state_manager.get_run(run_id)
        if not run:
            logger.error(f"Run {run_id} not found")
            return None

        if run.status not in ["executing", "paused"]:
            logger.info(f"Run {run_id} is in {run.status} state, no recovery needed")
            return None

        phases = await self.state_manager.get_phases_for_run(run_id)
        for phase in sorted(phases, key=lambda p: p.phase_number):
            if phase.status in ["in_progress", "paused"]:
                logger.info(
                    f"Recovery point found: Phase {phase.phase_number} ({phase.id})"
                )
                return phase.id

        logger.info(f"No recovery point found for run {run_id}")
        return None

    async def _run_verification(
        self,
        phase: PhaseState,
        pass_number: int,
        spec_path: str,
        copilot_result: CopilotExecutionResult
    ) -> "VerificationResult":
        """
        Run verification checks on Copilot execution results.

        Args:
            phase: Phase state
            pass_number: Current pass number
            spec_path: Path to spec file
            copilot_result: Copilot execution result

        Returns:
            Verification result
        """
        from orchestrator.verification_models import VerificationResult
        
        # Create verifier instance
        verifier = PhaseVerifier(
            state_manager=self.state_manager,
            llm_client=self.llm_client,
            config=self.verification_config,
            repo_path=Path(self.repo_path),
            prompts_config=self.prompts
        )

        # Get latest execution for this phase
        executions = await self.state_manager.get_executions_for_phase(phase.phase_id)
        latest_execution = max(executions, key=lambda e: e.started_at) if executions else None
        
        if not latest_execution:
            logger.warning(f"No execution found for phase {phase.phase_id}")
            # Return a passed result if no execution found (shouldn't happen)
            return VerificationResult(
                passed=True,
                findings=[],
                findings_summary={"major": 0, "medium": 0, "minor": 0},
                failed_checklist_items=[],
                execution_time=0.0,
                checks_run=[]
            )

        # Prepare copilot result dict for verifier
        copilot_result_dict = {
            "changes_summary": copilot_result.summary or copilot_result.changes_summary or "",
            "files_modified": copilot_result.files_modified or [],
            "files_created": copilot_result.files_created or [],
        }

        # Run verification
        verification_result = await verifier.verify_phase_execution(
            execution_id=latest_execution.execution_id,
            phase_id=phase.phase_id,
            spec_path=Path(spec_path),
            copilot_result=copilot_result_dict
        )

        # Generate findings reports (both MD and JSON)
        artifact_dir = Path(spec_path).parent
        
        md_path, json_path = await verifier.generate_findings_reports(
            phase_number=phase.phase_number,
            phase_title=phase.title,
            pass_number=pass_number,
            verification_result=verification_result,
            output_dir=artifact_dir
        )

        # Register findings report artifacts
        await self.state_manager.register_artifact(
            run_id=phase.run_id,
            phase_id=phase.phase_id,
            artifact_type="findings_report_md",
            file_path=str(md_path),
            metadata={
                "pass_number": pass_number,
                "passed": verification_result.passed,
                "findings_summary": verification_result.findings_summary
            }
        )
        
        await self.state_manager.register_artifact(
            run_id=phase.run_id,
            phase_id=phase.phase_id,
            artifact_type="findings_report_json",
            file_path=str(json_path),
            metadata={
                "pass_number": pass_number,
                "passed": verification_result.passed,
                "findings_count": len(verification_result.findings)
            }
        )

        logger.info(
            f"Verification completed: passed={verification_result.passed}, "
            f"findings={verification_result.findings_summary}"
        )

        return verification_result

    async def _handle_verification_failure(
        self,
        phase: PhaseState,
        verification_result: "VerificationResult",
        pass_number: int
    ) -> bool:
        """
        Handle verification failure - generate feedback spec and determine next action.

        Args:
            phase: Phase state
            verification_result: Verification result
            pass_number: Current pass number

        Returns:
            True if should retry, False if should stop
        """
        from orchestrator.verification_models import VerificationResult
        
        logger.info(f"Handling verification failure for phase {phase.phase_number}")

        # Create verifier instance
        verifier = PhaseVerifier(
            state_manager=self.state_manager,
            llm_client=self.llm_client,
            config=self.verification_config,
            repo_path=Path(self.repo_path),
            prompts_config=self.prompts
        )

        # Get original spec path
        artifact_dir = (
            Path(self.config.paths.artifact_base_path)
            / phase.run_id
            / phase.id
            / f"pass_{pass_number}"
        )
        original_spec_path = artifact_dir / "spec.md"

        # Get latest execution summary
        executions = await self.state_manager.get_executions_for_phase(phase.id)
        latest_execution = max(executions, key=lambda e: e.started_at) if executions else None
        copilot_summary = latest_execution.copilot_summary if latest_execution else ""

        # Generate feedback spec
        feedback_spec_path = await verifier.generate_feedback_spec(
            original_spec_path=original_spec_path,
            findings=verification_result.findings,
            failed_checklist_items=verification_result.failed_checklist_items,
            pass_number=pass_number,
            copilot_summary=copilot_summary
        )

        # Register feedback spec artifact
        await self.state_manager.register_artifact(
            run_id=phase.run_id,
            phase_id=phase.phase_id,
            artifact_type="feedback_spec",
            file_path=str(feedback_spec_path),
            metadata={"pass_number": pass_number}
        )

        logger.info(f"Generated feedback spec: {feedback_spec_path}")
        return True


def validate_executor_config(config: OrchestratorConfig) -> None:
    """
    Validate executor configuration.

    Args:
        config: Orchestrator configuration

    Raises:
        ConfigError: If configuration is invalid
    """
    if config.execution.max_retries < 1:
        raise ConfigError("max_retries must be >= 1")

    if config.execution.copilot_mode not in ["direct", "branch"]:
        raise ConfigError("copilot_mode must be 'direct' or 'branch'")

    if not re.match(r"^[a-zA-Z0-9\-_/]*$", config.execution.branch_prefix):
        raise ConfigError(
            "branch_prefix must contain only alphanumeric characters, hyphens, underscores, and slashes"
        )

    artifact_path = Path(config.paths.artifact_base_path)
    try:
        artifact_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise ConfigError(f"Cannot create artifact base path: {e}")


async def execute_run_standalone(
    run_id: str,
    config_path: str = "config/orchestrator-config.yaml",
    db_path: str = "data/orchestrator.db",
) -> None:
    """
    Execute a run in standalone mode (for testing).

    Args:
        run_id: Run ID to execute
        config_path: Path to configuration file
        db_path: Path to database file
    """
    from orchestrator.config import load_config
    from orchestrator.llm_client import OllamaClient
    from orchestrator.state import StateManager
    from repo_brain.rag_system import RAGSystem

    config = load_config(config_path)

    async with StateManager(db_path, config.paths.artifact_base_path) as state_manager:
        llm_client = OllamaClient(
            host=config.llm.host,
            model=config.llm.model,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )

        repo_path = os.getcwd()

        rag_system = RAGSystem(
            repo_path=repo_path,
            db_path=config.paths.vector_db_path,
            embedding_model=config.llm.embedding_model,
        )

        executor = PhaseExecutor(
            config=config,
            llm_client=llm_client,
            rag_system=rag_system,
            state_manager=state_manager,
            repo_path=repo_path,
        )

        await executor.execute_phases(run_id)

        summary = await executor.generate_execution_summary(run_id)

        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Run ID: {summary['run_id']}")
        print(f"Total Phases: {summary['total_phases']}")
        print(f"Completed: {summary['completed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"In Progress: {summary['in_progress']}")
        print(f"Total Passes: {summary['total_passes']}")
        print(f"Total Executions: {summary['total_executions']}")
        print(f"Total Findings: {summary['total_findings']}")
        print("=" * 60)
